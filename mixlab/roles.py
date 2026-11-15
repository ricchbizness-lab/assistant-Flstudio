"""Rôle de chaque stem : préfixe dans le nom de piste, ``roles.yaml`` en secours.

Le nom exact des fichiers produits par « Split mixer tracks » n'est pas encore
connu [NT] (le nom du projet précède probablement celui de la piste). On cherche
donc le jeton de rôle dans tout le nom du fichier, en gardant le dernier trouvé :
« Aquafina_KICK punchy.wav » -> KICK.

Ordre de décision :
1. ``roles.yaml`` (motifs de nom, insensibles à la casse) : toujours prioritaire.
2. Jeton de rôle en majuscules dans le nom (convention convenue).
3. Jeton de rôle quelle que soit la casse (« kick », « Pad ») : marqué « deviné ».
4. Sinon : UNKNOWN.

Format de roles.yaml :

    roles:
      "chords*": KEYS        # motif fnmatch sur le nom de fichier sans extension
      "Insert 7": PERC
"""

from __future__ import annotations

import fnmatch
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROLES = ("KICK", "808", "SNARE", "HAT", "PERC", "LEAD", "KEYS", "PAD", "FX", "VOX", "BUS", "SEND", "MASTER")
AUDIO_EXT = {".wav", ".flac", ".aif", ".aiff", ".mp3"}


class RolesError(Exception):
    pass


@dataclass(frozen=True)
class StemRole:
    file: str
    role: str
    source: str   # yaml | prefix | guessed | unknown


def load_roles_yaml(path: str | os.PathLike | None) -> dict[str, str]:
    if path is None or not Path(path).exists():
        return {}
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    mapping = data.get("roles", {}) if isinstance(data, dict) else {}
    if not isinstance(mapping, dict):
        raise RolesError("roles.yaml : la clé « roles » doit être un dictionnaire motif -> rôle")
    out = {}
    for pattern, role in mapping.items():
        role = str(role).upper()
        if role not in ROLES:
            raise RolesError(f"roles.yaml : rôle inconnu « {role} » pour « {pattern} ». Rôles : {', '.join(ROLES)}")
        out[str(pattern)] = role
    return out


def _tokens(stem: str) -> list[str]:
    return [t for t in re.split(r"[^0-9A-Za-zÀ-ÿ]+", stem) if t]


def detect_role(filename: str, overrides: dict[str, str] | None = None) -> StemRole:
    stem = Path(filename).stem
    for pattern, role in (overrides or {}).items():
        if fnmatch.fnmatch(stem.lower(), pattern.lower()):
            return StemRole(filename, role, "yaml")
    toks = _tokens(stem)
    upper = [t for t in toks if t in ROLES]
    if upper:
        return StemRole(filename, upper[-1], "prefix")
    loose = [t.upper() for t in toks if t.upper() in ROLES]
    if loose:
        return StemRole(filename, loose[-1], "guessed")
    return StemRole(filename, "UNKNOWN", "unknown")


def detect_folder(folder: str | os.PathLike, roles_yaml: str | os.PathLike | None = None) -> list[StemRole]:
    folder = Path(folder)
    overrides = load_roles_yaml(roles_yaml if roles_yaml is not None else folder / "roles.yaml")
    files = sorted(p.name for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXT)
    return [detect_role(f, overrides) for f in files]
