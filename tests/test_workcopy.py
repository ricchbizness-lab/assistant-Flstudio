import builtins
import io
import os
import stat

import pytest

from mixlab.workcopy import WorkCopyError, make_working_copy, sha256_file

PAYLOAD = os.urandom(3 * (1 << 20) + 123)  # > 1 bloc de lecture


@pytest.fixture
def original(tmp_path):
    p = tmp_path / "orig" / "808 slide.wav"
    p.parent.mkdir()
    p.write_bytes(PAYLOAD)
    return p


def _write_flags(mode) -> bool:
    if isinstance(mode, str):
        return any(c in mode for c in "wax+")
    return bool(mode & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))


def test_original_never_opened_for_writing(original, tmp_path, monkeypatch):
    seen = []
    real_open, real_io_open, real_os_open = builtins.open, io.open, os.open

    def spy_open(file, mode="r", *a, **k):
        seen.append((os.fspath(file) if not isinstance(file, int) else file, mode))
        return real_open(file, mode, *a, **k)

    def spy_os_open(path, flags, *a, **k):
        seen.append((os.fspath(path), flags))
        return real_os_open(path, flags, *a, **k)

    monkeypatch.setattr(builtins, "open", spy_open)
    monkeypatch.setattr(io, "open", spy_open)
    monkeypatch.setattr(os, "open", spy_os_open)

    before = original.stat()
    make_working_copy(original, tmp_path / "work")

    on_source = [m for f, m in seen if isinstance(f, str) and os.path.realpath(f) == str(original.resolve())]
    assert on_source, "la source doit avoir été lue"
    assert not any(_write_flags(m) for m in on_source), on_source
    after = original.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)
    assert original.read_bytes() == PAYLOAD


def test_copy_is_identical_hashed_and_read_only(original, tmp_path):
    wc = make_working_copy(original, tmp_path / "work")
    assert wc.path != original.resolve()
    assert wc.path.read_bytes() == PAYLOAD
    assert wc.sha256 == sha256_file(original) == sha256_file(wc.path)
    assert wc.path.parent.name == wc.sha256[:16]
    assert wc.path.name == original.name
    assert not (wc.path.stat().st_mode & stat.S_IWUSR)
    assert not list((tmp_path / "work").glob(".tmp-*"))


def test_hash_is_stable_and_copy_is_idempotent(original, tmp_path):
    a = make_working_copy(original, tmp_path / "work")
    b = make_working_copy(original, tmp_path / "work")
    assert a.sha256 == b.sha256 and a.path == b.path


def test_read_only_original_is_supported(original, tmp_path):
    os.chmod(original, stat.S_IREAD)
    try:
        wc = make_working_copy(original, tmp_path / "work")
        assert wc.path.read_bytes() == PAYLOAD
    finally:
        os.chmod(original, stat.S_IREAD | stat.S_IWRITE)


def test_tampered_existing_copy_is_detected(original, tmp_path):
    wc = make_working_copy(original, tmp_path / "work")
    os.chmod(wc.path, stat.S_IREAD | stat.S_IWRITE)
    wc.path.write_bytes(b"autre contenu")
    with pytest.raises(WorkCopyError, match="différente"):
        make_working_copy(original, tmp_path / "work")


def test_missing_file(tmp_path):
    with pytest.raises(WorkCopyError, match="introuvable"):
        make_working_copy(tmp_path / "absent.wav", tmp_path / "work")
