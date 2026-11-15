"""Étape 2 : image stéréo et dynamique sur signaux à valeur connue."""

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.analyze import band_profile
from mixlab.measures.dynamics import crest_db, dynamics_profile
from mixlab.measures.loudness import measure_loudness
from mixlab.measures.stereo import stereo_profile, stereo_stats
from mixlab.measures.truepeak import true_peak_dbtp

FS = 48000
NOISE = ts.pink_noise(-20, dur=10, seed=1)


def test_mono_signal():
    s = stereo_stats(ts.to_stereo(NOISE))
    assert s["correlation"] == pytest.approx(1.0)
    assert s["side_pct"] == pytest.approx(0.0)
    assert s["mono_loss_db"] == pytest.approx(0.0, abs=1e-6)
    assert s["balance_db"] == pytest.approx(0.0, abs=1e-6)


def test_independent_channels():
    s = stereo_stats(ts.stereo(NOISE, ts.pink_noise(-20, dur=10, seed=2)))
    assert abs(s["correlation"]) < 0.05
    assert s["side_pct"] == pytest.approx(50.0, abs=2.5)
    assert s["mono_loss_db"] == pytest.approx(-3.01, abs=0.2)


def test_polarity_inverted():
    s = stereo_stats(ts.to_stereo(NOISE, "inverted"))
    assert s["correlation"] == pytest.approx(-1.0)
    assert s["side_pct"] == pytest.approx(100.0)
    assert s["mono_loss_db"] is None            # tout disparaît en mono


def test_one_sided_and_panned():
    s = stereo_stats(ts.to_stereo(NOISE, "left"))
    assert s["one_sided"] and s["correlation"] is None and s["balance_db"] is None
    assert s["mono_loss_db"] == pytest.approx(-3.01, abs=0.01)
    p = stereo_stats(ts.stereo(NOISE, 0.5 * NOISE))
    assert p["correlation"] == pytest.approx(1.0)
    assert p["balance_db"] == pytest.approx(6.02, abs=0.01)


def test_width_per_band_mono_low_wide_high():
    """Grave mono et aigus indépendants : le profil par bande doit les séparer."""
    low = ts.lowpassed_noise(120, -20, dur=10, seed=3)
    hi_l = ts.pink_noise(-26, dur=10, seed=4, f_lo=3000)
    hi_r = ts.pink_noise(-26, dur=10, seed=5, f_lo=3000)
    prof = stereo_profile(ts.stereo(low + hi_l, low + hi_r), FS)["bands"]
    assert prof["sub"]["correlation"] > 0.98 and prof["sub"]["mono_loss_db"] > -0.1
    assert abs(prof["air"]["correlation"]) < 0.1 and prof["air"]["side_pct"] == pytest.approx(50, abs=5)


def test_silence_is_flagged():
    assert stereo_stats(np.zeros((1000, 2)))["silent"]


def test_sine_crest_factor():
    assert crest_db(ts.sine(1000, -10, dur=1)) == pytest.approx(3.01, abs=0.02)
    assert crest_db(np.zeros(10)) is None


def test_band_crest_of_sub_sine():
    """Sinus 40 Hz avec fondus : le filtre de bande ne doit pas déformer sa crête.
    Référence = crête du même signal non filtré (le fondu abaisse lui-même le RMS)."""
    x = ts.with_fades(ts.sine(40, -10, dur=4), FS, 200)
    prof = band_profile(ts.to_stereo(x), FS)
    assert prof["sub"]["crest_db"] == pytest.approx(crest_db(x), abs=0.1)
    assert prof["sub"]["rms_db"] == pytest.approx(10 * np.log10(np.mean(x ** 2)), abs=0.1)
    assert prof["mid"]["rms_db"] < -60


def _drums(seed=0):
    """Impulsions de bruit à décroissance rapide, 2 par seconde : signal très transitoire."""
    n = FS * 8
    env = np.zeros(n)
    hit = np.exp(-np.arange(int(0.25 * FS)) / (0.03 * FS))
    for start in range(0, n - len(hit), FS // 2):
        env[start:start + len(hit)] = hit
    return ts.to_stereo(0.9 * env * ts.white_noise(-3, dur=8, seed=seed) / 1.0)


def test_compression_lowers_crest_plr_and_psr():
    raw = _drums()
    squashed = np.tanh(6 * raw) / np.tanh(6)            # écrêtage doux très poussé
    def prof(x):
        lo = measure_loudness(x, FS)
        return dynamics_profile(x, FS, lo, true_peak_dbtp(x))
    a, b = prof(raw), prof(squashed)
    assert a["crest_db"] - b["crest_db"] > 6
    assert a["plr_db"] - b["plr_db"] > 3
    assert a["psr_db"] - b["psr_db"] > 3
