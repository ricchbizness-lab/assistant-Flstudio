"""Jeu de stems « Split mixer tracks » : chargement, rôles, bus, alignement sur le Master, masquage.

L'attribution de l'écrêtage du bus Master n'est pas faite ici (condition (b) de
l'utilisateur) : seuls le décalage stems/Master et l'écart global sont mesurés.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
from scipy.signal import correlate

from . import __version__
from .audio import load
from .features import bark_energies
from .levels import (gain_staging, importance_weight, master_chain_attribution, stem_levels,
                     third_octave_contributors)
from .masking import analyze_masking, envelope_correlation
from .measures.balance import compare_to_references
from .measures.spectrum import third_octave_spectrum
from .measures.loudness import measure_loudness
from .roles import AUDIO_EXT, detect_role, load_roles_yaml

BUS_RESIDUAL_DB = -30.0
BUS_CORR = 0.2
ALIGN_SEARCH_S = 0.05
ALIGN_WINDOW_S = 10.0


def display_name(filename: str) -> str:
    """Nom lisible : retire le préfixe de projet FL et les remplissages du nom de sample."""
    stem = Path(filename).stem
    tail = re.search(r"(Insert_\d+|Master)$", stem)
    if tail:
        return tail.group(1).replace("_", " ")
    parts = [q for q in re.split(r"_{2,}", stem) if q.strip("_- ")]
    if len(parts) >= 3:
        kind = parts[-2].replace("_", " ").strip(" -")
        sample = parts[-1].replace("_", " ").strip(" -")
        return f"{kind} - {sample}" if sample else kind
    return stem.split("_", 1)[-1] if "_" in stem else stem


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.ravel(), b.ravel()
    d = np.sqrt((a @ a) * (b @ b))
    return float(a @ b / d) if d > 0 else 0.0


def detect_buses(signals: list[np.ndarray]) -> list[int]:
    """Indices des stems qui sont la somme d'autres stems (résidu ≤ -30 dB)."""
    buses = []
    for k, xk in enumerate(signals):
        sources = [j for j, xj in enumerate(signals) if j != k and _corr(xk, xj) > BUS_CORR]
        if not sources:
            continue
        res = xk - sum(signals[j] for j in sources)
        ek, er = float(np.sum(xk * xk)), float(np.sum(res * res))
        if ek > 0 and (er == 0 or 10 * np.log10(er / ek) <= BUS_RESIDUAL_DB):
            buses.append(k)
    return buses


def align(master: np.ndarray, stem_sum: np.ndarray, fs: int) -> dict:
    """Décalage (échantillons, positif = Master en retard) et écart Master - somme alignée."""
    m = master.mean(axis=1) if master.ndim == 2 else master
    s = stem_sum.mean(axis=1) if stem_sum.ndim == 2 else stem_sum
    n = min(len(m), len(s), int(ALIGN_WINDOW_S * fs))
    c = correlate(m[:n], s[:n], mode="full", method="fft")
    lags = np.arange(-n + 1, n)
    search = np.abs(lags) <= int(ALIGN_SEARCH_S * fs)
    lag = int(lags[search][np.argmax(c[search])])
    if lag >= 0:
        mm, ss = master[lag:], stem_sum[: len(stem_sum) - lag]
    else:
        mm, ss = master[: len(master) + lag], stem_sum[-lag:]
    k = min(len(mm), len(ss))
    mm, ss = mm[:k], ss[:k]
    em, er = float(np.sum(mm * mm)), float(np.sum((mm - ss) ** 2))
    return {"lag_samples": lag, "lag_ms": round(1000 * lag / fs, 2),
            "difference_db": None if em == 0 else (float("-inf") if er == 0 else round(10 * np.log10(er / em), 2)),
            "correlation": round(_corr(mm, ss), 4)}


