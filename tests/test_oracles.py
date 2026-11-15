"""Non-régression contre des oracles externes (ffmpeg ebur128, pyloudnorm), si installés.

Le comparatif complet (corpus EBU + références réelles + code de RicchBeatz Master)
est produit par tools/compare_oracles.py.
"""

import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.ebu_cases import all_cases
from mixlab.measures.loudness import measure_loudness
from mixlab.measures.truepeak import true_peak_dbtp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


def _signals():
    music_like = ts.stereo(
        ts.with_fades(np.concatenate([ts.pink_noise(-14, 8, seed=1), ts.pink_noise(-24, 6, seed=2),
                                      ts.pink_noise(-10, 8, seed=3)])),
        ts.with_fades(np.concatenate([ts.pink_noise(-15, 8, seed=4), ts.pink_noise(-25, 6, seed=5),
                                      ts.pink_noise(-11, 8, seed=6)])),
    )
    case5 = next(c for c in all_cases() if c.id == "3341-5").signals[0]
    return {"bruit rose à 3 niveaux": music_like, "EBU 3341-5": case5}


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
@pytest.mark.parametrize("name", list(_signals()))
def test_matches_ffmpeg_ebur128(name, tmp_path):
    from compare_oracles import ffmpeg_ebur128

    x = _signals()[name]
    p = tmp_path / "s.wav"
    ts.write_wav(p, x, 48000, subtype="FLOAT")
    ff = ffmpeg_ebur128(p)
    m = measure_loudness(x, 48000)
    assert m.integrated == pytest.approx(ff["I"], abs=0.15)
    assert m.lra == pytest.approx(ff["LRA"], abs=0.25)
    assert true_peak_dbtp(x) == pytest.approx(ff["TP"], abs=0.15)


@pytest.mark.parametrize("name", list(_signals()))
def test_matches_pyloudnorm_integrated(name):
    pyln = pytest.importorskip("pyloudnorm")
    x = _signals()[name]
    assert measure_loudness(x, 48000).integrated == pytest.approx(pyln.Meter(48000).integrated_loudness(x), abs=0.1)
