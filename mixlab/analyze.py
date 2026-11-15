"""Analyse complète d'un mix stéréo (étape 2) : mesures factuelles, sans recommandation.

Contenu : format du fichier, loudness, true-peak, dynamique (globale et par bande),
image stéréo (globale et par bande), équilibre tonal et mud, sections, et, si des
références sont fournies, comparaison spectrale après normalisation du loudness.
Les recommandations chiffrées relèvent de l'étape 4 (module ``rules``).
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from . import __version__
from .audio import load
from .bands import iter_bands
from .measures.balance import compare_to_references, mud_profile
from .measures.dynamics import crest_db
from .measures.loudness import measure_loudness
from .measures.spectrum import NOMINAL_THIRD_OCTAVE, third_octave_spectrum
from .measures.stereo import stereo_stats
from .measures.truepeak import sample_peak_dbfs, true_peak_dbtp
from .sections import detect_boundaries, make_sections, section_table


def _r(v, nd: int = 2):
    return None if v is None or not np.isfinite(v) else round(float(v), nd)


def band_profile(x: np.ndarray, fs: int) -> dict:
    out = {}
    for band, xb in iter_bands(x, fs):
        ms = float(np.mean(xb * xb))
        out[band.key] = {"name": band.name, "lo_hz": band.lo, "hi_hz": band.hi,
                         "rms_db": _r(10 * np.log10(ms)) if ms > 0 else None,
                         "crest_db": _r(crest_db(xb)), "stereo": stereo_stats(xb)}
    return out


def headline(x: np.ndarray, fs: int) -> dict:
    """Mesures principales d'un fichier, réutilisées pour le mix et pour chaque référence."""
    loud = measure_loudness(x, fs)
    tp = true_peak_dbtp(x)
    spec = third_octave_spectrum(x, fs)
    return {"loudness": loud, "true_peak": tp, "spectrum": spec}


def analyze_signal(x: np.ndarray, fs: int, boundaries: list[float] | None = None,
                   section_threshold_db: float = 3.0, min_section_s: float = 8.0) -> dict:
    h = headline(x, fs)
    loud, tp, spec = h["loudness"], h["true_peak"], h["spectrum"]
    duration = x.shape[0] / fs
    auto = boundaries is None
    cuts = detect_boundaries(x, fs, section_threshold_db, min_section_s) if auto else boundaries
    sections = section_table(x, fs, make_sections(duration, cuts))
    for row in sections:
        seg = x[int(row["start_s"] * fs):int(row["end_s"] * fs)]
        st = stereo_stats(seg)
        row["side_pct"] = st.get("side_pct")
        row["crest_db"] = _r(crest_db(seg))
    return {
        "loudness": {**loud.summary(), "true_peak_dbtp": _r(tp), "sample_peak_dbfs": _r(sample_peak_dbfs(x))},
        "dynamics": {"crest_db": _r(crest_db(x)), "plr_db": _r(tp - loud.integrated),
                     "psr_db": _r(tp - loud.short_term_max), "lra_lu": _r(loud.lra)},
        "stereo": stereo_stats(x),
        "bands": band_profile(x, fs),
        "balance": mud_profile(spec),
        "third_octave": spec.to_dict(NOMINAL_THIRD_OCTAVE),
        "sections": {"method": "auto" if auto else "manual", "items": sections,
                     "threshold_db": section_threshold_db if auto else None,
                     "min_section_s": min_section_s if auto else None},
    }


def analyze_file(path: str | os.PathLike, refs: list[str | os.PathLike] = (),
                 boundaries: list[float] | None = None, section_threshold_db: float = 3.0,
                 min_section_s: float = 8.0) -> dict:
    x, info = load(path)
    result = {"mixlab_version": __version__, "file": info.to_dict(),
              "analysis": analyze_signal(x, info.sample_rate, boundaries, section_threshold_db, min_section_s)}
    if refs:
        mix_h = headline(x, info.sample_rate)
        ref_items, ref_files = [], []
        for rp in refs:
            rx, rinfo = load(rp)
            rh = headline(rx, rinfo.sample_rate)
            ref_items.append((Path(rp).stem, rh["spectrum"], rh["loudness"].integrated))
            st = stereo_stats(rx)
            ref_files.append({**rinfo.to_dict(), "integrated_lufs": _r(rh["loudness"].integrated),
                              "true_peak_dbtp": _r(rh["true_peak"]),
                              "plr_db": _r(rh["true_peak"] - rh["loudness"].integrated),
                              "lra_lu": _r(rh["loudness"].lra), "side_pct": st.get("side_pct"),
                              "mud_excess_db": mud_profile(rh["spectrum"])["mud_excess_db"]})
        result["references"] = {
            "files": ref_files,
            "comparison": compare_to_references((mix_h["spectrum"], mix_h["loudness"].integrated), ref_items),
        }
    return result