def analyze_stems(folder: str | os.PathLike, roles_yaml: str | os.PathLike | None = None,
                  exclude: list[str] = (), refs: list[str | os.PathLike] = ()) -> dict:
    folder = Path(folder)
    overrides = load_roles_yaml(roles_yaml if roles_yaml is not None else folder / "roles.yaml")
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in AUDIO_EXT and p.name not in exclude)
    items = []
    for p in files:
        x, info = load(p)
        items.append({"path": p, "x": x, "info": info, "role": detect_role(p.name, overrides)})
    rates = {it["info"].sample_rate for it in items}
    if len(rates) != 1:
        raise ValueError(f"fréquences d'échantillonnage différentes : {sorted(rates)}")
    fs = rates.pop()
    n = max(it["x"].shape[0] for it in items)
    for it in items:
        x = it["x"] if it["x"].shape[1] == 2 else np.repeat(it["x"], 2, axis=1)
        it["x"] = np.pad(x, ((0, n - x.shape[0]), (0, 0)))

    masters = [it for it in items if it["role"].role == "MASTER"]
    stems = [it for it in items if it["role"].role != "MASTER"]
    bus_idx = set(detect_buses([it["x"] for it in stems]))
    bus_idx |= {k for k, it in enumerate(stems) if it["role"].role == "BUS"}
    used = [it for k, it in enumerate(stems) if k not in bus_idx]

    def describe(it, status):
        lo = measure_loudness(it["x"], fs)
        return {"file": it["path"].name, "name": display_name(it["path"].name), "role": it["role"].role,
                "role_source": it["role"].source, "format": it["info"].label,
                "duration_s": round(it["info"].duration, 2),
                "integrated_lufs": None if not np.isfinite(lo.integrated) else round(lo.integrated, 2),
                "status": status}

    out = {"mixlab_version": __version__, "folder": str(folder), "sample_rate": fs,
           "stems": [describe(it, "bus (exclu de la somme)" if k in bus_idx else "analysé")
                     for k, it in enumerate(stems)],
           "masters": [describe(it, "master") for it in masters],
           "excluded_files": list(exclude)}

    stem_sum = sum(it["x"] for it in used)
    names = [display_name(it["path"].name) for it in used]
    roles = [it["role"].role for it in used]
    signals = [it["x"] for it in used]
    master = masters[0]["x"] if masters else None

    out["levels"] = stem_levels(signals, names, roles, fs)
    out["gain_staging"] = gain_staging(stem_sum, master, fs)
    if master is not None:
        al = align(master, stem_sum, fs)
        out["master_alignment"] = {**al, "master": masters[0]["path"].name}
        lag = al["lag_samples"]
        if lag >= 0:
            m_al, st_al = master[lag:], [x[: len(x) - lag] for x in signals]
        else:
            m_al, st_al = master[: len(master) + lag], [x[-lag:] for x in signals]
        attr = master_chain_attribution(st_al, names, m_al, fs)
        attr.pop("reduction_db_per_frame", None)
        out["master_chain"] = attr
        if refs:
            m_lufs = measure_loudness(master, fs).integrated
            ref_items = []
            for rp in refs:
                rx, rinfo = load(rp)
                ref_items.append((Path(rp).stem, third_octave_spectrum(rx, rinfo.sample_rate),
                                  measure_loudness(rx, rinfo.sample_rate).integrated))
            comp = compare_to_references((third_octave_spectrum(master, fs), m_lufs), ref_items)
            flagged = [b for b in comp["bands"] if abs(b["delta_db"]) >= 3]
            contrib = third_octave_contributors(signals, names, fs, [b["band_hz"] for b in flagged])
            out["bands_vs_refs"] = {"references": comp["references"], "normalization": comp["normalization"],
                                    "bands": [{**b, "contributors": contrib.get(b["band_hz"], [])} for b in flagged]}

    m_max = {r["name"]: (r["momentary_max_lufs"] if r["momentary_max_lufs"] is not None else -np.inf)
             for r in out["levels"]}
    loudest = max(m_max.values())
    weights = [importance_weight(m_max[nm], loudest) for nm in names]
    energies = [bark_energies(x, fs)[0] for x in signals]
    out["masking"] = analyze_masking(energies, names, roles, weights)

    kicks = [k for k, r in enumerate(roles) if r == "KICK"]
    basses = [k for k, r in enumerate(roles) if r == "808"]
    out["kick_bass"] = [{"kick": names[k], "bass": names[b],
                         "envelope_correlation_30_120hz": (lambda v: None if v is None else round(v, 2))(
                             envelope_correlation(used[k]["x"], used[b]["x"], fs))}
                        for k in kicks for b in basses]
    return out


