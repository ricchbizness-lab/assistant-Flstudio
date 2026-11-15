"""Mesures de base d'un fichier : format, crêtes, RMS, loudness, true-peak, PLR, spectre."""

from __future__ import annotations

import os

import numpy as np

from .. import __version__
from ..audio import load
from .loudness import measure_loudness
from .spectrum import NOMINAL_THIRD_OCTAVE, third_octave_spectrum
from .truepeak import sample_peak_dbfs, true_peak_dbtp


def _r(v: float, nd: int = 2):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def measure_signal(x: np.ndarray, fs: int) -> dict:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    loud = measure_loudness(x, fs)
    tp = true_peak_dbtp(x)
    with np.errstate(divide="ignore"):
        rms = 10 * np.log10(np.mean(x ** 2, axis=0))
    out = {
        "sample_peak_dbfs": _r(sample_peak_dbfs(x)),
        "sample_peak_per_channel_dbfs": [_r(sample_peak_dbfs(x[:, c])) for c in range(x.shape[1])],
        "true_peak_dbtp": _r(tp),
        "rms_per_channel_dbfs": [_r(v) for v in rms],
        **loud.summary(),
        "plr_db": _r(tp - loud.integrated) if np.isfinite(loud.integrated) else None,
        "third_octave": third_octave_spectrum(x, fs).to_dict(NOMINAL_THIRD_OCTAVE),
    }
    return out


def measure_file(path: str | os.PathLike) -> dict:
    x, info = load(path)
    return {"mixlab_version": __version__, "file": info.to_dict(), "measures": measure_signal(x, info.sample_rate)}


def format_summary(result: dict) -> str:
    f, m = result["file"], result["measures"]
    fmt = lambda v, u: "n/a" if v is None else f"{v:.1f} {u}"  # noqa: E731
    lines = [
        f"Fichier         {os.path.basename(f['path'])}",
        f"Format          {f['label']} · {f['channels']} canal(aux) · {f['duration_s']:.1f} s",
        f"LUFS intégré    {fmt(m['integrated_lufs'], 'LUFS')}",
        f"LRA             {fmt(m['lra_lu'], 'LU')}",
        f"Momentané max   {fmt(m['momentary_max_lufs'], 'LUFS')}",
        f"Court terme max {fmt(m['short_term_max_lufs'], 'LUFS')}",
        f"True-peak       {fmt(m['true_peak_dbtp'], 'dBTP')}",
        f"Crête éch.      {fmt(m['sample_peak_dbfs'], 'dBFS')}",
        f"PLR             {fmt(m['plr_db'], 'dB')}",
    ]
    return "\n".join(lines)
