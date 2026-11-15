"""Étape 1 : comparaison de mixlab avec trois oracles indépendants.

Oracles : ffmpeg (filtre ebur128, peak=true), pyloudnorm (BS.1770-4, pas de
true-peak), et le code de RicchBeatz Master (Source/Dsp.h compilé sans JUCE).

Corpus : cas EBU mono-fichier reconstruits (mixlab.ebu_cases) + tous les WAV
de data/refs/. Les fichiers de travail vont dans data/validation/ (ignoré par git).
Le tableau est écrit dans docs/validation/step1-oracles.md.

Usage : python tools/compare_oracles.py [--master-src ../Master-plugin/Source]
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mixlab import testsignals as ts  # noqa: E402
from mixlab.audio import load  # noqa: E402
from mixlab.ebu_cases import all_cases  # noqa: E402
from mixlab.measures.loudness import measure_loudness  # noqa: E402
from mixlab.measures.truepeak import true_peak_dbtp  # noqa: E402
from mixlab.workcopy import make_working_copy  # noqa: E402

VAL = ROOT / "data" / "validation"
BIN = ROOT / "data" / "bin" / "master_oracle"

# Écarts maximaux acceptés (définis dans docs/PHASE0.md, étape 1).
# ffmpeg n'affiche qu'une décimale : son arrondi (±0,05) s'ajoute à la tolérance.
TOL_I, TOL_LRA, TOL_TP, FFMPEG_ROUND = 0.1, 0.2, 0.1, 0.05


def ffmpeg_ebur128(path: Path) -> dict:
    p = subprocess.run(["ffmpeg", "-nostats", "-hide_banner", "-i", str(path), "-filter_complex",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True, check=True)
    tail = p.stderr[p.stderr.rfind("Summary:"):]
    grab = lambda pat: float(re.search(pat, tail).group(1))  # noqa: E731
    return {"I": grab(r"I:\s+(-?[\d.]+|-inf) LUFS"), "LRA": grab(r"LRA:\s+(-?[\d.]+) LU"),
            "TP": grab(r"Peak:\s+(-?[\d.]+|-inf) dBFS")}


def pyloudnorm_measure(x: np.ndarray, fs: int) -> dict:
    import pyloudnorm as pyln

    meter = pyln.Meter(fs)
    out = {"I": float(meter.integrated_loudness(x)), "LRA": None}
    try:
        out["LRA"] = float(meter.loudness_range(x))
    except (AttributeError, ValueError):      # LRA absent de la version, ou signal < 3 s
        pass
    return out


def build_master_oracle(src: Path) -> bool:
    if BIN.exists():
        return True
    if not (src / "Dsp.h").exists() or shutil.which("g++") is None:
        return False
    BIN.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["g++", "-O2", "-std=c++17", "-I", str(src), str(ROOT / "tools" / "master_oracle.cpp"),
                    "-o", str(BIN)], check=True)
    return True


def master_measure(x: np.ndarray, fs: int) -> dict:
    raw = VAL / "_tmp.f32"
    st = x if x.shape[1] == 2 else np.repeat(x, 2, axis=1)
    st.astype("<f4").tofile(raw)
    out = subprocess.run([str(BIN), str(raw), str(fs)], capture_output=True, text=True, check=True).stdout.split()
    raw.unlink()
    return {"I": float(out[0]), "LRA": float(out[1]), "TP": float(out[2])}


def corpus() -> list[tuple[str, Path]]:
    VAL.mkdir(parents=True, exist_ok=True)
    items = []
    for c in all_cases():
        # un fichier par signal : les cas 1 et 2 existent en trois variantes (I, M, S) du même signal
        if len(c.signals) != 1 or c.id.endswith(("-momentary_max", "-short_term_max")):
            continue
        p = VAL / f"ebu-{c.id}.wav"
        if not p.exists():
            ts.write_wav(p, c.signals[0], c.fs, subtype="FLOAT")
        items.append((f"EBU {c.id}", p))
    for ref in sorted((ROOT / "data" / "refs").glob("*.wav")):
        wc = make_working_copy(ref, ROOT / "data" / "work")
        items.append((ref.stem, wc.path))
    return items


def fmt(v):
    return "–" if v is None else f"{v:.2f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--master-src", default=str(ROOT.parent / "Master-plugin" / "Source"))
    ap.add_argument("--out", default=str(ROOT / "docs" / "validation" / "step1-oracles.md"))
    args = ap.parse_args()
    have_master = build_master_oracle(Path(args.master_src))

    rows, failures = [], []
    for name, path in corpus():
        x, info = load(path)
        lo = measure_loudness(x, info.sample_rate)
        mine = {"I": lo.integrated, "LRA": lo.lra, "TP": true_peak_dbtp(x)}
        ff = ffmpeg_ebur128(path)
        py = pyloudnorm_measure(x, info.sample_rate)
        ms = master_measure(x, info.sample_rate) if have_master else {"I": None, "LRA": None, "TP": None}

        def check(label, a, b, tol):
            if a is not None and b is not None and np.isfinite(a) and np.isfinite(b) and abs(a - b) > tol:
                failures.append(f"{name} : {label} {a:.2f} vs {b:.2f}")

        check("I/ffmpeg", mine["I"], ff["I"], TOL_I + FFMPEG_ROUND)
        check("I/pyloudnorm", mine["I"], py["I"], TOL_I)
        check("LRA/ffmpeg", mine["LRA"], ff["LRA"], TOL_LRA + FFMPEG_ROUND)
        check("TP/ffmpeg", mine["TP"], ff["TP"], TOL_TP + FFMPEG_ROUND)
        rows.append((name, info.label, mine, ff, py, ms))
        print(f"{name:40s} {info.label:22s} I {mine['I']:7.2f} | ff {ff['I']:6.1f} | py {py['I']:7.2f} | "
              f"master {fmt(ms['I'])}   TP {mine['TP']:6.2f} | ff {ff['TP']:5.1f} | master {fmt(ms['TP'])}")

    lines = [
        "# Étape 1 : comparaison avec les oracles",
        "",
        "Généré par `tools/compare_oracles.py`. Oracles : ffmpeg `ebur128=peak=true` (une décimale), "
        "pyloudnorm 0.2.0 (pas de true-peak), RicchBeatz Master (`Source/Dsp.h` compilé sans JUCE).",
        "",
        f"Tolérances : intégré ±{TOL_I} LU, LRA ±{TOL_LRA} LU, true-peak ±{TOL_TP} dB "
        f"(+{FFMPEG_ROUND} pour l'arrondi d'affichage de ffmpeg). Comparaisons avec Master : "
        "informatives seulement (voir notes).",
        "",
        "| Fichier | Format | I mixlab | I ffmpeg | I pyloudnorm | I Master | LRA mixlab | LRA ffmpeg | "
        "LRA pyloudnorm | LRA Master | TP mixlab | TP ffmpeg | TP Master |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for name, label, mine, ff, py, ms in rows:
        lines.append(f"| {name} | {label} | {fmt(mine['I'])} | {ff['I']:.1f} | {fmt(py['I'])} | {fmt(ms['I'])} | "
                     f"{fmt(mine['LRA'])} | {ff['LRA']:.1f} | {fmt(py['LRA'])} | {fmt(ms['LRA'])} | "
                     f"{fmt(mine['TP'])} | {ff['TP']:.1f} | {fmt(ms['TP'])} |")
    lines += ["", f"**Résultat : {'aucun écart hors tolérance' if not failures else str(len(failures)) + ' écart(s)'}**"]
    lines += [f"- {f}" for f in failures]
    lines += [
        "",
        "## Notes de lecture",
        "",
        "- **pyloudnorm** lit l'intégré environ 0,04 LU plus bas que les trois autres sur tous les signaux : "
        "écart systématique de sa pondération K, sans conséquence (tolérance 0,1).",
        "- **LRA sur musique réelle** : les implémentations divergent davantage que sur les signaux d'essai, "
        "car Tech 3342 laisse libres le pas du court terme (≥ 10 Hz) et l'estimateur de percentile. "
        "mixlab suit le pseudo-code de la norme (pas de 100 ms, percentiles par rang) et reste à ±0,15 LU "
        "de ffmpeg. Master utilise un pas de 1 s, pyloudnorm un autre estimateur : ils sont listés à titre "
        "indicatif et ne servent pas de critère.",
        "- **True-peak, cas EBU 20 à 23** : la crête réelle du signal filtré est de -0,07 à -0,13 dBTP "
        "(référence : suréchantillonnage x32). Le x4 de mixlab et de Master sous-lit au plus 0,06 dB, "
        "ce que la tolérance de la norme (+0,2/-0,4 dB) prévoit.",
        "- **ffmpeg** n'affiche qu'une décimale : ses valeurs sont arrondies à ±0,05.",
    ]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{len(failures)} écart(s) hors tolérance. Tableau : {out}")
    for f in failures:
        print("  ", f)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
