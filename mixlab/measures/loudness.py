"""Loudness ITU-R BS.1770-4 et EBU R128 (momentané, court terme, intégré, LRA).

- Pondération K : deux biquads (shelf +4 dB vers 1,7 kHz, passe-haut ~38 Hz),
  coefficients recalculés pour toute fréquence d'échantillonnage (mêmes formules
  que ``kWeighting`` dans RicchBeatz Master, Source/Dsp.h).
- Énergies calculées par tranches de 10 ms, puis regroupées :
  * intégré : blocs de 400 ms au pas de 100 ms (grille BS.1770), porte absolue
    -70 LUFS puis porte relative -10 LU ;
  * momentané (400 ms) et court terme (3 s) : fenêtres glissantes au pas de 10 ms
    pour les maxima. Un pas de 100 ms sous-estime jusqu'à 0,2 dB un son de 400 ms
    mal aligné (EBU Tech 3341, cas 13) ;
  * LRA (EBU Tech 3342) : court terme au pas de 100 ms, portes >= -70 LUFS et
    >= -20 LU, percentiles 10 et 95 par rang (pseudo-code de la norme).
- Canaux : mono ou stéréo, pondération 1,0 par canal (somme des énergies).

Rendu : ``-inf`` quand aucun bloc ne passe les portes (silence ou signal trop court).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import sosfilt

ABS_GATE = -70.0
REL_GATE = -10.0
LRA_REL_GATE = -20.0
TICKS_PER_S = 100          # tranches de 10 ms
M_TICKS, S_TICKS, BLOCK_STEP = 40, 300, 10


def k_weighting_sos(fs: float) -> np.ndarray:
    f0, gain_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = np.tan(np.pi * f0 / fs)
    vh = 10.0 ** (gain_db / 20.0)
    vb = vh ** 0.4996667741545416
    a0 = 1.0 + k / q + k * k
    shelf = [(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0,
             1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]
    f0, q = 38.13547087602444, 0.5003270373238773
    k = np.tan(np.pi * f0 / fs)
    a0 = 1.0 + k / q + k * k
    highpass = [1.0, -2.0, 1.0, 1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0]
    return np.array([shelf, highpass])


def energy_to_lufs(e):
    e = np.asarray(e, dtype=np.float64)
    with np.errstate(divide="ignore"):
        return -0.691 + 10.0 * np.log10(e)


def _tick_energies(x: np.ndarray, fs: int) -> tuple[np.ndarray, np.ndarray]:
    """Somme des carrés pondérés K par tranche de 10 ms (canaux additionnés) et taille des tranches."""
    if x.ndim == 1:
        x = x[:, None]
    n_ticks = int(np.floor(x.shape[0] * TICKS_PER_S / fs + 1e-9))
    bounds = np.round(np.arange(n_ticks + 1) * fs / TICKS_PER_S).astype(np.int64)
    if n_ticks == 0:
        return np.zeros(0), np.zeros(0)
    sos = k_weighting_sos(fs)
    total = np.zeros(n_ticks)
    for ch in range(x.shape[1]):
        y = sosfilt(sos, x[:, ch])[: bounds[-1]]
        total += np.add.reduceat(y * y, bounds[:-1])
    return total, np.diff(bounds).astype(np.float64)


def _windows(sq: np.ndarray, sizes: np.ndarray, width: int, step: int) -> np.ndarray:
    """Énergie moyenne des fenêtres de `width` tranches, au pas de `step` tranches."""
    if len(sq) < width:
        return np.zeros(0)
    cs = np.concatenate([[0.0], np.cumsum(sq)])
    cn = np.concatenate([[0.0], np.cumsum(sizes)])
    starts = np.arange(0, len(sq) - width + 1, step)
    return (cs[starts + width] - cs[starts]) / (cn[starts + width] - cn[starts])


def _percentile_rank(sorted_vals: np.ndarray, pct: float) -> float:
    """Percentile par rang, comme le pseudo-code MATLAB de Tech 3342 : v(round((n-1)p + 1))."""
    i = int(np.floor((len(sorted_vals) - 1) * pct / 100.0 + 0.5))
    return float(sorted_vals[i])


@dataclass(frozen=True)
class Loudness:
    integrated: float
    lra: float
    momentary_max: float
    short_term_max: float
    momentary: np.ndarray      # pas de 100 ms (fenêtre 400 ms), la valeur i finit à (i*0,1 + 0,4) s
    short_term: np.ndarray     # pas de 100 ms (fenêtre 3 s), la valeur i finit à (i*0,1 + 3) s

    def summary(self) -> dict:
        r = lambda v: None if not np.isfinite(v) else round(float(v), 2)  # noqa: E731
        return {"integrated_lufs": r(self.integrated), "lra_lu": r(self.lra),
                "momentary_max_lufs": r(self.momentary_max), "short_term_max_lufs": r(self.short_term_max)}


def integrated_from_blocks(block_energy: np.ndarray) -> float:
    lufs = energy_to_lufs(block_energy)
    above = block_energy[lufs > ABS_GATE]
    if above.size == 0:
        return float("-inf")
    threshold = float(energy_to_lufs(above.mean())) + REL_GATE
    kept = block_energy[lufs > max(threshold, ABS_GATE)]
    return float(energy_to_lufs(kept.mean()))


def lra_from_short_term(st_lufs: np.ndarray) -> float:
    v = st_lufs[st_lufs >= ABS_GATE]
    if v.size == 0:
        return 0.0
    gate = float(10.0 * np.log10(np.mean(10.0 ** (v / 10.0)))) + LRA_REL_GATE
    v = np.sort(v[v >= gate])
    if v.size < 2:
        return 0.0
    return _percentile_rank(v, 95) - _percentile_rank(v, 10)


def measure_loudness(x: np.ndarray, fs: int) -> Loudness:
    sq, sizes = _tick_energies(np.asarray(x, dtype=np.float64), fs)

    blocks = _windows(sq, sizes, M_TICKS, BLOCK_STEP)
    integrated = integrated_from_blocks(blocks)

    st_100 = energy_to_lufs(_windows(sq, sizes, S_TICKS, BLOCK_STEP))
    lra = lra_from_short_term(st_100)

    m_fine = _windows(sq, sizes, M_TICKS, 1)
    s_fine = _windows(sq, sizes, S_TICKS, 1)
    mx = lambda e: float(energy_to_lufs(e.max())) if e.size else float("-inf")  # noqa: E731
    return Loudness(integrated, lra, mx(m_fine), mx(s_fine), energy_to_lufs(blocks), st_100)
