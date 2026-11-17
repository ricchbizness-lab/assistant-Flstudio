"""Équilibre des niveaux, gain staging et effet de la chaîne Master (docs/STEP3B_LEVELS.md, figé).

Tout est mesuré, rien n'est recommandé ici : les corrections chiffrées viennent de
l'étape 4. Les stems sont supposés alignés entre eux (export « Split mixer tracks »).
"""

from __future__ import annotations

import numpy as np

from .bands import BANDS, filter_band
from .measures.dynamics import crest_db
from .measures.loudness import measure_loudness
from .measures.spectrum import NOMINAL_THIRD_OCTAVE, band_energies, psd, third_octave_edges
from .measures.truepeak import sample_peak_dbfs, true_peak_dbtp

TARGET_SUM_PEAK_DBFS = -6.0
FRAME_S = 0.005
REDUCTION_EVENT_DB = 1.0
SILENT_PEAK = 1e-4


def _db(v: float) -> float | None:
    return None if v is None or not np.isfinite(v) else round(float(v), 2)


def importance_weight(m_max_target: float, m_max_loudest: float) -> float:
    """Poids d'importance (STEP3B §2) : rapport d'amplitude des loudness momentanés max, borné à [0, 1]."""
    if not np.isfinite(m_max_target) or not np.isfinite(m_max_loudest):
        return 0.0
    return float(min(1.0, max(0.0, 10 ** ((m_max_target - m_max_loudest) / 20))))


def stem_levels(signals: list[np.ndarray], names: list[str], roles: list[str], fs: int) -> list[dict]:
    rows = []
    band_e = np.array([[float(np.sum(filter_band(x, fs, b) ** 2)) for b in BANDS] for x in signals])
    totals = band_e.sum(axis=0)
    for k, x in enumerate(signals):
        lo = measure_loudness(x, fs)
        rows.append({
            "name": names[k], "role": roles[k],
            "integrated_lufs": _db(lo.integrated), "momentary_max_lufs": _db(lo.momentary_max),
            "sample_peak_dbfs": _db(sample_peak_dbfs(x)), "crest_db": _db(crest_db(x)),
            "band_share_pct": {b.key: (round(100 * band_e[k, i] / totals[i], 1) if totals[i] > 0 else None)
                               for i, b in enumerate(BANDS)},
        })
    return rows


def third_octave_contributors(signals: list[np.ndarray], names: list[str], fs: int,
                              bands_hz: list[float], top: int = 3) -> dict:
    """Pour chaque tiers d'octave demandé : stems qui y apportent le plus d'énergie (%)."""
    lo, hi = third_octave_edges()
    energies = []
    for x in signals:
        f, p = psd(x, fs)
        energies.append(band_energies(f, p, lo, np.minimum(hi, fs / 2)))
    e = np.array(energies)
    out = {}
    for hz in bands_hz:
        i = NOMINAL_THIRD_OCTAVE.index(hz)
        tot = e[:, i].sum()
        if tot <= 0:
            continue
        order = np.argsort(e[:, i])[::-1][:top]
        out[hz] = [{"name": names[k], "share_pct": round(float(100 * e[k, i] / tot), 1)} for k in order]
    return out


def gain_staging(stem_sum: np.ndarray, master: np.ndarray | None, fs: int) -> dict:
    sp = sample_peak_dbfs(stem_sum)
    out = {"sum_peak_dbfs": _db(sp), "sum_true_peak_dbtp": _db(true_peak_dbtp(stem_sum)),
           "sum_crest_db": _db(crest_db(stem_sum)),
           "sum_lufs": _db(measure_loudness(stem_sum, fs).integrated),
           "trim_to_target_db": _db(TARGET_SUM_PEAK_DBFS - sp), "target_sum_peak_dbfs": TARGET_SUM_PEAK_DBFS}
    if master is not None:
        ml = measure_loudness(master, fs).integrated
        out.update({"master_peak_dbfs": _db(sample_peak_dbfs(master)),
                    "master_true_peak_dbtp": _db(true_peak_dbtp(master)),
                    "master_crest_db": _db(crest_db(master)), "master_lufs": _db(ml),
                    "crest_lost_db": _db(crest_db(stem_sum) - crest_db(master)),
                    "loudness_gained_lu": _db(ml - measure_loudness(stem_sum, fs).integrated)})
    return out


def _frame_peaks(x: np.ndarray, hop: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Par trame : crête (tous canaux), indice de l'échantillon et canal de cette crête."""
    n = (x.shape[0] // hop) * hop
    a = np.abs(x[:n]).reshape(-1, hop, x.shape[1])
    flat = a.reshape(a.shape[0], -1)
    arg = np.argmax(flat, axis=1)
    peaks = flat[np.arange(len(arg)), arg]
    idx = np.arange(len(arg)) * hop + arg // x.shape[1]
    ch = arg % x.shape[1]
    return peaks, idx, ch


def master_chain_attribution(stems: list[np.ndarray], names: list[str], master_aligned: np.ndarray, fs: int) -> dict:
    """Réduction de crête appliquée par la chaîne Master, et part de chaque stem (STEP3B §1).
    `master_aligned` doit déjà être aligné sur la somme et de même longueur."""
    s = sum(stems)
    n = min(len(s), len(master_aligned))
    s, m = s[:n], master_aligned[:n]
    hop = max(1, int(round(FRAME_S * fs)))
    ps, idx, ch = _frame_peaks(s, hop)
    pm, _, _ = _frame_peaks(m, hop)
    live = ps > SILENT_PEAK
    if live.sum() < 10:
        return {"makeup_gain_db": None, "frames": 0}
    lo, hi = np.percentile(ps[live], [10, 50])
    calm = live & (ps >= lo) & (ps <= hi) & (pm > 0)
    g = float(np.median(pm[calm] / ps[calm]))
    red = np.zeros_like(ps)
    ok = live & (pm > SILENT_PEAK)          # Master quasi muet (bords, fondus) : trame ignorée
    red[ok] = 20 * np.log10(g * ps[ok] / pm[ok])
    events = ok & (red > REDUCTION_EVENT_DB)
    weights = np.zeros(len(stems))
    for f in np.flatnonzero(events):
        i, c = idx[f], ch[f]
        sign = np.sign(s[i, c])
        contrib = np.array([max(0.0, float(x[i, c]) * sign) for x in stems])
        tot = contrib.sum()
        if tot > 0:
            weights += red[f] * contrib / tot
    total = weights.sum()
    return {
        "makeup_gain_db": round(20 * np.log10(g), 2),
        "frames": int(live.sum()),
        "reduction_events_pct": round(float(100 * events.sum() / live.sum()), 2),
        "reduction_over_3db_pct": round(float(100 * np.sum(ok & (red > 3)) / live.sum()), 2),
        "max_reduction_db": round(float(red[ok].max()), 2) if ok.any() else None,
        "attribution_pct": sorted(({"name": names[k], "share_pct": round(float(100 * weights[k] / total), 1)}
                                   for k in range(len(stems)) if total > 0 and weights[k] > 0),
                                  key=lambda d: -d["share_pct"]),
        "reduction_db_per_frame": red,   # retiré de la sortie JSON par l'appelant
    }
