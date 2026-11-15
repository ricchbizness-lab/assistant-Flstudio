"""Équilibre tonal et mud.

1. Pente spectrale : droite ajustée (moindres carrés) sur le spectre en tiers
   d'octave, en dB par octave, sur les bandes de 80-140 Hz et 700 Hz-10 kHz
   (la zone du mud est exclue pour ne pas biaiser la référence). Bruit rose : 0.
2. mud_excess_db : écart moyen des bandes 200-500 Hz au-dessus de cette pente.
   Indicateur sans référence, utile en absolu mais peu fiable sur les styles très
   chargés en sub (la pente est alors tirée par le grave).
3. Comparaison aux références (``compare_to_references``) : chaque spectre est
   d'abord ramené à 0 LUFS intégré (niveau de bande - LUFS intégré du fichier),
   puis on calcule l'écart du mix à la moyenne des références, bande par bande,
   avec l'étendue min/max des références. C'est la mesure à privilégier.
"""

from __future__ import annotations

import numpy as np

from .spectrum import NOMINAL_THIRD_OCTAVE, THIRD_OCTAVE_CENTERS, BandSpectrum

TREND_RANGES = ((80.0, 140.0), (700.0, 10000.0))
MUD_RANGE = (200.0, 500.0)
COMPARE_RANGE = (25.0, 16000.0)


def _mask(lo: float, hi: float) -> np.ndarray:
    return (THIRD_OCTAVE_CENTERS >= lo * 0.99) & (THIRD_OCTAVE_CENTERS <= hi * 1.01)


def spectral_trend(spec: BandSpectrum) -> tuple[float, float]:
    """(pente en dB/octave, ordonnée à 1 kHz)."""
    sel = np.zeros_like(THIRD_OCTAVE_CENTERS, dtype=bool)
    for lo, hi in TREND_RANGES:
        sel |= _mask(lo, hi)
    sel &= np.isfinite(spec.level_db)
    octaves = np.log2(THIRD_OCTAVE_CENTERS[sel] / 1000.0)
    slope, intercept = np.polyfit(octaves, spec.level_db[sel], 1)
    return float(slope), float(intercept)


def mud_profile(spec: BandSpectrum) -> dict:
    slope, intercept = spectral_trend(spec)
    trend = intercept + slope * np.log2(THIRD_OCTAVE_CENTERS / 1000.0)
    sel = _mask(*MUD_RANGE)
    dev = spec.level_db[sel] - trend[sel]
    return {
        "tilt_db_per_octave": round(slope, 2),
        "mud_excess_db": round(float(np.mean(dev)), 2),
        "mud_bands": [{"band_hz": n, "above_trend_db": round(float(d), 2)}
                      for n, d in zip(np.array(NOMINAL_THIRD_OCTAVE, dtype=object)[sel], dev)],
    }


def normalized_levels(spec: BandSpectrum, integrated_lufs: float) -> np.ndarray:
    """Niveaux de bande ramenés à un loudness intégré de 0 LUFS."""
    return spec.level_db - integrated_lufs


def compare_to_references(mix: tuple[BandSpectrum, float], refs: list[tuple[str, BandSpectrum, float]]) -> dict:
    """mix = (spectre, LUFS intégré) ; refs = [(nom, spectre, LUFS intégré)]. Normalisation du loudness d'abord."""
    if not refs:
        return {}
    m = normalized_levels(*mix)
    r = np.array([normalized_levels(s, lufs) for _, s, lufs in refs])
    mean, lo, hi = r.mean(axis=0), r.min(axis=0), r.max(axis=0)
    sel = _mask(*COMPARE_RANGE)
    bands = []
    for i in np.flatnonzero(sel):
        d = m[i] - mean[i]
        bands.append({
            "band_hz": NOMINAL_THIRD_OCTAVE[i],
            "mix_db": round(float(m[i]), 2),
            "refs_mean_db": round(float(mean[i]), 2),
            "delta_db": round(float(d), 2),
            "refs_min_db": round(float(lo[i]), 2),
            "refs_max_db": round(float(hi[i]), 2),
            # l'étendue des références n'a de sens qu'avec au moins deux références
            "outside_refs": bool(m[i] < lo[i] or m[i] > hi[i]) if len(refs) >= 2 else None,
        })
    mud = [b["delta_db"] for b in bands if MUD_RANGE[0] * 0.99 <= b["band_hz"] <= MUD_RANGE[1] * 1.01]
    return {
        "normalization": "chaque spectre ramené à 0 LUFS intégré avant comparaison",
        "references": [name for name, _, _ in refs],
        "mud_vs_refs_db": round(float(np.mean(mud)), 2),
        "bands": bands,
    }
