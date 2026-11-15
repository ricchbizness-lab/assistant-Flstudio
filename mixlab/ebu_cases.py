"""Signaux d'essai « minimum requirements » des normes EBU, reconstruits à partir des textes.

- EBU Tech 3341 (version 2023), tableau 1, cas 1-5, 9, 10, 12, 13 et 15-23
  (le cas 6 est en 5.0, les cas 7-8 sont des programmes réels non publiés,
  les cas 11 et 14 visent les mesureurs « en direct » : non repris).
- EBU Tech 3342 (version 2023), cas 1-4 (les cas 5-6 sont des programmes réels).

Les fichiers officiels de l'EBU n'ont pas pu être téléchargés (HTTP 403) ; ces
signaux suivent la description textuelle de chaque cas. Toutes les tonalités
sont des sinus 1 kHz stéréo en phase, niveaux en crête par canal.

Chaque cas est un ``Case`` : identifiant, liste de signaux (plusieurs fichiers
pour les cas 10 et 13), fréquence d'échantillonnage, valeur attendue et tolérance.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import resample_poly

from . import testsignals as ts

FS = 48000


@dataclass
class Case:
    id: str
    description: str
    signals: list[np.ndarray]
    measure: str               # integrated | momentary_max | short_term_max | short_term_flat | momentary_flat | true_peak | lra
    expected: float
    tol_plus: float
    tol_minus: float
    fs: int = FS
    extra: dict = field(default_factory=dict)

    def accepts(self, value: float) -> bool:
        return self.expected - self.tol_minus <= value <= self.expected + self.tol_plus


def _tones(segments: list[tuple[float, float]], fs: int = FS) -> np.ndarray:
    """Concaténation de sinus 1 kHz : segments = [(durée s, dBFS crête), ...] ; dBFS None = silence."""
    parts = []
    for dur, level in segments:
        n = int(round(dur * fs))
        parts.append(np.zeros(n) if level is None else ts.sine(1000, level, dur, fs))
    return ts.to_stereo(np.concatenate(parts))


def _sine_tp(freq_div: int, amp: float, phase_deg: float, fs: int = FS) -> np.ndarray:
    x = amp * np.sin(2 * np.pi * (fs / freq_div) * np.arange(fs) / fs + np.deg2rad(phase_deg))
    return ts.to_stereo(ts.with_fades(x, fs, 10.0))


def _case20(offset: int, fs: int = FS) -> np.ndarray:
    """Sinus fs/6 (0,5) contenant une période de fs/4 (1,0), continu en phase,
    synthétisé à 4·fs, filtré puis décimé avec un décalage de `offset` échantillons."""
    fs4 = 4 * fs
    n = fs4  # 1 s
    freq = np.full(n, fs / 6.0)
    amp = np.full(n, 0.5)
    # début de la période insérée sur un passage par zéro montant de la phase (multiple de 2π)
    period_fs6 = 24                                  # une période de fs/6 = 24 échantillons à 4·fs
    k0 = (n // 2) // period_fs6 * period_fs6
    freq[k0:k0 + 16] = fs / 4.0                      # une période de fs/4 = 16 échantillons à 4·fs
    amp[k0:k0 + 16] = 1.0
    phase = 2 * np.pi * np.concatenate([[0.0], np.cumsum(freq[:-1])]) / fs4
    x4 = ts.with_fades(amp * np.sin(phase), fs4, 10.0)
    x = resample_poly(x4[offset:], 1, 4)
    return ts.to_stereo(x)


def tech3341_cases() -> list[Case]:
    c: list[Case] = []
    for i, lvl in ((1, -23.0), (2, -33.0)):
        sig = _tones([(20, lvl)])
        for m in ("integrated", "momentary_max", "short_term_max"):
            c.append(Case(f"3341-{i}-{m}", f"Sinus 1 kHz {lvl} dBFS, 20 s", [sig], m, lvl, 0.1, 0.1))
    c.append(Case("3341-3", "10 s -36 ; 60 s -23 ; 10 s -36", [_tones([(10, -36), (60, -23), (10, -36)])],
                  "integrated", -23.0, 0.1, 0.1))
    c.append(Case("3341-4", "10 s -72 ; 10 s -36 ; 60 s -23 ; 10 s -36 ; 10 s -72",
                  [_tones([(10, -72), (10, -36), (60, -23), (10, -36), (10, -72)])], "integrated", -23.0, 0.1, 0.1))
    c.append(Case("3341-5", "20 s -26 ; 20,1 s -20 ; 20 s -26", [_tones([(20, -26), (20.1, -20), (20, -26)])],
                  "integrated", -23.0, 0.1, 0.1))
    c.append(Case("3341-9", "(1,34 s -20 ; 1,66 s -30) x5 : court terme constant après 3 s",
                  [_tones([(1.34, -20), (1.66, -30)] * 5)], "short_term_flat", -23.0, 0.1, 0.1))
    c.append(Case("3341-10", "20 fichiers : i·0,15 s silence ; 3 s -23 ; 1 s silence -> max court terme",
                  [_tones([(i * 0.15, None), (3, -23), (1, None)]) for i in range(20)],
                  "short_term_max", -23.0, 0.1, 0.1))
    c.append(Case("3341-12", "(0,18 s -20 ; 0,22 s -30) x25 : momentané constant après 1 s",
                  [_tones([(0.18, -20), (0.22, -30)] * 25)], "momentary_flat", -23.0, 0.1, 0.1))
    c.append(Case("3341-13", "20 fichiers : i·20 ms silence ; 400 ms -23 ; 1 s silence -> max momentané",
                  [_tones([(i * 0.02, None), (0.4, -23), (1, None)]) for i in range(20)],
                  "momentary_max", -23.0, 0.1, 0.1))
    for i, div, amp, ph, exp in ((15, 4, 0.5, 0.0, -6.0), (16, 4, 0.5, 45.0, -6.0), (17, 6, 0.5, 60.0, -6.0),
                                 (18, 8, 0.5, 67.5, -6.0), (19, 4, 1.41, 45.0, 3.0)):
        c.append(Case(f"3341-{i}", f"Sinus fs/{div}, amplitude {amp}, phase {ph}°", [_sine_tp(div, amp, ph)],
                      "true_peak", exp, 0.2, 0.4))
    for i, off in ((20, 0), (21, 1), (22, 2), (23, 3)):
        c.append(Case(f"3341-{i}", f"Sinus fs/6 avec une période fs/4 à 1,0, décimé (décalage {off})",
                      [_case20(off)], "true_peak", 0.0, 0.2, 0.4))
    return c


def tech3342_cases() -> list[Case]:
    defs = [(1, [-20, -30], 10), (2, [-20, -15], 5), (3, [-40, -20], 20), (4, [-50, -35, -20, -35, -50], 15)]
    return [Case(f"3342-{i}", " ; ".join(f"20 s {lv}" for lv in lvls), [_tones([(20, lv) for lv in lvls])],
                 "lra", exp, 1.0, 1.0) for i, lvls, exp in defs]


def all_cases() -> list[Case]:
    return tech3341_cases() + tech3342_cases()
