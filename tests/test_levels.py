"""Étape 3B : tests L1-L10 de docs/STEP3B_LEVELS.md. Seuils figés : ne pas modifier."""

import time

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.features import bark_energies
from mixlab.levels import (gain_staging, importance_weight, master_chain_attribution, stem_levels,
                           third_octave_contributors)
from mixlab.masking import analyze_masking

FS = 44100


def _kick(dur=8.0, peak_db=-3.0):
    n = int(dur * FS)
    x = np.zeros(n)
    t = np.arange(int(0.15 * FS)) / FS
    hit = np.sin(2 * np.pi * (50 + 70 * np.exp(-t / 0.01)).cumsum() / FS) * np.exp(-t / 0.04)
    hit *= ts.db_to_amp(peak_db) / np.max(np.abs(hit))
    for start in np.arange(0, dur - 0.5, 0.5):
        i = int(start * FS)
        x[i:i + len(hit)] += hit
    return ts.to_stereo(x)


def _scene(dur=8.0):
    kick = _kick(dur)
    pad = ts.to_stereo(ts.pink_noise(-30, dur, FS, seed=1, f_lo=300))
    bass = ts.to_stereo(ts.sine(110, -18, dur, FS))
    return [kick, pad, bass], ["kick", "pad", "bass"]


def hard_clip(x, ceiling_db=-1.0):
    c = ts.db_to_amp(ceiling_db)
    return np.clip(x, -c, c)


# L1
def test_l1_trim_to_target():
    s = ts.to_stereo(ts.sine(100, 6.0, 1.0, FS))
    assert gain_staging(s, None, FS)["trim_to_target_db"] == pytest.approx(-12.0, abs=0.01)


# L2
def test_l2_gain_only_master():
    stems, _ = _scene()
    s = sum(stems)
    g = gain_staging(s, 0.5 * s, FS)
    assert g["crest_lost_db"] <= 0.1
    assert g["loudness_gained_lu"] == pytest.approx(-6.02, abs=0.05)


# L3 + L4
def test_l3_l4_clipper_makeup_and_attribution():
    stems, names = _scene()
    master = hard_clip(1.5 * sum(stems))
    r = master_chain_attribution(stems, names, master, FS)
    assert r["makeup_gain_db"] == pytest.approx(3.52, abs=0.5)
    kick = next(d for d in r["attribution_pct"] if d["name"] == "kick")
    assert kick["share_pct"] >= 80


# L5
def test_l5_gain_only_has_no_reduction_events():
    stems, names = _scene()
    r = master_chain_attribution(stems, names, 0.8 * sum(stems), FS)
    assert r["reduction_events_pct"] <= 1.0


# L6
def _limiter(x, thr=0.5, release_s=0.05):
    a = np.max(np.abs(x), axis=1)
    target = np.minimum(1.0, thr / np.maximum(a, 1e-12))
    coef = 1 - np.exp(-1 / (release_s * FS))
    g = np.empty_like(target)
    cur = 1.0
    for i, t in enumerate(target):
        cur = t if t < cur else cur + (1 - cur) * coef
        g[i] = cur
    return x * g[:, None], g


def test_l6_estimated_reduction_matches_true_limiter():
    stems, names = _scene(10.0)
    s = sum(stems)
    master, g = _limiter(s)
    r = master_chain_attribution(stems, names, master, FS)
    hop = int(round(0.005 * FS))
    n = (len(g) // hop) * hop
    true_red = -20 * np.log10(g[:n].reshape(-1, hop).min(axis=1))
    est = r["reduction_db_per_frame"][: len(true_red)]
    sel = true_red >= 2
    assert sel.sum() > 20
    assert np.median(np.abs(est[sel] - true_red[sel])) <= 1.0


# L7
def test_l7_third_octave_contributors():
    a = ts.to_stereo(ts.pink_noise(-20, 10, FS, seed=2, f_hi=300))
    b = ts.to_stereo(ts.pink_noise(-20, 10, FS, seed=3, f_lo=1000))
    c = third_octave_contributors([a, b], ["A", "B"], FS, [250, 2000])
    assert c[250][0]["name"] == "A" and c[250][0]["share_pct"] >= 95
    assert c[2000][0]["name"] == "B" and c[2000][0]["share_pct"] >= 95


# L8
def test_l8_importance_weight():
    assert importance_weight(-40, -5) == pytest.approx(0.0178, abs=0.0005)
    assert importance_weight(-5, -5) == 1.0
    assert importance_weight(0, -5) == 1.0


# L9
def test_l9_weighted_ranking_puts_audible_target_first():
    sig = {"M1": ts.to_stereo(ts.with_fades(ts.sine(1000, -20, 2, FS))),
           "Q": ts.to_stereo(ts.with_fades(ts.sine(1100, -50, 2, FS))),
           "M2": ts.to_stereo(ts.with_fades(ts.sine(3000, -20, 2, FS))),
           "P": ts.to_stereo(ts.with_fades(ts.sine(3300, -30, 2, FS)))}
    names = list(sig)
    levels = stem_levels(list(sig.values()), names, ["LEAD"] * 4, FS)
    mmax = {v["name"]: v["momentary_max_lufs"] for v in levels}
    w = [importance_weight(mmax[k], max(mmax.values())) for k in names]
    r = analyze_masking([bark_energies(x, FS)[0] for x in sig.values()], names, ["LEAD"] * 4, w)
    order = [c["masked"] for c in r["conflicts"]]
    assert order.index("P") < order.index("Q")


# L10
def test_l10_runtime_levels_and_masking():
    stems = [ts.to_stereo(ts.pink_noise(-26, 30.0, FS, seed=20 + k)) for k in range(16)]
    names = [f"s{k}" for k in range(16)]
    t0 = time.time()
    levels = stem_levels(stems, names, ["PAD"] * 16, FS)
    s = sum(stems)
    gain_staging(s, hard_clip(s), FS)
    master_chain_attribution(stems, names, hard_clip(s), FS)
    w = [importance_weight(v["momentary_max_lufs"], max(x["momentary_max_lufs"] for x in levels)) for v in levels]
    analyze_masking([bark_energies(x, FS)[0] for x in stems], names, ["PAD"] * 16, w)
    assert time.time() - t0 <= 60
