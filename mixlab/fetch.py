"""Téléchargement des données de test depuis une release GitHub.

Les fichiers sont téléchargés dans ``data/`` (ignoré par git), jamais ailleurs.
Un dépôt privé exige un jeton : variable d'environnement ``GITHUB_TOKEN`` ou
``GH_TOKEN`` (droits de lecture sur le dépôt suffisent).
Après extraction, ``MANIFEST.json`` liste le SHA-256 de chaque fichier.
"""

from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from .workcopy import sha256_file

API = "https://api.github.com"
MAX_UNZIPPED_BYTES = 8 * 1024**3

Opener = Callable[[urllib.request.Request], object]


class FetchError(Exception):
    pass


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def _request(url: str, accept: str, token: str | None) -> urllib.request.Request:
    headers = {"Accept": accept, "User-Agent": "mixlab-fetch", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def _open(opener: Opener, req: urllib.request.Request, what: str):
    try:
        return opener(req)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise FetchError(
                f"{what} : introuvable (HTTP 404). Causes possibles : tag absent, release encore "
                "en brouillon, ou dépôt privé sans jeton GITHUB_TOKEN valide."
            ) from e
        if e.code in (401, 403):
            raise FetchError(f"{what} : accès refusé (HTTP {e.code}). Vérifie le jeton GITHUB_TOKEN.") from e
        raise FetchError(f"{what} : erreur HTTP {e.code}.") from e
    except urllib.error.URLError as e:
        raise FetchError(f"{what} : réseau indisponible ({e.reason}).") from e


def safe_extract(zip_path: Path, dest: Path) -> list[Path]:
    """Extrait un zip en refusant les chemins qui sortent de dest et les archives démesurées."""
    dest = dest.resolve()
    out: list[Path] = []
    with zipfile.ZipFile(zip_path) as z:
        infos = [i for i in z.infolist() if not i.is_dir()]
        if sum(i.file_size for i in infos) > MAX_UNZIPPED_BYTES:
            raise FetchError("Archive trop volumineuse une fois décompressée.")
        for info in infos:
            target = (dest / info.filename).resolve()
            if dest not in target.parents:
                raise FetchError(f"Chemin dangereux dans l'archive : {info.filename}")
        for info in infos:
            target = (dest / info.filename).resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst, 1 << 20)
            out.append(target)
    return out


def write_manifest(folder: Path) -> Path:
    files = sorted(p for p in folder.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    manifest = {str(p.relative_to(folder).as_posix()): {"sha256": sha256_file(p), "size": p.stat().st_size}
                for p in files}
    path = folder / "MANIFEST.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def fetch_release_asset(owner: str, repo: str, tag: str, asset_match: str, dest_root: str | os.PathLike,
                        token: str | None = None, opener: Opener | None = None) -> Path:
    """Télécharge l'asset dont le nom contient ``asset_match`` et l'extrait s'il s'agit d'un zip.

    Renvoie le dossier contenant les fichiers (data/<nom de l'asset sans extension>).
    """
    opener = opener or (lambda req: urllib.request.urlopen(req, timeout=60))
    token = token if token is not None else _token()
    dest_root = Path(dest_root).resolve()

    with _open(opener, _request(f"{API}/repos/{owner}/{repo}/releases/tags/{tag}",
                                "application/vnd.github+json", token), f"Release {tag}") as r:
        release = json.load(r)

    assets = release.get("assets", [])
    matches = [a for a in assets if asset_match.lower() in a["name"].lower()]
    if len(matches) != 1:
        names = ", ".join(a["name"] for a in assets) or "aucun"
        raise FetchError(f"{len(matches)} asset(s) correspondant à « {asset_match} ». Disponibles : {names}")
    asset = matches[0]

    dest_root.mkdir(parents=True, exist_ok=True)
    download = dest_root / (asset["name"] + ".part")
    with _open(opener, _request(asset["url"], "application/octet-stream", token), f"Asset {asset['name']}") as r, \
            open(download, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)

    if asset.get("size") and download.stat().st_size != asset["size"]:
        download.unlink()
        raise FetchError("Téléchargement incomplet (taille différente de celle annoncée).")

    stem = Path(asset["name"]).stem
    folder = dest_root / stem
    if zipfile.is_zipfile(download):
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        safe_extract(download, folder)
        download.unlink()
    else:
        folder.mkdir(parents=True, exist_ok=True)
        os.replace(download, folder / asset["name"])
    write_manifest(folder)
    return folder
