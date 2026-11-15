import shutil
import subprocess

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.audio import load, probe
from mixlab.cli import main
from mixlab.measures.basic import measure_file


@pytest.mark.parametrize("fs,subtype,label", [
    (48000, "PCM_16", "48 kHz / 16 bits"),
    (44100, "PCM_24", "44,1 kHz / 24 bits"),
    (96000, "FLOAT", "96 kHz / 32 bits flottant"),
])
def test_probe_reports_rate_and_depth(tmp_path, fs, subtype, label):
    p = tmp_path / "f.wav"
    ts.write_wav(p, ts.to_stereo(ts.sine(1000, -20, dur=0.5, fs=fs)), fs, subtype=subtype)
    info = probe(p)
    assert (info.sample_rate, info.channels, info.label) == (fs, 2, label)
    assert info.duration == pytest.approx(0.5)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg absent")
def test_mp3_is_read_and_flagged_lossy(tmp_path):
    wav, mp3 = tmp_path / "a.wav", tmp_path / "a.mp3"
    ts.write_wav(wav, ts.to_stereo(ts.sine(1000, -20, dur=2)), 48000, subtype="PCM_16")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(wav), "-b:a", "320k", str(mp3)], check=True)
    x, info = load(mp3)
    assert info.lossy and info.bit_depth is None and "MP3" in info.label
    assert x.shape[1] == 2


def test_measure_file_on_known_signal(tmp_path):
    p = tmp_path / "s.wav"
    ts.write_wav(p, ts.to_stereo(ts.with_fades(ts.sine(1000, -20, dur=10))), 48000, subtype="PCM_24")
    r = measure_file(p)
    m = r["measures"]
    assert r["file"]["label"] == "48 kHz / 24 bits"
    assert m["integrated_lufs"] == pytest.approx(-20, abs=0.1)
    assert m["true_peak_dbtp"] == pytest.approx(-20, abs=0.05)
    assert m["plr_db"] == pytest.approx(0, abs=0.15)
    assert m["rms_per_channel_dbfs"] == pytest.approx([-23.01, -23.01], abs=0.05)
    band_1k = next(b for b in m["third_octave"] if b["band_hz"] == 1000)
    assert band_1k["level_db"] == pytest.approx(-23.0, abs=0.1)


def test_cli_measure_works_on_a_copy(tmp_path, capsys):
    p = tmp_path / "orig.wav"
    ts.write_wav(p, ts.to_stereo(ts.sine(1000, -20, dur=5)), 48000, subtype="PCM_16")
    before = p.read_bytes()
    assert main(["measure", str(p), "--work", str(tmp_path / "work"), "--json", str(tmp_path / "m.json")]) == 0
    out = capsys.readouterr().out
    assert "48 kHz / 16 bits" in out and "LUFS" in out
    assert p.read_bytes() == before
    assert (tmp_path / "m.json").exists()
