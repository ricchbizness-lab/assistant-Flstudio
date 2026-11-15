"""Dynamique : facteur de crête global et par bande, PLR, PSR.

- crest_db : crête des échantillons - RMS (dB), tous canaux. Sinus : 3,01 dB.
  Un mix très compressé ou écrêté a un facteur de crête faible.
- Par bande : même calcul sur le signal filtré. Dans le sub et les basses, il
  renseigne sur l'impact des kicks et des attaques de 808 (crête élevée =
  transitoires préservés).
- plr_db : true-peak - LUFS intégré. psr_db : true-peak - court terme maximal.
"""

from __future__ import annotations

import numpy as np

from ..bands import iter_bands
from .loudness import Loudness


def crest_db(x: np.ndarray) -> float | None:
    x = np.asarray(x, dtype=np.float64)
    ms = float(np.mean(x * x))
    if ms <= 0:
        return None
    return float(20 * np.log10(np.max(np.abs(x))) - 10 * np.log10(ms))


def dynamics_profile(x: np.ndarray, fs: int, loud: Loudness, true_peak_dbtp: float) -> dict:
    r = lambda v: None if v is None or not np.isfinite(v) else round(float(v), 2)  # noqa: E731
    out = {
        "crest_db": r(crest_db(x)),
        "plr_db": r(true_peak_dbtp - loud.integrated),
        "psr_db": r(true_peak_dbtp - loud.short_term_max),
        "lra_lu": r(loud.lra),
        "bands": {},
    }
    for band, xb in iter_bands(x, fs):
        ms = float(np.mean(xb * xb))
        out["bands"][band.key] = {
            "name": band.name,
            "rms_db": r(10 * np.log10(ms)) if ms > 0 else None,
            "crest_db": r(crest_db(xb)),
        }
    return out
