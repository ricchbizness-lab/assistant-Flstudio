"""Masquage simultané entre stems (modèle figé dans docs/STEP3_THRESHOLDS.md, §1).

Pour une cible i et un masqueur M (somme des autres stems, ou un seul stem j) :
1. seuil = énergie de M étalée sur l'échelle Bark (fonction de Schroeder) - 6 dB ;
2. SMR = énergie de la cible - seuil, par trame, canal et bande ;
3. on ne regarde que les trames où la cible joue et les bandes qui comptent pour
   elle (à moins de 30 dB de sa bande la plus forte) ;
4. une case (trame, bande) est masquée si le SMR est négatif dans tous les canaux
   où la bande compte (la stéréo peut donc démasquer).

Limites assumées : seuil relatif (indépendant du volume d'écoute), pas de masquage
temporel avant/après, modèle de masquage monaural appliqué canal par canal.
Chevauchement d'énergie ne veut pas dire inaudibilité : ces chiffres indiquent où
regarder, l'oreille tranche.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import butter, sosfiltfilt

from .measures.spectrum import BARK_EDGES, hz_to_bark

OFFSET_DB = 6.0
RELEVANT_DB = 30.0
ACTIVE_DB = 30.0
ACTIVE_PCT = 95.0
EPS = 1e-20

BAND_LABELS = [f"{int(lo)}-{int(hi)} Hz" for lo, hi in zip(BARK_EDGES[:-1], BARK_EDGES[1:])]


def schroeder_db(dz):
    dz = np.asarray(dz, dtype=float) + 0.474
    return 15.81 + 7.5 * dz - 17.5 * np.sqrt(1.0 + dz * dz)


def spreading_matrix() -> np.ndarray:
    """S[cible, masqueur] linéaire, décalage de 6 dB inclus."""
    z = hz_to_bark(np.sqrt(BARK_EDGES[:-1] * BARK_EDGES[1:]))
    return 10.0 ** ((schroeder_db(z[:, None] - z[None, :]) - OFFSET_DB) / 10.0)


SPREAD = spreading_matrix()


def threshold(e_masker: np.ndarray) -> np.ndarray:
    """e_masker (..., 24) -> seuil de masquage (..., 24)."""
    return e_masker @ SPREAD.T


@dataclass
class TargetMasking:
    masked_ratio: np.ndarray        # (24,) NaN si la bande ne compte jamais
    energy_masked_pct: float
    median_smr_db: float | None
    band_masked_energy: np.ndarray  # (24,) énergie masquée par bande (pour localiser le conflit)
    active_frames: int
    median_smr_overlap_db: float | None = None   # SMR médian sur les trames où le masqueur joue aussi
    overlap_pct: float | None = None             # part des trames actives de la cible où le masqueur joue


def relevance(e_target: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(trames actives (T,), cases pertinentes (T, C, B)) pour une cible (T, C, B)."""
    total = e_target.sum(axis=(1, 2))
    ref = np.percentile(total, ACTIVE_PCT) if total.size else 0.0
    active = (total >= ref * 10 ** (-ACTIVE_DB / 10)) & (total > EPS)
    peak = e_target.max(axis=2, keepdims=True)
    rel = (e_target >= peak * 10 ** (-RELEVANT_DB / 10)) & (e_target > EPS) & active[:, None, None]
    return active, rel


def masker_activity(e_masker: np.ndarray) -> np.ndarray:
    """Trames où le masqueur joue (même règle que pour la cible)."""
    return relevance(e_masker)[0]


def mask_target(e_target: np.ndarray, thr: np.ndarray, rel_info=None,
                masker_active: np.ndarray | None = None) -> TargetMasking:
    active, rel = rel_info if rel_info is not None else relevance(e_target)
    smr = 10 * np.log10(np.maximum(e_target, EPS)) - 10 * np.log10(np.maximum(thr, EPS))
    any_rel = rel.any(axis=1)                                         # (T, B)
    smr_cell = np.where(rel, smr, -np.inf).max(axis=1)               # SMR le plus favorable des canaux pertinents
    masked = any_rel & (smr_cell < 0)
    n_rel = any_rel.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        ratio = np.where(n_rel > 0, masked.sum(axis=0) / np.maximum(n_rel, 1), np.nan)
    e_rel = np.where(rel, e_target, 0.0)
    e_masked = np.where(masked[:, None, :], e_rel, 0.0)
    total = e_rel.sum()
    vals = smr_cell[any_rel]
    smr_ov, ov_pct = None, None
    if masker_active is not None:
        both = any_rel & masker_active[:, None]
        if both.any():
            smr_ov = float(np.median(smr_cell[both]))
        if active.any():
            ov_pct = float(100 * np.sum(active & masker_active) / np.sum(active))
    return TargetMasking(
        masked_ratio=ratio,
        energy_masked_pct=float(100 * e_masked.sum() / total) if total > 0 else 0.0,
        median_smr_db=float(np.median(vals)) if vals.size else None,
        band_masked_energy=e_masked.sum(axis=(0, 1)),
        active_frames=int(active.sum()),
        median_smr_overlap_db=smr_ov,
        overlap_pct=ov_pct,
    )


