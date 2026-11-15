"""Spectre moyen long terme par bandes (tiers d'octave et Bark).

Niveau d'une bande = 10·log10(énergie moyenne du signal dans la bande), en dB
relatif à la pleine échelle. Un sinus de crête A placé dans une bande y vaut
20·log10(A) - 3,01 dB. En stéréo, on prend la moyenne des puissances L et R.

Densité spectrale : Welch, fenêtre de Hann, segments d'environ 0,68 s (2^15 à
48 kHz), 50 % de recouvrement. L'énergie d'une bande intègre chaque case FFT au
prorata de son recouvrement avec la bande (pas d'effet d'escalier aux bords).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import welch

# Tiers d'octave, base 10 (IEC 61260) : fc = 1000·10^(k/10), 20 Hz .. 20 kHz
THIRD_OCTAVE_CENTERS = 1000.0 * 10.0 ** (np.arange(-17, 14) / 10.0)
NOMINAL_THIRD_OCTAVE = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000,
                        1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000]

# Bandes critiques de Zwicker (24 bandes Bark), bornes en Hz
BARK_EDGES = np.array([20, 100, 200, 300, 400, 510, 630, 770, 920, 1080, 1270, 1480, 1720, 2000, 2320, 2700,
                       3150, 3700, 4400, 5300, 6400, 7700, 9500, 12000, 15500], dtype=float)


def third_octave_edges() -> tuple[np.ndarray, np.ndarray]:
    return THIRD_OCTAVE_CENTERS * 10 ** (-1 / 20), THIRD_OCTAVE_CENTERS * 10 ** (1 / 20)


def hz_to_bark(f):
    """Formule de Zwicker & Terhardt."""
    f = np.asarray(f, dtype=float)
    return 13.0 * np.arctan(0.00076 * f) + 3.5 * np.arctan((f / 7500.0) ** 2)


def bark_band_index(freq: float) -> int:
    """Indice (0..23) de la bande critique contenant freq, -1 si hors bornes."""
    i = int(np.searchsorted(BARK_EDGES, freq, side="right")) - 1
    return i if 0 <= i < len(BARK_EDGES) - 1 else -1


def psd(x: np.ndarray, fs: int, nperseg: int | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Densité spectrale de puissance unilatérale, moyennée sur les canaux."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if nperseg is None:
        nperseg = 1 << int(round(np.log2(fs * 0.6826)))
    nperseg = min(nperseg, x.shape[0])
    f, p = welch(x, fs=fs, window="hann", nperseg=nperseg, noverlap=nperseg // 2, axis=0,
                 detrend=False, scaling="density")
    return f, p.mean(axis=1)


def band_energies(f: np.ndarray, p: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Intègre la DSP sur chaque bande [lo, hi[ avec recouvrement fractionnaire des cases."""
    df = f[1] - f[0]
    b_lo = np.maximum(f - df / 2, 0.0)
    b_hi = f + df / 2
    out = np.empty(len(lo))
    for i, (a, b) in enumerate(zip(lo, hi)):
        overlap = np.clip(np.minimum(b_hi, b) - np.maximum(b_lo, a), 0.0, None)
        out[i] = np.sum(p * overlap)
    return out


def _db(e: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore"):
        return 10.0 * np.log10(e)


@dataclass(frozen=True)
class BandSpectrum:
    centers: np.ndarray   # Hz
    lo: np.ndarray
    hi: np.ndarray
    level_db: np.ndarray  # dB pleine échelle (énergie moyenne)

    def to_dict(self, nominal: list | None = None) -> list[dict]:
        names = nominal if nominal is not None else [round(float(c), 1) for c in self.centers]
        return [{"band_hz": n, "lo_hz": round(float(a), 1), "hi_hz": round(float(b), 1),
                 "level_db": None if not np.isfinite(v) else round(float(v), 2)}
                for n, a, b, v in zip(names, self.lo, self.hi, self.level_db)]


def third_octave_spectrum(x: np.ndarray, fs: int) -> BandSpectrum:
    f, p = psd(x, fs)
    lo, hi = third_octave_edges()
    hi = np.minimum(hi, fs / 2)
    return BandSpectrum(THIRD_OCTAVE_CENTERS, lo, hi, _db(band_energies(f, p, lo, hi)))


def bark_spectrum(x: np.ndarray, fs: int) -> BandSpectrum:
    f, p = psd(x, fs)
    lo, hi = BARK_EDGES[:-1], np.minimum(BARK_EDGES[1:], fs / 2)
    return BandSpectrum(np.sqrt(lo * hi), lo, hi, _db(band_energies(f, p, lo, hi)))
