import numpy as np
import pytest
from scipy.signal import resample_poly

from mixlab import testsignals as ts

FS = 48000


def band_powers_db(x, fs, centers):
    """Puissance par octave (centre fc, bornes fc/√2 .. fc·√2) en dB."""
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / fs)
    return np.array([10 * np.log10(spec[(f >= c / np.sqrt(2)) & (f < c * np.sqrt(2))].sum()) for c in centers])


OCTAVES = [63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]


def test_sine_level_and_frequency():
    x = ts.sine(1000, -20, dur=1.0, fs=FS)
    assert ts.amp_to_db(np.max(np.abs(x))) == pytest.approx(-20.0, abs=1e-3)
    assert ts.rms_db(x) == pytest.approx(-20.0 - 3.0103, abs=0.005)
    k = np.argmax(np.abs(np.fft.rfft(x)))
    assert np.fft.rfftfreq(len(x), 1 / FS)[k] == pytest.approx(1000, abs=1)


def test_tones_contain_both_components():
    x = ts.tones([(1000, -20), (1100, -40)], dur=1.0, fs=FS)
    spec = np.abs(np.fft.rfft(x)) / (len(x) / 2)
    assert ts.amp_to_db(spec[1000]) == pytest.approx(-20, abs=0.01)
    assert ts.amp_to_db(spec[1100]) == pytest.approx(-40, abs=0.01)


def test_intersample_sine_true_peak():
    x = ts.intersample_sine(dur=0.5, fs=FS)
    assert ts.amp_to_db(np.max(np.abs(x))) == pytest.approx(-3.0103, abs=0.001)
    up = resample_poly(x, 16, 1)[1000:-1000]
    assert ts.amp_to_db(np.max(np.abs(up))) == pytest.approx(0.0, abs=0.05)


@pytest.mark.parametrize("gen", [ts.pink_noise, ts.white_noise])
def test_noise_rms_and_determinism(gen):
    a = gen(-20, dur=2.0, fs=FS, seed=1)
    assert ts.rms_db(a) == pytest.approx(-20.0, abs=1e-6)
    assert np.array_equal(a, gen(-20, dur=2.0, fs=FS, seed=1))
    b = gen(-20, dur=2.0, fs=FS, seed=2)
    assert abs(np.corrcoef(a, b)[0, 1]) < 0.05


def test_pink_noise_equal_energy_per_octave():
    x = ts.pink_noise(-20, dur=20.0, fs=FS, seed=3)
    p = band_powers_db(x, FS, OCTAVES)
    assert np.ptp(p) < 1.0, p


def test_pink_noise_is_band_limited():
    x = ts.pink_noise(-20, dur=10.0, fs=FS, seed=7)
    spec = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1 / FS)
    out_of_band = spec[(f < 20) | (f > 20000)].sum()
    assert out_of_band < 1e-12 * spec.sum()


def test_white_noise_plus_3db_per_octave():
    x = ts.white_noise(-20, dur=20.0, fs=FS, seed=4)
    steps = np.diff(band_powers_db(x, FS, OCTAVES))
    assert np.allclose(steps, 3.01, atol=0.5), steps


def test_stereo_modes():
    x = ts.pink_noise(-20, dur=2.0, fs=FS, seed=5)
    assert np.corrcoef(*ts.to_stereo(x, "dual").T)[0, 1] == pytest.approx(1.0)
    assert np.corrcoef(*ts.to_stereo(x, "inverted").T)[0, 1] == pytest.approx(-1.0)
    assert not ts.to_stereo(x, "left")[:, 1].any()
    indep = ts.stereo(x, ts.pink_noise(-20, dur=2.0, fs=FS, seed=6))
    assert abs(np.corrcoef(*indep.T)[0, 1]) < 0.05


def test_write_wav_roundtrip_and_clip_guard(tmp_path):
    import soundfile as sf

    x = ts.to_stereo(ts.sine(440, -6, dur=0.2, fs=FS))
    ts.write_wav(tmp_path / "s.wav", x, FS, subtype="PCM_24")
    y, fs = sf.read(tmp_path / "s.wav")
    assert fs == FS and y.shape == x.shape
    assert np.max(np.abs(y - x)) < 2 ** -22
    with pytest.raises(ValueError):
        ts.write_wav(tmp_path / "c.wav", 3.0 * x, FS, subtype="PCM_24")


def test_invalid_arguments():
    with pytest.raises(ValueError):
        ts.sine(30000, fs=FS)
    with pytest.raises(ValueError):
        ts.to_stereo(np.zeros(4), "surround")