def _top_bands(band_energy: np.ndarray, share: float = 0.8) -> list[str]:
    """Bandes qui concentrent `share` de l'énergie masquée."""
    total = band_energy.sum()
    if total <= 0:
        return []
    order = np.argsort(band_energy)[::-1]
    out, acc = [], 0.0
    for b in order:
        out.append(int(b))
        acc += band_energy[b]
        if acc >= share * total:
            break
    return [BAND_LABELS[b] for b in sorted(out)]


def analyze_masking(energies: list[np.ndarray], names: list[str], roles: list[str],
                    weights: list[float] | None = None) -> dict:
    """energies : une matrice (T, C, 24) par stem, mêmes T et C.
    weights : poids d'importance de chaque stem (STEP3B §2) ; classement = % masqué × poids de la cible."""
    n = len(energies)
    e = np.stack(energies)                                            # (S, T, C, B)
    rel = [relevance(e[i]) for i in range(n)]
    thr_each = threshold(e)                                           # seuil produit par chaque stem seul
    total = e.sum(axis=0)

    per_stem = []
    for i in range(n):
        m = mask_target(e[i], threshold(total - e[i]), rel[i])
        per_stem.append({
            "name": names[i], "role": roles[i],
            "energy_masked_pct": round(m.energy_masked_pct, 1),
            "median_smr_db": None if m.median_smr_db is None else round(m.median_smr_db, 1),
            "masked_bands": _top_bands(m.band_masked_energy),
            "masked_ratio": [None if np.isnan(v) else round(float(v), 3) for v in m.masked_ratio],
        })

    pair = np.zeros((n, n))
    detail: dict[tuple[int, int], TargetMasking] = {}
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            detail[(i, j)] = mask_target(e[i], thr_each[j], rel[i], rel[j][0])
            pair[i, j] = detail[(i, j)].energy_masked_pct

    w = np.ones(n) if weights is None else np.asarray(weights, dtype=float)
    weighted = pair * w[:, None]
    conflicts = []
    for i in range(n):
        for j in range(i + 1, n):
            victim, masker = (i, j) if weighted[i, j] >= weighted[j, i] else (j, i)
            d = detail[(victim, masker)]
            if pair[victim, masker] <= 0:
                continue
            conflicts.append({
                "score": round(float(weighted[victim, masker]), 2),
                "raw_score": round(float(pair[victim, masker]), 1),
                "victim_weight": round(float(w[victim]), 3),
                "masked": names[victim], "masked_role": roles[victim],
                "masker": names[masker], "masker_role": roles[masker],
                "energy_masked_pct": round(float(pair[victim, masker]), 1),
                "reverse_pct": round(float(pair[masker, victim]), 1),
                "bands": _top_bands(d.band_masked_energy),
                "median_smr_db": None if d.median_smr_db is None else round(d.median_smr_db, 1),
                "median_smr_overlap_db": None if d.median_smr_overlap_db is None else round(d.median_smr_overlap_db, 1),
                "overlap_pct": None if d.overlap_pct is None else round(d.overlap_pct, 1),
            })
    conflicts.sort(key=lambda c: -c["score"])
    return {"stems": per_stem, "conflicts": conflicts,
            "pair_matrix_pct": [[round(float(v), 1) for v in row] for row in pair], "names": names}


def low_envelope(x: np.ndarray, fs: int, lo: float = 30.0, hi: float = 120.0, frame_s: float = 0.01) -> np.ndarray:
    mono = x.mean(axis=1) if x.ndim == 2 else x
    y = sosfiltfilt(butter(4, [lo, hi], btype="bandpass", fs=fs, output="sos"), mono)
    hop = int(round(frame_s * fs))
    n = len(y) // hop
    return np.sqrt(np.mean(y[: n * hop].reshape(n, hop) ** 2, axis=1))


def envelope_correlation(a: np.ndarray, b: np.ndarray, fs: int) -> float | None:
    ea, eb = low_envelope(a, fs), low_envelope(b, fs)
    n = min(len(ea), len(eb))
    ea, eb = ea[:n], eb[:n]
    if ea.std() == 0 or eb.std() == 0:
        return None
    return float(np.corrcoef(ea, eb)[0, 1])
