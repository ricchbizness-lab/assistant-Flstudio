"""Six bandes d'analyse larges, communes à la largeur stéréo et à la dynamique.

Filtrage temporel (Butterworth d'ordre 4 par bord, appliqué aller-retour : phase
nulle, pente effective de 48 dB/octave). Les bandes sont jointives. Chaque bande
est traitée puis libérée, pour borner la mémoire sur un morceau entier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np
from scipy.signal import butter, sosfiltfilt


@dataclass(frozen=True)
class Band:
    key: str
    name: str
    lo: float
    hi: float


BANDS = (
    Band("sub", "Sub", 20.0, 60.0),
    Band("bass", "Basses", 60.0, 150.0),
    Band("lowmid", "Bas-médium", 150.0, 500.0),
    Band("mid", "Médium", 500.0, 2000.0),
    Band("highmid", "Haut-médium", 2000.0, 6000.0),
    Band("air", "Air", 6000.0, 20000.0),
)


def band_sos(band: Band, fs: int) -> np.ndarray:
    hi = min(band.hi, 0.45 * fs)
    if band.hi >= 0.45 * fs:
        return butter(4, band.lo, btype="highpass", fs=fs, output="sos")
    return butter(4, [band.lo, hi], btype="bandpass", fs=fs, output="sos")


def filter_band(x: np.ndarray, fs: int, band: Band) -> np.ndarray:
    """x : (n,) ou (n, canaux). Renvoie le signal de la bande, même forme."""
    return sosfiltfilt(band_sos(band, fs), np.asarray(x, dtype=np.float64), axis=0)


def iter_bands(x: np.ndarray, fs: int) -> Iterator[tuple[Band, np.ndarray]]:
    for b in BANDS:
        yield b, filter_band(x, fs, b)
