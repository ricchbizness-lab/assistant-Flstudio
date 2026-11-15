"""Découpage d'un morceau en sections (intro, couplet, refrain...) sans étiquette musicale.

Méthode : contraste spectral avant/après chaque instant.
1. Toutes les 100 ms, énergie de la somme mono dans les 24 bandes Bark.
2. Pour chaque instant t, moyenne des énergies sur les ``context_s`` secondes
   avant et après t, conversion en dB, différence par bande.
3. Seules comptent les bandes à moins de ``dynamic_db`` de la bande la plus forte
   (une bande quasi vide fluctue beaucoup en dB sans rien signifier).
4. Contraste = moyenne quadratique des différences (dB). Une frontière est un
   maximum local du contraste au-dessus de ``threshold_db`` et à au moins
   ``min_section_s`` de la précédente (8 s par défaut : environ 4 mesures à 130-140 BPM ;
   choisi sur deux morceaux réels, sans vérité terrain, à valider).

Le seuil est en dB, donc interprétable : par défaut une section commence quand le
spectre moyen change d'au moins 3 dB. Un signal stationnaire ne produit aucune
frontière. Les frontières peuvent aussi être imposées par l'utilisateur.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import stft

from .measures.loudness import measure_loudness
from .measures.spectrum import BARK_EDGES

HOP_S = 0.1


@dataclass(frozen=True)
class Section:
    index: int
    start: float
    end: float

    @property
    def label(self) -> str:
        return chr(ord("A") + self.index) if self.index < 26 else f"S{self.index + 1}"


def bark_frames(x: np.ndarray, fs: int) -> np.ndarray:
    """Énergie par bande Bark, une trame toutes les 100 ms : forme (trames, 24)."""
    mono = x.mean(axis=1) if x.ndim == 2 else x
    hop = int(round(HOP_S * fs))
    nper = 2 * hop
    f, _, z = stft(mono, fs=fs, nperseg=nper, noverlap=nper - hop, boundary="even", padded=True)
    p = np.abs(z) ** 2
    idx = np.searchsorted(BARK_EDGES, f, side="right") - 1
    out = np.zeros((p.shape[1], len(BARK_EDGES) - 1))
    for b in range(len(BARK_EDGES) - 1):
        sel = idx == b
        if sel.any():
            out[:, b] = p[sel].sum(axis=0)
    return out


def contrast_curve(frames: np.ndarray, context_s: float = 4.0, dynamic_db: float = 40.0) -> np.ndarray:
    k = int(round(context_s / HOP_S))
    n = frames.shape[0]
    c = np.zeros(n)
    if n < 2 * k:
        return c
    cs = np.concatenate([np.zeros((1, frames.shape[1])), np.cumsum(frames, axis=0)])
    for t in range(k, n - k + 1):
        before = (cs[t] - cs[t - k]) / k
        after = (cs[t + k] - cs[t]) / k
        with np.errstate(divide="ignore"):
            db_b, db_a = 10 * np.log10(before + 1e-30), 10 * np.log10(after + 1e-30)
        top = max(db_b.max(), db_a.max())
        used = np.maximum(db_b, db_a) > top - dynamic_db
        d = np.clip(db_a[used] - db_b[used], -dynamic_db, dynamic_db)
        c[t] = float(np.sqrt(np.mean(d * d))) if d.size else 0.0
    return c


def detect_boundaries(x: np.ndarray, fs: int, threshold_db: float = 3.0, min_section_s: float = 8.0,
                      context_s: float = 4.0) -> list[float]:
    c = contrast_curve(bark_frames(x, fs), context_s)
    gap = int(round(min_section_s / HOP_S))
    candidates = [t for t in range(1, len(c) - 1) if c[t] >= threshold_db and c[t] >= c[t - 1] and c[t] >= c[t + 1]]
    chosen: list[int] = []
    for t in sorted(candidates, key=lambda t: -c[t]):
        if all(abs(t - u) >= gap for u in chosen):
            chosen.append(t)
    return [round(t * HOP_S, 2) for t in sorted(chosen)]


def make_sections(duration: float, boundaries: list[float]) -> list[Section]:
    cuts = [0.0] + sorted(b for b in boundaries if 0.0 < b < duration) + [duration]
    return [Section(i, cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]


def section_table(x: np.ndarray, fs: int, sections: list[Section]) -> list[dict]:
    rows = []
    for s in sections:
        seg = x[int(s.start * fs):int(s.end * fs)]
        lo = measure_loudness(seg, fs)
        rows.append({"label": s.label, "start_s": round(s.start, 2), "end_s": round(s.end, 2),
                     "duration_s": round(s.end - s.start, 2),
                     "integrated_lufs": None if not np.isfinite(lo.integrated) else round(lo.integrated, 2)})
    finite = [r for r in rows if r["integrated_lufs"] is not None]
    if finite:
        loudest = max(finite, key=lambda r: r["integrated_lufs"])
        for r in rows:
            r["loudest"] = r is loudest
    return rows
