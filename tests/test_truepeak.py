import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.measures import truepeak as tp


def test_upsampling_keeps_original_samples():
    x = ts.pink_noise(-20, dur=0.5, seed=1)
    y = tp.upsample4(x)
    assert len(y) == 4 * len(x)
    assert np.allclose(y[::4], x, atol=1e-12)


def test_intersample_sine_reads_0_dbtp():
    x = ts.with_fades(ts.intersample_sine(dur=1.0))
    assert tp.sample_peak_dbfs(x) == pytest.approx(-3.01, abs=0.01)
    assert tp.true_peak_dbtp(x) == pytest.approx(0.0, abs=0.05)


@pytest.mark.parametrize("freq", [100, 1000, 5000, 10000])
def test_sine_true_peak_equals_amplitude(freq):
    x = ts.with_fades(ts.sine(freq, -6, dur=1.0))
    assert tp.true_peak_dbtp(x) == pytest.approx(-6.0, abs=0.05)


def test_stereo_takes_loudest_channel():
    x = ts.stereo(ts.with_fades(ts.sine(1000, -12, dur=1.0)), ts.with_fades(ts.intersample_sine(dur=1.0)) * 0.5)
    assert tp.true_peak_dbtp(x) == pytest.approx(-6.02, abs=0.05)


def test_block_boundaries_do_not_change_the_result(monkeypatch):
    x = ts.with_fades(ts.pink_noise(-12, dur=3.0, seed=2))
    full = tp.true_peak_linear(x)
    monkeypatch.setattr(tp, "BLOCK", 1000)
    assert tp.true_peak_linear(x) == pytest.approx(full, rel=1e-12)


def test_true_peak_never_below_sample_peak():
    x = ts.pink_noise(-6, dur=2.0, seed=4)
    assert tp.true_peak_dbtp(x) >= tp.sample_peak_dbfs(x)


def test_silence():
    assert tp.true_peak_dbtp(np.zeros(1000)) == float("-inf")
