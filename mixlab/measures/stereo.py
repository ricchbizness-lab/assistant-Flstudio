"""Image stéréo : corrélation, part d'énergie sur les côtés, perte en mono, balance.

Définitions (sommes sur les échantillons, M = (L+R)/2, S = (L-R)/2) :
- correlation : ΣLR / sqrt(ΣL² ΣR²), de -1 (opposition de phase) à +1 (mono).
  Indéfinie si un canal est muet : renvoyée à None.
- side_pct : 100·ΣS² / (ΣM² + ΣS²). 0 % = mono, 50 % = canaux indépendants,
  100 % = opposition de phase.
- mono_loss_db : 10·log10(ΣM² / ((ΣL² + ΣR²)/2)). Ce que perd le signal quand
  il est sommé en mono : 0 dB pour du mono, -3 dB pour des canaux indépendants,
  -inf en opposition de phase. Mesure clé sous 150 Hz (sub et basses).
- balance_db : 10·log10(ΣL² / ΣR²), positif = penche à gauche.
"""

from __future__ import annotations

import numpy as np

from ..bands import iter_bands

SILENCE = 1e-20


def _db(v: float) -> float | None:
    if v <= 0:
        return None if v == 0 else float("-inf")
    return float(10 * np.log10(v))


def stereo_stats(x: np.ndarray) -> dict:
    x = np.asarray(x, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != 2:
        return {"stereo": False}
    left, right = x[:, 0], x[:, 1]
    ll, rr, lr = float(left @ left), float(right @ right), float(left @ right)
    mm = (ll + rr + 2 * lr) / 4
    ss = (ll + rr - 2 * lr) / 4
    if ll + rr < SILENCE:
        return {"stereo": True, "silent": True}
    one_sided = min(ll, rr) < SILENCE
    mono_loss = mm / ((ll + rr) / 2)
    return {
        "stereo": True,
        "correlation": None if one_sided else round(float(lr / np.sqrt(ll * rr)), 3),
        "side_pct": round(100 * ss / (mm + ss), 1),
        "mono_loss_db": None if mono_loss <= 0 else round(_db(mono_loss), 2),
        "balance_db": None if one_sided else round(_db(ll / rr), 2),
        "one_sided": one_sided,
    }


def stereo_profile(x: np.ndarray, fs: int) -> dict:
    """Mesures globales et par bande."""
    out = {"global": stereo_stats(x), "bands": {}}
    if not out["global"].get("stereo"):
        return out
    for band, xb in iter_bands(x, fs):
        out["bands"][band.key] = {"name": band.name, "lo_hz": band.lo, "hi_hz": band.hi, **stereo_stats(xb)}
    return out
