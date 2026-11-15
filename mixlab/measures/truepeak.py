"""True-peak (dBTP) : suréchantillonnage x4 par sinc fenêtré Kaiser (beta 7,5, ±16 échantillons).

Même filtre que ``TruePeakTable`` de RicchBeatz Master (Source/Dsp.h), validé là-bas
contre ``ffmpeg ebur128=peak=true``. Les échantillons d'origine sont conservés à
l'identique (phase 0 du filtre = impulsion unité). Traitement par blocs pour
borner la mémoire sur un morceau entier.
"""

from __future__ import annotations

import numpy as np
from scipy.signal import upfirdn

UP = 4
HALF_SPAN = 16           # demi-largeur du noyau, en échantillons d'origine
BETA = 7.5
BLOCK = 1 << 18


def _kernel() -> np.ndarray:
    t = np.arange(-HALF_SPAN * UP, HALF_SPAN * UP + 1) / UP
    w = np.kaiser(len(t), BETA)
    return np.sinc(t) * w


_H = _kernel()
_DELAY = HALF_SPAN * UP  # retard du filtre, en échantillons suréchantillonnés


def upsample4(x: np.ndarray) -> np.ndarray:
    """Signal mono suréchantillonné x4, aligné : y[4n] == x[n]."""
    y = upfirdn(_H, np.asarray(x, dtype=np.float64), up=UP)
    return y[_DELAY:_DELAY + UP * len(x)]


def true_peak_linear(x: np.ndarray) -> float:
    """Crête réelle (linéaire), tous canaux confondus."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    n = x.shape[0]
    for ch in range(x.shape[1]):
        s = x[:, ch]
        for start in range(0, n, BLOCK):
            lo = max(0, start - HALF_SPAN)
            hi = min(n, start + BLOCK + HALF_SPAN)
            y = upsample4(s[lo:hi])
            core = y[(start - lo) * UP:(start - lo + min(BLOCK, n - start)) * UP]
            if core.size:
                peak = max(peak, float(np.max(np.abs(core))))
    return peak


def to_db(a: float) -> float:
    return float(20.0 * np.log10(a)) if a > 0 else float("-inf")


def true_peak_dbtp(x: np.ndarray) -> float:
    return to_db(true_peak_linear(x))


def sample_peak_dbfs(x: np.ndarray) -> float:
    x = np.asarray(x)
    return to_db(float(np.max(np.abs(x)))) if x.size else float("-inf")
