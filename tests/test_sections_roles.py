"""Étape 2 : découpage en sections et rôles des stems."""

import json

import numpy as np
import pytest

from mixlab import testsignals as ts
from mixlab.cli import main
from mixlab.roles import RolesError, detect_folder, detect_role, load_roles_yaml
from mixlab.sections import detect_boundaries, make_sections, section_table

FS = 48000


def test_three_spectrally_different_parts():
    """Plan, étape 2 : 3 parties nettement différentes -> frontières à ±0,5 s."""
    x = np.concatenate([ts.pink_noise(-20, 12, seed=1), ts.lowpassed_noise(400, -20, 12, seed=2),
                        ts.white_noise(-26, 12, seed=3)])
    b = detect_boundaries(ts.to_stereo(x), FS)
    assert len(b) == 2
    assert b[0] == pytest.approx(12, abs=0.5) and b[1] == pytest.approx(24, abs=0.5)


def test_level_change_only_is_a_boundary():
    x = np.concatenate([ts.pink_noise(-26, 10, seed=4), ts.pink_noise(-20, 10, seed=5)])
    assert detect_boundaries(ts.to_stereo(x), FS) == pytest.approx([10.0], abs=0.5)


def test_stationary_signal_has_no_boundary():
    assert detect_boundaries(ts.to_stereo(ts.pink_noise(-20, 30, seed=6)), FS) == []


def test_small_change_below_threshold_is_ignored():
    x = np.concatenate([ts.pink_noise(-21, 10, seed=7), ts.pink_noise(-20, 10, seed=8)])
    assert detect_boundaries(ts.to_stereo(x), FS) == []


def test_minimum_section_length():
    """Deux changements à 2 s d'écart : un seul retenu (durée minimale d'une section)."""
    x = np.concatenate([ts.pink_noise(-30, 10, seed=9), ts.pink_noise(-20, 2, seed=10),
                        ts.pink_noise(-10, 10, seed=11)])
    b = detect_boundaries(ts.to_stereo(x), FS)
    assert len(b) == 1


def test_section_table_and_loudest():
    x = ts.to_stereo(np.concatenate([ts.sine(1000, -30, 5), ts.sine(1000, -20, 5)]))
    rows = section_table(x, FS, make_sections(10.0, [5.0]))
    assert [r["label"] for r in rows] == ["A", "B"]
    assert rows[0]["integrated_lufs"] == pytest.approx(-30, abs=0.1)
    assert rows[1]["integrated_lufs"] == pytest.approx(-20, abs=0.1)
    assert rows[1]["loudest"] and not rows[0]["loudest"]


def test_make_sections_ignores_out_of_range_cuts():
    s = make_sections(30.0, [-1, 10, 30, 45, 20])
    assert [(x.start, x.end) for x in s] == [(0, 10), (10, 20), (20, 30)]


@pytest.mark.parametrize("name,role,source", [
    ("Aquafina_KICK punchy.wav", "KICK", "prefix"),
    ("808 slide.wav", "808", "prefix"),
    ("Aquafina - BUS drums.wav", "BUS", "prefix"),
    ("Projet KICK_SEND reverb.wav", "SEND", "prefix"),     # le dernier jeton de rôle gagne
    ("Aquafina_Master.wav", "MASTER", "guessed"),
    ("pad strings.wav", "PAD", "guessed"),
    ("Insert 7.wav", "UNKNOWN", "unknown"),
    ("Kickback melody.wav", "UNKNOWN", "unknown"),          # « Kickback » n'est pas « KICK »
])
def test_detect_role(name, role, source):
    r = detect_role(name)
    assert (r.role, r.source) == (role, source)


def test_roles_yaml_overrides_and_validates(tmp_path):
    y = tmp_path / "roles.yaml"
    y.write_text('roles:\n  "insert 7": perc\n  "*KICK punchy": "808"\n', encoding="utf-8")
    overrides = load_roles_yaml(y)
    assert detect_role("Insert 7.wav", overrides).role == "PERC"
    r = detect_role("Aquafina_KICK punchy.wav", overrides)
    assert (r.role, r.source) == ("808", "yaml")
    y.write_text('roles:\n  "x": GUITARE\n', encoding="utf-8")
    with pytest.raises(RolesError, match="GUITARE"):
        load_roles_yaml(y)


def test_detect_folder_and_cli(tmp_path, capsys):
    for n in ("A_KICK.wav", "A_808 sub.wav", "A_chords.wav", "notes.txt"):
        (tmp_path / n).write_bytes(b"")
    (tmp_path / "roles.yaml").write_text('roles:\n  "*chords": KEYS\n', encoding="utf-8")
    roles = {r.file: r.role for r in detect_folder(tmp_path)}
    assert roles == {"A_808 sub.wav": "808", "A_KICK.wav": "KICK", "A_chords.wav": "KEYS"}
    assert main(["roles", str(tmp_path)]) == 0
    assert "KEYS" in capsys.readouterr().out


def test_cli_analyze_with_reference(tmp_path, capsys):
    mix, ref = tmp_path / "mix.wav", tmp_path / "ref.wav"
    ts.write_wav(mix, ts.to_stereo(ts.with_fades(ts.pink_noise(-24, 12, seed=12))), FS, subtype="PCM_24")
    ts.write_wav(ref, ts.to_stereo(ts.with_fades(ts.pink_noise(-18, 12, seed=13))), 44100, subtype="PCM_16")
    before = mix.read_bytes()
    out = tmp_path / "a.json"
    assert main(["analyze", str(mix), "--ref", str(ref), "--work", str(tmp_path / "w"), "--json", str(out)]) == 0
    text = capsys.readouterr().out
    assert "48 kHz / 24 bits" in text and "44,1 kHz / 16 bits" in text
    assert mix.read_bytes() == before
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["references"]["comparison"]["normalization"].startswith("chaque spectre")
    assert abs(data["references"]["comparison"]["mud_vs_refs_db"]) < 0.5
    assert set(data["analysis"]["bands"]) == {"sub", "bass", "lowmid", "mid", "highmid", "air"}
