import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.measures import spectrum as sp


def test_third_octave_centers():
    assert len(sp.THIRD_OCTAVE_CENTERS) == len(sp.NOMINAL_THIRD_OCTAVE) == 31
    assert np.allclose(sp.THIRD_OCTAVE_CENTERS, sp.NOMINAL_THIRD_OCTAVE, rtol=0.03)
    lo, hi = sp.third_octave_edges()
    assert np.allclose(lo[1:], hi[:-1])          # bandes jointives


@pytest.mark.parametrize("freq,band", [(100, 7), (1000, 17), (3150, 22), (63, 5)])
def test_sine_lands_in_its_third_octave_band(freq, band):
    x = ts.sine(freq, -20, dur=5)
    s = sp.third_octave_spectrum(x, 48000)
    assert int(np.argmax(s.level_db)) == band
    assert s.level_db[band] == pytest.approx(-23.01, abs=0.1)   # énergie d'un sinus de crête 0,1
    others = np.delete(s.level_db, [band - 1, band, band + 1])
    assert np.all(others < s.level_db[band] - 60)


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_pink_noise_is_flat_in_third_octaves(seed):
    x = ts.pink_noise(-20, dur=30, seed=seed)
    s = sp.third_octave_spectrum(x, 48000)
    inner = s.level_db[2:-1]                      # 31,5 Hz .. 16 kHz (bornes du bruit exclues)
    assert np.ptp(inner) < 1.0, np.round(inner, 2)
    assert np.all(np.abs(inner - np.median(inner)) < 0.5)


def test_band_energies_sum_to_total():
    x = ts.pink_noise(-20, dur=10, seed=5)
    f, p = sp.psd(x, 48000)
    total = np.sum(p) * (f[1] - f[0])
    lo, hi = sp.third_octave_edges()
    e = sp.band_energies(f, p, np.r_[0.0, lo[0], hi[-1]], np.r_[lo[0], hi[-1], 24000.0])
    assert e.sum() == pytest.approx(total, rel=1e-9)
    assert e[1] == pytest.approx(np.mean(x ** 2), rel=0.02)


@pytest.mark.parametrize("freq,idx", [(50, 0), (150, 1), (1000, 8), (1100, 9), (4000, 17), (14000, 23), (17000, -1)])
def test_bark_band_index(freq, idx):
    assert sp.bark_band_index(freq) == idx


def test_hz_to_bark_reference_points():
    assert sp.hz_to_bark(1000) == pytest.approx(8.5, abs=0.2)
    assert np.all(np.diff(sp.hz_to_bark(np.linspace(20, 20000, 100))) > 0)


def test_bark_spectrum_sine():
    s = sp.bark_spectrum(ts.sine(1000, -20, dur=5), 48000)
    assert int(np.argmax(s.level_db)) == 8
    assert s.level_db[8] == pytest.approx(-23.01, abs=0.1)
