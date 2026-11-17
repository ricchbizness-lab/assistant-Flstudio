"""Trames de caractéristiques : énergie par bande Bark, par canal, toutes les ~23 ms.

C'est la représentation commune au mode fichier (Phase A) et au futur mode flux
(sondes VST3, Phase B) : le masquage ne travaille que sur ces énergies.

Paramètres (figés dans docs/STEP3_THRESHOLDS.md, §1) :
- pas = puissance de 2 la plus proche de 23,2 ms (1024 à 44,1 et 48 kHz) ;
- fenêtre de Hann de 4 x le pas pour les bandes dont la borne haute ≤ 510 Hz
  (résolution fréquentielle dans le grave), de 1 x le pas au-dessus (résolution
  temporelle) ; trames centrées sur k·pas ;
- énergie normalisée en carré moyen : un sinus de crête A donne A²/2 dans sa bande.
"""

from __future__ import annotations

import numpy as np

from .measures.spectrum import BARK_EDGES

LOW_SPLIT_HZ = 510.0


def hop_for(fs: int) -> int:
    return 1 << int(round(np.log2(fs * 0.0232)))


def _frames(x: np.ndarray, win: int, hop: int, n_frames: int) -> np.ndarray:
    """Trames centrées (n_frames, win) d'un signal mono, complété par des zéros."""
    pad = win // 2
    xp = np.concatenate([np.zeros(pad), x, np.zeros(pad + win)])
    idx = np.arange(n_frames)[:, None] * hop + np.arange(win)[None, :]
    return xp[idx]


def _band_energy(x: np.ndarray, fs: int, win: int, hop: int, n_frames: int, bands: np.ndarray) -> np.ndarray:
    w = np.hanning(win + 1)[:-1]                       # Hann périodique
    spec = np.abs(np.fft.rfft(_frames(x, win, hop, n_frames) * w, axis=1)) ** 2
    spec[:, 1:-1] *= 2.0                               # spectre unilatéral
    spec /= win * np.sum(w * w)                        # -> carré moyen
    f = np.fft.rfftfreq(win, 1.0 / fs)
    idx = np.searchsorted(BARK_EDGES, f, side="right") - 1
    out = np.zeros((n_frames, len(bands)))
    for k, b in enumerate(bands):
        sel = idx == b
        if sel.any():
            out[:, k] = spec[:, sel].sum(axis=1)
    return out


def bark_energies(x: np.ndarray, fs: int) -> tuple[np.ndarray, float]:
    """Renvoie (énergies de forme (trames, canaux, 24), pas en secondes)."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    hop = hop_for(fs)
    n_frames = 1 + x.shape[0] // hop
    n_bands = len(BARK_EDGES) - 1
    low = np.array([b for b in range(n_bands) if BARK_EDGES[b + 1] <= LOW_SPLIT_HZ])
    high = np.array([b for b in range(n_bands) if BARK_EDGES[b + 1] > LOW_SPLIT_HZ])
    out = np.zeros((n_frames, x.shape[1], n_bands))
    for c in range(x.shape[1]):
        out[:, c, low] = _band_energy(x[:, c], fs, 4 * hop, hop, n_frames, low)
        out[:, c, high] = _band_energy(x[:, c], fs, hop, hop, n_frames, high)
    return out, hop / fs