def format_stems_report(r: dict, top: int = 3) -> str:
    L = [f"Dossier   {r['folder']}", f"Fréquence {r['sample_rate']} Hz", "", "STEMS"]
    for s in r["masters"] + r["stems"]:
        lufs = "n/a" if s["integrated_lufs"] is None else f"{s['integrated_lufs']:.1f} LUFS"
        L.append(f"  {s['role']:<7} {s['format']:<26} {lufs:>11}  {s['name']}"
                 + ("" if s["status"] == "analysé" else f"  [{s['status']}]"))
    if r["excluded_files"]:
        L.append(f"  Exclus à ta demande : {', '.join(r['excluded_files'])}")
    g = r["gain_staging"]
    L += ["", "GAIN STAGING",
          f"  Somme des stems avant le Master : crête {g['sum_peak_dbfs']:+.1f} dBFS, true-peak {g['sum_true_peak_dbtp']:+.1f} dBTP,"
          f" facteur de crête {g['sum_crest_db']:.1f} dB, {g['sum_lufs']:.1f} LUFS",
          f"  Pour que la somme culmine à {g['target_sum_peak_dbfs']:.0f} dBFS : {g['trim_to_target_db']:+.1f} dB sur toutes les pistes"]
    if "master_crest_db" in g:
        L.append(f"  Master : crête {g['master_peak_dbfs']:+.1f} dBFS, true-peak {g['master_true_peak_dbtp']:+.1f} dBTP, "
                 f"facteur de crête {g['master_crest_db']:.1f} dB, {g['master_lufs']:.1f} LUFS")
        L.append(f"  La chaîne Master retire {g['crest_lost_db']:.1f} dB de facteur de crête pour {g['loudness_gained_lu']:+.1f} LU de loudness")
    if "master_alignment" in r:
        a, c = r["master_alignment"], r.get("master_chain", {})
        L += ["", "CHAÎNE MASTER (limiteur, clipper) : QUI LA FAIT TRAVAILLER",
              f"  Décalage {a['lag_samples']} échantillons ({a['lag_ms']} ms), corrélation après alignement {a['correlation']}"]
        if c.get("makeup_gain_db") is not None:
            L.append(f"  Gain appliqué hors réduction : {c['makeup_gain_db']:+.1f} dB · réduction > 1 dB sur "
                     f"{c['reduction_events_pct']:.0f} % du temps, > 3 dB sur {c['reduction_over_3db_pct']:.0f} %, max {c['max_reduction_db']:.1f} dB")
            L.append("  Part de la réduction déclenchée par chaque piste :")
            for d in c["attribution_pct"][:6]:
                L.append(f"    {d['share_pct']:5.1f} %  {d['name']}")
    L += ["", "NIVEAUX DES STEMS (part de l'énergie de chaque bande)",
          "  LUFS   M max  Crête    Sub   Basses  Bas-méd.  Piste"]
    for v in sorted(r["levels"], key=lambda v: -(v["integrated_lufs"] or -99)):
        b = v["band_share_pct"]
        f = lambda x: "  -  " if x is None else f"{x:4.0f} %"  # noqa: E731
        L.append(f"  {v['integrated_lufs']:6.1f} {v['momentary_max_lufs']:6.1f} {v['sample_peak_dbfs']:+5.1f}  {f(b['sub'])} {f(b['bass'])}  {f(b['lowmid'])}   {v['role']:<6} {v['name']}")
    if r.get("bands_vs_refs"):
        br = r["bands_vs_refs"]
        L += ["", f"BANDES À 3 dB OU PLUS DES RÉFÉRENCES ({br['normalization']}) ET QUI LES REMPLIT"]
        for b in br["bands"]:
            who = ", ".join(f"{c['name']} {c['share_pct']:.0f} %" for c in b["contributors"])
            L.append(f"  {str(b['band_hz']):>6} Hz {b['delta_db']:+5.1f} dB : {who}")
    m = r["masking"]
    L += ["", "MASQUAGE GLOBAL (chaque stem face à tous les autres)",
          "  % d'énergie utile masquée · SMR médian · bandes concernées"]
    for s in sorted(m["stems"], key=lambda s: -s["energy_masked_pct"]):
        smr = "n/a" if s["median_smr_db"] is None else f"{s['median_smr_db']:+.1f} dB"
        L.append(f"  {s['energy_masked_pct']:5.1f} %  {smr:>9}  {s['role']:<6} {s['name']:<32} "
                 f"{', '.join(s['masked_bands'][:4])}")
    L += ["", f"CONFLITS PRINCIPAUX (paires, un seul masqueur, classés par % masqué × importance de la piste masquée) — top {top}"]
    for k, c in enumerate(m["conflicts"][:top], 1):
        smr = "n/a" if c["median_smr_overlap_db"] is None else f"{c['median_smr_overlap_db']:+.1f} dB"
        L.append(f"  {k}. {c['masker']} ({c['masker_role']}) masque {c['masked']} ({c['masked_role']}) : "
                 f"{c['energy_masked_pct']:.0f} % de son énergie utile × importance {c['victim_weight']:.2f} = score {c['score']:.1f}, "
                 f"surtout {', '.join(c['bands'][:3])}")
        L.append(f"     jouent ensemble {c['overlap_pct']:.0f} % du temps de la cible · SMR médian quand les deux jouent {smr}"
                 f" · sens inverse {c['reverse_pct']:.0f} %")
    if r["kick_bass"]:
        L += ["", "KICK / BASSES (30-120 Hz) : corrélation des enveloppes (1 = frappent ensemble, ≤ 0 = alternent)"]
        for kb in sorted(r["kick_bass"], key=lambda d: -(d["envelope_correlation_30_120hz"] or -9)):
            L.append(f"  {kb['envelope_correlation_30_120hz']:+.2f}  {kb['kick']} / {kb['bass']}")
    return "\n".join(L)