def _f(v, unit: str = "", nd: int = 1) -> str:
    return "n/a" if v is None else f"{v:.{nd}f}{(' ' + unit) if unit else ''}"


def format_report(res: dict) -> str:
    f, a = res["file"], res["analysis"]
    lo, dy, st, ba = a["loudness"], a["dynamics"], a["stereo"], a["balance"]
    out = [
        f"Fichier   {os.path.basename(f['path'])}",
        f"Format    {f['label']} · {f['channels']} canal(aux) · {f['duration_s']:.1f} s",
        "",
        "LOUDNESS",
        f"  Intégré {_f(lo['integrated_lufs'], 'LUFS')} · court terme max {_f(lo['short_term_max_lufs'], 'LUFS')}"
        f" · LRA {_f(lo['lra_lu'], 'LU')} · true-peak {_f(lo['true_peak_dbtp'], 'dBTP')}",
        "DYNAMIQUE",
        f"  Crête {_f(dy['crest_db'], 'dB')} · PLR {_f(dy['plr_db'], 'dB')} · PSR {_f(dy['psr_db'], 'dB')}",
        "STÉRÉO",
        f"  Corrélation {_f(st.get('correlation'), nd=2)} · côtés {_f(st.get('side_pct'), '%')}"
        f" · perte en mono {_f(st.get('mono_loss_db'), 'dB')} · balance {_f(st.get('balance_db'), 'dB')}",
        "",
        "  Bande          RMS      Crête   Corrél.  Côtés   Perte mono",
    ]
    for b in a["bands"].values():
        s = b["stereo"]
        out.append(f"  {b['name']:<12} {_f(b['rms_db'], nd=1):>7}  {_f(b['crest_db'], nd=1):>7}  "
                   f"{_f(s.get('correlation'), nd=2):>7}  {_f(s.get('side_pct'), '%'):>7}  {_f(s.get('mono_loss_db'), 'dB'):>9}")
    out += [
        "",
        "ÉQUILIBRE",
        f"  Pente {_f(ba['tilt_db_per_octave'], 'dB/octave')} · mud (200-500 Hz au-dessus de la pente) "
        f"{_f(ba['mud_excess_db'], 'dB')}",
        "",
        f"SECTIONS ({'détection auto' if a['sections']['method'] == 'auto' else 'fournies'})",
    ]
    for s in a["sections"]["items"]:
        mark = "  <- la plus forte" if s.get("loudest") else ""
        out.append(f"  {s['label']}  {s['start_s']:6.1f} - {s['end_s']:6.1f} s  {_f(s['integrated_lufs'], 'LUFS'):>11}"
                   f"  côtés {_f(s['side_pct'], '%'):>7}  crête {_f(s['crest_db'], 'dB')}{mark}")
    if "references" in res:
        refs = res["references"]
        out += ["", "RÉFÉRENCES"]
        for r in refs["files"]:
            out.append(f"  {Path(r['path']).stem} · {r['label']} · {_f(r['integrated_lufs'], 'LUFS')} · "
                       f"TP {_f(r['true_peak_dbtp'], 'dBTP')} · PLR {_f(r['plr_db'], 'dB')} · côtés {_f(r['side_pct'], '%')}"
                       f" · mud {_f(r['mud_excess_db'], 'dB')}")
        c = refs["comparison"]
        out += ["", f"  Écart spectral du mix à la moyenne des références ({c['normalization']}) :",
                f"  mud (200-500 Hz) : {c['mud_vs_refs_db']:+.1f} dB", ""]
        several = len(c["references"]) >= 2
        shown = [b for b in c["bands"] if b["outside_refs"] or abs(b["delta_db"]) >= 3]
        if shown:
            out.append("  Bandes à 3 dB ou plus de la moyenne des références"
                       + (" ou hors de leur étendue :" if several else " (une seule référence : pas d'étendue) :"))
            for b in shown:
                spread = (f"  (références de {b['refs_min_db'] - b['refs_mean_db']:+.1f} à "
                          f"{b['refs_max_db'] - b['refs_mean_db']:+.1f} dB autour de leur moyenne)") if several else ""
                out.append(f"    {str(b['band_hz']):>6} Hz  {b['delta_db']:+5.1f} dB{spread}")
        else:
            out.append("  Aucune bande à 3 dB ou plus de la moyenne des références.")
    return "\n".join(out)
