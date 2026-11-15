"""Loudness BS.1770-4 / EBU R128 sur signaux synthétiques à valeur connue."""

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.measures.loudness import k_weighting_sos, measure_loudness

RATES = [44100, 48000, 96000]


@pytest.mark.parametrize("fs", RATES)
def test_sine_1k_both_channels(fs):
    """EBU Tech 3341 : sinus 1 kHz à X dBFS sur L et R -> X LUFS."""
    for level in (-20.0, -23.0):
        x = ts.to_stereo(ts.sine(1000, level, dur=20, fs=fs))
        assert measure_loudness(x, fs).integrated == pytest.approx(level, abs=0.1)


@pytest.mark.parametrize("fs", RATES)
def test_sine_1k_single_channel_is_3db_lower(fs):
    x = ts.to_stereo(ts.sine(1000, -20, dur=20, fs=fs), "left")
    assert measure_loudness(x, fs).integrated == pytest.approx(-23.0, abs=0.1)


def test_mono_file_equals_one_channel():
    s = ts.sine(1000, -20, dur=10)
    assert measure_loudness(s, 48000).integrated == pytest.approx(
        measure_loudness(ts.to_stereo(s, "left"), 48000).integrated, abs=1e-9)


def test_k_weighting_response():
    """Gain de la pondération K : ~0 dB à 1 kHz, ~+4 dB au-dessus de 5 kHz, coupure sous 50 Hz."""
    from scipy.signal import sosfreqz

    fs = 48000
    f, h = sosfreqz(k_weighting_sos(fs), worN=[20, 100, 1000, 10000], fs=fs)
    g = 20 * np.log10(np.abs(h))
    assert g[2] == pytest.approx(0.69, abs=0.05)   # compensé par le -0,691 de la formule
    assert g[3] == pytest.approx(4.0, abs=0.2)
    assert g[0] < -10 and g[1] < 0


def test_steady_signal_momentary_and_short_term_match_integrated():
    x = ts.to_stereo(ts.sine(1000, -18, dur=10))
    m = measure_loudness(x, 48000)
    assert m.momentary_max == pytest.approx(-18, abs=0.1)
    assert m.short_term_max == pytest.approx(-18, abs=0.1)
    assert np.ptp(m.momentary) < 0.05
    assert len(m.momentary) == 97 and len(m.short_term) == 71   # pas de 100 ms


def test_absolute_gate_ignores_silence():
    s = np.concatenate([ts.sine(1000, -20, dur=10), np.zeros(48000 * 10)])
    assert measure_loudness(ts.to_stereo(s), 48000).integrated == pytest.approx(-20, abs=0.1)


def test_relative_gate_excludes_quiet_passage():
    """Passage à -40 sous la porte relative (-10 LU sous la moyenne) : ignoré."""
    s = np.concatenate([ts.sine(1000, -20, dur=10), ts.sine(1000, -40, dur=10)])
    assert measure_loudness(ts.to_stereo(s), 48000).integrated == pytest.approx(-20, abs=0.1)


def test_relative_gate_keeps_moderate_passage():
    """-20 et -26 : les deux passent la porte ; résultat = moyenne d'énergie."""
    s = np.concatenate([ts.sine(1000, -20, dur=10), ts.sine(1000, -26, dur=10)])
    expected = 10 * np.log10((10 ** -2 + 10 ** -2.6) / 2)
    assert measure_loudness(ts.to_stereo(s), 48000).integrated == pytest.approx(expected, abs=0.1)


def test_silence():
    m = measure_loudness(np.zeros((48000 * 5, 2)), 48000)
    assert m.integrated == float("-inf") and m.lra == 0.0


@pytest.mark.parametrize("delta", [10.0, 5.0, 20.0])
def test_lra_two_levels(delta):
    """EBU Tech 3342 (cas 1-3) : 20 s à L1 puis 20 s à L1-delta -> LRA = delta (±1 LU dans la norme)."""
    a = ts.pink_noise(-20, dur=20, seed=1)
    b = ts.pink_noise(-20 - delta, dur=20, seed=2)
    m = measure_loudness(ts.to_stereo(np.concatenate([a, b])), 48000)
    assert m.lra == pytest.approx(delta, abs=0.5)


def test_lra_constant_signal_is_zero():
    m = measure_loudness(ts.to_stereo(ts.pink_noise(-20, dur=20, seed=3)), 48000)
    assert m.lra < 0.3


def test_too_short_signal():
    m = measure_loudness(ts.to_stereo(ts.sine(1000, -20, dur=0.3)), 48000)
    assert m.integrated == float("-inf")
