"""Étape 2 : pente spectrale, mud, comparaison aux références après normalisation du loudness."""

import numpy as np
import pytest
from scipy.signal import sosfreqz

from mixlab import testsignals as ts
from mixlab.measures.balance import compare_to_references, mud_profile, spectral_trend
from mixlab.measures.loudness import measure_loudness
from mixlab.measures.spectrum import BandSpectrum, THIRD_OCTAVE_CENTERS, third_octave_edges, third_octave_spectrum

FS = 48000


def spec_and_lufs(x):
    return third_octave_spectrum(x, FS), measure_loudness(x, FS).integrated


def expected_band_gains_db(sos) -> np.ndarray:
    """Gain attendu par tiers d'octave d'un filtre appliqué à du bruit rose (pondération 1/f)."""
    lo, hi = third_octave_edges()
    out = []
    for a, b in zip(lo, hi):
        f = np.geomspace(a, b, 400)
        _, h = sosfreqz(sos, worN=f, fs=FS)
        w = 1 / f
        out.append(10 * np.log10(np.trapezoid(np.abs(h) ** 2 * w, f) / np.trapezoid(w, f)))
    return np.array(out)


@pytest.mark.parametrize("seed", [1, 2])
def test_pink_noise_flat_tilt_no_mud(seed):
    m = mud_profile(third_octave_spectrum(ts.to_stereo(ts.pink_noise(-20, dur=30, seed=seed)), FS))
    assert m["tilt_db_per_octave"] == pytest.approx(0.0, abs=0.1)
    assert m["mud_excess_db"] == pytest.approx(0.0, abs=0.3)


def test_white_noise_tilt_plus_3db_per_octave():
    m = mud_profile(third_octave_spectrum(ts.white_noise(-20, dur=30, seed=3), FS))
    assert m["tilt_db_per_octave"] == pytest.approx(3.01, abs=0.1)
    assert m["mud_excess_db"] == pytest.approx(0.0, abs=0.3)


def test_mud_bump_is_measured_as_predicted():
    """Bruit rose + cloche +6 dB à 300 Hz (Q 1) : valeur égale à la prédiction calculée
    depuis la réponse du filtre (±0,3 dB). La fourchette +4/+6 dB du plan (Phase 0) était
    une estimation fausse : les flancs de la cloche relèvent aussi les bandes de la pente
    (+0,8 dB à 125 Hz, +1,3 dB à 800 Hz) ; la prédiction exacte est 3,73 dB."""
    sos = ts.peaking_sos(FS, 300, 6.0, 1.0)
    x = ts.peaking_eq(ts.pink_noise(-20, dur=30, seed=4), FS, 300, 6.0, 1.0)
    measured = mud_profile(third_octave_spectrum(x, FS))["mud_excess_db"]
    predicted = mud_profile(BandSpectrum(THIRD_OCTAVE_CENTERS, *third_octave_edges(),
                                         expected_band_gains_db(sos)))["mud_excess_db"]
    assert predicted == pytest.approx(3.73, abs=0.05)
    assert measured == pytest.approx(predicted, abs=0.3)


def test_trend_ignores_the_mud_region():
    lvl = np.zeros(31)
    lvl[(THIRD_OCTAVE_CENTERS > 190) & (THIRD_OCTAVE_CENTERS < 520)] = 10.0
    slope, intercept = spectral_trend(BandSpectrum(THIRD_OCTAVE_CENTERS, *third_octave_edges(), lvl))
    assert slope == pytest.approx(0.0, abs=1e-9) and intercept == pytest.approx(0.0, abs=1e-9)


def test_comparison_normalizes_loudness_first():
    """Même signal, 10 dB plus fort : écart nul après normalisation (gain pur)."""
    x = ts.to_stereo(ts.pink_noise(-24, dur=20, seed=5))
    c = compare_to_references(spec_and_lufs(x), [("ref", *spec_and_lufs(x * 10 ** (10 / 20)))])
    assert all(abs(b["delta_db"]) < 0.01 for b in c["bands"]), [b["delta_db"] for b in c["bands"]]
    assert c["mud_vs_refs_db"] == pytest.approx(0.0, abs=0.01)


def test_comparison_two_noise_draws_stay_close():
    """Deux tirages différents de bruit rose, niveaux différents : écarts dus au seul hasard (< 1 dB)."""
    mix = spec_and_lufs(ts.to_stereo(ts.pink_noise(-24, dur=20, seed=5)))
    ref = spec_and_lufs(ts.to_stereo(ts.pink_noise(-14, dur=20, seed=6)))
    c = compare_to_references(mix, [("ref", *ref)])
    assert all(abs(b["delta_db"]) < 1.0 for b in c["bands"])
    assert c["mud_vs_refs_db"] == pytest.approx(0.0, abs=0.3)


def test_comparison_shows_mud_deficit_against_muddy_reference():
    sos_gain = expected_band_gains_db(ts.peaking_sos(FS, 300, 6.0, 1.0))
    mix = spec_and_lufs(ts.to_stereo(ts.pink_noise(-20, dur=20, seed=7)))
    ref_x = ts.to_stereo(ts.peaking_eq(ts.pink_noise(-20, dur=20, seed=8), FS, 300, 6.0, 1.0))
    c = compare_to_references(mix, [("ref", *spec_and_lufs(ref_x))])
    b300 = next(b for b in c["bands"] if b["band_hz"] == 315)
    assert b300["delta_db"] < -4
    assert b300["outside_refs"] is None          # une seule référence : pas d'étendue
    # le spectre normalisé de la référence est décalé par son surplus de loudness : on compare la forme
    mud_mask = (THIRD_OCTAVE_CENTERS > 190) & (THIRD_OCTAVE_CENTERS < 520)
    assert c["mud_vs_refs_db"] < -3.0
    assert c["mud_vs_refs_db"] > -float(np.mean(sos_gain[mud_mask])) - 1.0


def test_refs_spread_and_flags():
    mix = spec_and_lufs(ts.to_stereo(ts.pink_noise(-20, dur=20, seed=9)))
    r1 = spec_and_lufs(ts.to_stereo(ts.peaking_eq(ts.pink_noise(-20, dur=20, seed=10), FS, 300, 3.0, 1.0)))
    r2 = spec_and_lufs(ts.to_stereo(ts.peaking_eq(ts.pink_noise(-20, dur=20, seed=11), FS, 300, -3.0, 1.0)))
    c = compare_to_references(mix, [("r1", *r1), ("r2", *r2)])
    b = next(b for b in c["bands"] if b["band_hz"] == 315)
    assert b["refs_min_db"] < b["mix_db"] < b["refs_max_db"] and not b["outside_refs"]
    assert c["references"] == ["r1", "r2"]


def test_no_refs():
    assert compare_to_references(spec_and_lufs(ts.pink_noise(-20, dur=5)), []) == {}
