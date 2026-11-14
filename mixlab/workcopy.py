"""Copies de travail : les fichiers originaux ne sont jamais modifiés.

Le fichier source est ouvert uniquement en lecture binaire ("rb"). La copie est
rangée sous ``<work_root>/<sha256[:16]>/<nom d'origine>``, vérifiée par hash,
puis passée en lecture seule. Toute analyse travaille sur la copie.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path

CHUNK = 1 << 20


class WorkCopyError(Exception):
    pass


@dataclass(frozen=True)
class WorkingCopy:
    source: Path
    path: Path
    sha256: str
    size: int


def sha256_file(path: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _signature(p: Path) -> tuple[int, int]:
    st = p.stat()
    return st.st_size, st.st_mtime_ns


def _copy_and_hash(src: Path, tmp: Path) -> str:
    """Copie src -> tmp en un seul passage et renvoie le hash de ce qui a été lu."""
    h = hashlib.sha256()
    with open(src, "rb") as fin, open(tmp, "wb") as fout:
        while True:
            block = fin.read(CHUNK)
            if not block:
                break
            h.update(block)
            fout.write(block)
    return h.hexdigest()


def _make_read_only(p: Path) -> None:
    os.chmod(p, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)


def make_working_copy(src: str | os.PathLike, work_root: str | os.PathLike) -> WorkingCopy:
    src = Path(src).resolve()
    work_root = Path(work_root).resolve()
    if not src.is_file():
        raise WorkCopyError(f"Fichier introuvable : {src}")

    before = _signature(src)
    work_root.mkdir(parents=True, exist_ok=True)
    tmp = work_root / f".tmp-{os.getpid()}-{src.name}"
    try:
        digest = _copy_and_hash(src, tmp)
        if _signature(src) != before:
            raise WorkCopyError(f"Le fichier source a changé pendant la copie : {src}")
        if sha256_file(tmp) != digest:
            raise WorkCopyError(f"Copie corrompue (hash différent) : {src}")

        dest_dir = work_root / digest[:16]
        dest = dest_dir / src.name
        if dest.exists() and dest.samefile(src):
            raise WorkCopyError("La source est déjà une copie de travail ; rien à faire.")
        if dest.exists():
            if sha256_file(dest) != digest:
                raise WorkCopyError(f"Une copie différente existe déjà : {dest}")
            tmp.unlink()
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, dest)
            _make_read_only(dest)
    finally:
        if tmp.exists():
            tmp.unlink()

    return WorkingCopy(source=src, path=dest, sha256=digest, size=before[0])
