import io
import json
import urllib.error
import zipfile

import pytest

from mixlab.fetch import FetchError, fetch_release_asset, safe_extract
from mixlab.workcopy import sha256_file


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


def fake_github(release: dict | None, blobs: dict[str, bytes], calls: list):
    def opener(req):
        calls.append(req)
        url = req.full_url
        if "/releases/tags/" in url:
            if release is None:
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
            return FakeResponse(json.dumps(release).encode())
        if url in blobs:
            return FakeResponse(blobs[url])
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
    return opener


def test_missing_release_gives_clear_message(tmp_path):
    calls = []
    with pytest.raises(FetchError, match="brouillon"):
        fetch_release_asset("o", "r", "test-data-v1", "Aquafina", tmp_path / "data",
                            token="", opener=fake_github(None, {}, calls))


def test_download_extract_and_manifest(tmp_path):
    content = {"Aquafina/KICK punchy.wav": b"k" * 1000, "Aquafina/LISEZMOI.txt": "48 kHz".encode()}
    blob = make_zip(content)
    release = {"assets": [{"name": "Aquafina.zip", "url": "https://x/assets/1", "size": len(blob)},
                          {"name": "autre.zip", "url": "https://x/assets/2", "size": 1}]}
    calls = []
    folder = fetch_release_asset("o", "r", "test-data-v1", "aquafina", tmp_path / "data", token="T",
                                 opener=fake_github(release, {"https://x/assets/1": blob}, calls))
    assert folder == (tmp_path / "data" / "Aquafina").resolve()
    assert (folder / "Aquafina" / "KICK punchy.wav").read_bytes() == b"k" * 1000
    manifest = json.loads((folder / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["Aquafina/LISEZMOI.txt"]["sha256"] == sha256_file(folder / "Aquafina" / "LISEZMOI.txt")
    assert not list((tmp_path / "data").glob("*.part"))
    assert all(c.headers["Authorization"] == "Bearer T" for c in calls)
    assert calls[1].headers["Accept"] == "application/octet-stream"


def test_ambiguous_or_missing_asset(tmp_path):
    release = {"assets": [{"name": "autre.zip", "url": "https://x/u", "size": 1}]}
    with pytest.raises(FetchError, match="autre.zip"):
        fetch_release_asset("o", "r", "t", "Aquafina", tmp_path, token="",
                            opener=fake_github(release, {}, []))


def test_truncated_download_is_rejected(tmp_path):
    blob = make_zip({"a.txt": b"abc"})
    release = {"assets": [{"name": "Aquafina.zip", "url": "https://x/u1", "size": len(blob) + 10}]}
    with pytest.raises(FetchError, match="incomplet"):
        fetch_release_asset("o", "r", "t", "Aquafina", tmp_path, token="",
                            opener=fake_github(release, {"https://x/u1": blob}, []))
    assert not list(tmp_path.glob("*.part"))


def test_zip_path_traversal_is_refused(tmp_path):
    z = tmp_path / "evil.zip"
    z.write_bytes(make_zip({"../../evil.txt": b"x"}))
    (tmp_path / "dest").mkdir()
    with pytest.raises(FetchError, match="dangereux"):
        safe_extract(z, tmp_path / "dest")
    assert not (tmp_path / "evil.txt").exists()
