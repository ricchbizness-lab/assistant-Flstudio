"""Lecture des fichiers audio (lecture seule) et description de leur format.

Chaque rapport affiche la fréquence d'échantillonnage et la profondeur de
chaque fichier : ``AudioInfo.label`` produit par exemple « 48 kHz / 24 bits ».
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

_BITS = {"PCM_S8": 8, "PCM_U8": 8, "PCM_16": 16, "PCM_24": 24, "PCM_32": 32, "FLOAT": 32, "DOUBLE": 64}
_LOSSY = {"MPEG_LAYER_I", "MPEG_LAYER_II", "MPEG_LAYER_III", "VORBIS", "OPUS"}


@dataclass(frozen=True)
class AudioInfo:
    path: str
    format: str            # WAV, FLAC, MP3...
    subtype: str           # PCM_16, PCM_24, FLOAT, MPEG_LAYER_III...
    sample_rate: int
    channels: int
    frames: int
    bit_depth: int | None  # None pour un format compressé avec pertes
    is_float: bool
    lossy: bool

    @property
    def duration(self) -> float:
        return self.frames / self.sample_rate

    @property
    def label(self) -> str:
        khz = f"{self.sample_rate / 1000:g}".replace(".", ",")
        if self.lossy:
            depth = f"{self.format} (compressé)"
        elif self.is_float:
            depth = f"{self.bit_depth} bits flottant"
        else:
            depth = f"{self.bit_depth} bits"
        return f"{khz} kHz / {depth}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["duration_s"] = round(self.duration, 3)
        d["label"] = self.label
        return d


def probe(path: str | os.PathLike) -> AudioInfo:
    i = sf.info(os.fspath(path))
    lossy = i.subtype in _LOSSY
    return AudioInfo(
        path=str(Path(path)),
        format=i.format,
        subtype=i.subtype,
        sample_rate=int(i.samplerate),
        channels=int(i.channels),
        frames=int(i.frames),
        bit_depth=None if lossy else _BITS.get(i.subtype),
        is_float=i.subtype in ("FLOAT", "DOUBLE"),
        lossy=lossy,
    )


def load(path: str | os.PathLike) -> tuple[np.ndarray, AudioInfo]:
    """Renvoie (signal float64 de forme (n, canaux), info). Le fichier n'est ouvert qu'en lecture."""
    info = probe(path)
    data, fs = sf.read(os.fspath(path), dtype="float64", always_2d=True)
    if fs != info.sample_rate:
        raise ValueError("fréquence d'échantillonnage incohérente")
    if data.shape[1] > 2:
        raise ValueError(f"{data.shape[1]} canaux : seuls le mono et la stéréo sont pris en charge")
    return data, info
