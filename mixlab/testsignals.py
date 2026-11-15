"""Signaux synthétiques de validation (règle 3 : toute mesure est validée dessus).

Convention de niveau : ``dbfs`` désigne l'amplitude crête d'un sinus
(1,0 = 0 dBFS). Un sinus à -20 dBFS a donc une crête de 0,1 et une valeur RMS
de -23,01 dB. C'est la convention des tests EBU Tech 3341 : un sinus 1 kHz à
-20 dBFS sur les deux canaux donne -20,0 LUFS.

Pour les bruits, ``rms_dbfs`` fixe la valeur RMS (20·log10 de la racine de la
moyenne des carrés).

Tous les signaux sont en float64. Mono : forme (n,). Stéréo : forme (n, 2).
"""

from __future__ import annotations

import os

import numpy as np

DEFAULT_FS = 48000


def db_to_amp(db: float) -> float:
    return float(10.0 ** (db / 20.0))


def amp_to_db(a: float) -> float:
    return float(20.0 * np.log10(max(a, 1e-300)))


def rms_db(x: np.ndarray) -> float:
    return amp_to_db(float(np.sqrt(np.mean(np.square(x, dtype=np.float64)))))


def _n(dur: float, fs: int) -> int:
    n = int(round(dur * fs))
    if n <= 0:
        raise ValueError("durée nulle")
    return n


def sine(freq: float, dbfs: float = -20.0, dur: float = 1.0, fs: int = DEFAULT_FS,
         phase: float = 0.0) -> np.ndarray:
    if not 0 < freq < fs / 2:
        raise ValueError("fréquence hors de ]0, fs/2[")
    t = np.arange(_n(dur, fs)) / fs
    return db_to_amp(dbfs) * np.sin(2 * np.pi * freq * t + phase)


def tones(components: list[tuple[float, float]], dur: float = 1.0,
          fs: int = DEFAULT_FS) -> np.ndarray:
    """Somme de sinus : components = [(fréquence, dBFS crête), ...]."""
    return np.sum([sine(f, db, dur, fs) for f, db in components], axis=0)


def intersample_sine(dur: float = 1.0, fs: int = DEFAULT_FS) -> np.ndarray:
    """Sinus à fs/4 déphasé de 45° : crête des échantillons -3,01 dBFS, crête réelle 0 dBTP."""
    return sine(fs / 4, 0.0, dur, fs, phase=np.pi / 4)


def _shaped_noise(n: int, fs: int, seed: int, exponent: float,
                  f_lo: float = 0.0, f_hi: float | None = None) -> np.ndarray:
    """Bruit dont la densité spectrale de puissance suit f^-exponent (0 blanc, 1 rose),
    limité à la bande [f_lo, f_hi] (coupure franche dans le domaine fréquentiel)."""
    rng = np.random.default_rng(seed)
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    f = np.fft.rfftfreq(n, 1.0 / fs)
    gain = np.zeros_like(f)
    gain[1:] = f[1:] ** (-exponent / 2.0)
    gain[f < f_lo] = 0.0
    if f_hi is not None:
        gain[f > f_hi] = 0.0
    x = np.fft.irfft(spec * gain, n)
    return x


def _normalize_rms(x: np.ndarray, rms_dbfs: float) -> np.ndarray:
    return x * (db_to_amp(rms_dbfs) / np.sqrt(np.mean(x * x)))


def white_noise(rms_dbfs: float = -20.0, dur: float = 1.0, fs: int = DEFAULT_FS,
                seed: int = 0) -> np.ndarray:
    return _normalize_rms(_shaped_noise(_n(dur, fs), fs, seed, 0.0), rms_dbfs)


def pink_noise(rms_dbfs: float = -20.0, dur: float = 1.0, fs: int = DEFAULT_FS,
               seed: int = 0, f_lo: float = 20.0, f_hi: float = 20000.0) -> np.ndarray:
    """Bruit rose : énergie égale par octave (-3 dB/octave en densité).

    Limité par défaut à 20 Hz - 20 kHz : sans cette limite, l'énergie infrasonore
    (jusqu'à 1/durée Hz) dominerait le RMS et fausserait toute comparaison avec
    une mesure pondérée (LUFS, bandes).
    """
    return _normalize_rms(_shaped_noise(_n(dur, fs), fs, seed, 1.0, f_lo, min(f_hi, fs / 2)), rms_dbfs)


def with_fades(x: np.ndarray, fs: int = DEFAULT_FS, ms: float = 10.0) -> np.ndarray:
    """Fondus d'entrée et de sortie en sinus carré. Sans eux, un signal qui démarre
    brutalement produit un vrai dépassement inter-échantillons au premier échantillon
    (environ +0,1 dB sur le sinus à fs/4), qui fausserait les tests de true-peak."""
    n = int(round(fs * ms / 1000.0))
    if n == 0 or 2 * n > x.shape[0]:
        return x.copy()
    ramp = np.sin(np.linspace(0.0, np.pi / 2, n)) ** 2
    env = np.ones(x.shape[0])
    env[:n], env[-n:] = ramp, ramp[::-1]
    return x * (env[:, None] if x.ndim == 2 else env)


def stereo(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    if left.shape != right.shape or left.ndim != 1:
        raise ValueError("deux signaux mono de même longueur attendus")
    return np.stack([left, right], axis=1)


def to_stereo(x: np.ndarray, mode: str = "dual") -> np.ndarray:
    """dual : L = R ; left : signal à gauche seulement ; inverted : R = -L."""
    if mode == "dual":
        return stereo(x, x.copy())
    if mode == "left":
        return stereo(x, np.zeros_like(x))
    if mode == "inverted":
        return stereo(x, -x)
    raise ValueError(f"mode inconnu : {mode}")


def write_wav(path: str | os.PathLike, x: np.ndarray, fs: int = DEFAULT_FS,
              subtype: str = "FLOAT") -> None:
    import soundfile as sf

    if subtype != "FLOAT" and np.max(np.abs(x)) > 1.0:
        raise ValueError("écrêtage : crête > 0 dBFS en format entier")
    sf.write(os.fspath(path), x, fs, subtype=subtype)
