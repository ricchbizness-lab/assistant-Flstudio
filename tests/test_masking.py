"""Étape 3 : tests T1-T10 de docs/STEP3_THRESHOLDS.md. Seuils figés : ne pas modifier."""

import time

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.features import bark_energies
from mixlab.masking import analyze_masking, envelope_correlation, mask_target, threshold
from mixlab.measures.spectrum import bark_band_index
from mixlab.stems import align, detect_buses

FS = 44100


def tone(f, db, dur=2.0, mode="dual"):
    return ts.to_stereo(ts.with_fades(ts.sine(f, db, dur, FS), FS), mode)


def target_vs_masker(target, masker):
    et, _ = bark_energies(target, FS)
    em, _ = bark_energies(masker, FS)
    return mask_target(et, threshold(em))


def band_of(f):
    return bark_band_index(f)


# T1
def test_t1_close_tone_is_masked():
    m = target_vs_masker(tone(1100, -40), tone(1000, -20))
    b = band_of(1100)
    assert m.masked_ratio[b] >= 0.9
    assert m.median_smr_db <= -6


# T2
def test_t2_distant_tone_is_not_masked():
    m = target_vs_masker(tone(4000, -40), tone(1000, -20))
    assert m.masked_ratio[band_of(4000)] <= 0.05


# T3
def test_t3_upward_spread_asymmetry():
    up = target_vs_masker(tone(700, -45), tone(500, -20))
    down = target_vs_masker(tone(500, -45), tone(700, -20))
    assert up.masked_ratio[band_of(700)] >= 0.9                    # T3a
    assert down.masked_ratio[band_of(500)] <= 0.1                  # T3b
    assert down.median_smr_db - up.median_smr_db >= 8              # T3c


# T4
def _hits(kind, offset_s, dur=8.0):
    n = int(dur * FS)
    x = np.zeros(n)
    if kind == "kick":
        t = np.arange(int(0.18 * FS)) / FS
        f = 50 + 70 * np.exp(-t / 0.01)                            # balayage 120 -> 50 Hz
        hit = np.sin(2 * np.pi * np.cumsum(f) / FS) * np.exp(-t / 0.03) * ts.db_to_amp(-14)
    else:
        t = np.arange(int(0.22 * FS)) / FS
        hit = np.sin(2 * np.pi * 45 * t) * np.exp(-t / 0.06) * ts.db_to_amp(-2)
    for start in np.arange(offset_s, dur - 0.5, 0.5):
        i = int(start * FS)
        x[i:i + len(hit)] += hit
    return ts.to_stereo(x)


def test_t4a_alternating_kick_and_808_do_not_mask():
    kick, bass = _hits("kick", 0.0), _hits("808", 0.25)
    m = target_vs_masker(kick, bass)
    assert m.masked_ratio[0] <= 0.1
    assert envelope_correlation(kick, bass, FS) <= 0.2


def test_t4b_simultaneous_kick_and_808_mask():
    kick, bass = _hits("kick", 0.0), _hits("808", 0.0)
    m = target_vs_masker(kick, bass)
    assert m.masked_ratio[0] >= 0.6
    assert envelope_correlation(kick, bass, FS) >= 0.7


# T5
def test_t5a_hard_panning_unmasks():
    m = target_vs_masker(tone(1100, -40, mode="dual") * np.array([0.0, 1.0]),
                         tone(1000, -20, mode="dual") * np.array([1.0, 0.0]))
    assert m.masked_ratio[band_of(1100)] <= 0.1


def test_t5b_centered_control_matches_t1():
    m = target_vs_masker(tone(1100, -40), tone(1000, -20))
    assert m.masked_ratio[band_of(1100)] >= 0.9 and m.median_smr_db <= -6


# T6
def test_t6_tone_above_pink_noise_is_not_masked():
    noise = ts.to_stereo(ts.pink_noise(-20, 2.0, FS, seed=1))
    m = target_vs_masker(tone(1000, -20), noise)
    assert m.masked_ratio[band_of(1000)] <= 0.1


# T7
def test_t7_bus_detection():
    a = ts.to_stereo(ts.pink_noise(-20, 5.0, FS, seed=2))
    b = ts.to_stereo(ts.pink_noise(-20, 5.0, FS, seed=3))
    assert detect_buses([a, b, a + b]) == [2]


# T8
def test_t8_alignment_with_master():
    s = ts.to_stereo(ts.pink_noise(-20, 12.0, FS, seed=4))
    master = np.concatenate([np.zeros((86, 2)), s[:-86]])
    r = align(master, s, FS)
    assert abs(r["lag_samples"] - 86) <= 1
    assert r["difference_db"] <= -60


# T9
def test_t9_runtime_16_stems_30s():
    stems = [ts.to_stereo(ts.pink_noise(-20, 30.0, FS, seed=10 + k)) for k in range(16)]
    t0 = time.time()
    energies = [bark_energies(x, FS)[0] for x in stems]
    analyze_masking(energies, [f"s{k}" for k in range(16)], ["PAD"] * 16)
    assert time.time() - t0 <= 60


# T10
def test_t10_pair_score_independent_of_order():
    a, b, c = tone(1100, -40), tone(1000, -20), tone(4000, -30)
    ea, eb, ec = (bark_energies(x, FS)[0] for x in (a, b, c))
    r1 = analyze_masking([ea, eb, ec], ["a", "b", "c"], ["LEAD"] * 3)
    r2 = analyze_masking([ec, eb, ea], ["c", "b", "a"], ["LEAD"] * 3)
    key = lambda r: {frozenset((c["masked"], c["masker"])): c["score"] for c in r["conflicts"]}  # noqa: E731
    assert key(r1) == key(r2)


def test_sine_energy_normalisation():
    """Contrôle du §1 : un sinus de crête A vaut A²/2 dans sa bande (trames du milieu)."""
    e, _ = bark_energies(tone(1000, -20), FS)
    mid = e[20:-20, 0, band_of(1000)]
    assert 10 * np.log10(np.median(mid)) == pytest.approx(-23.01, abs=0.2)


def test_overlap_metrics_ignore_frames_without_masker():
    """Affichage : le SMR « quand les deux jouent » ne doit pas être gonflé par les silences du masqueur."""
    from mixlab.masking import masker_activity

    target = tone(1100, -40, dur=4.0)
    masker = tone(1000, -20, dur=4.0)
    masker[: len(masker) // 2] = 0.0                       # masqueur absent la première moitié
    et, em = bark_energies(target, FS)[0], bark_energies(masker, FS)[0]
    m = mask_target(et, threshold(em), masker_active=masker_activity(em))
    assert m.overlap_pct == pytest.approx(50, abs=5)
    assert m.median_smr_overlap_db <= -6
    assert m.median_smr_db > m.median_smr_overlap_db
