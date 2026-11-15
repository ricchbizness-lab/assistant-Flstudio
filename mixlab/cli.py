"""Interface en ligne de commande. Les commandes d'analyse arrivent à partir de l'étape 2."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .fetch import FetchError, fetch_release_asset
from .roles import RolesError
from .workcopy import WorkCopyError, make_working_copy


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mixlab", description="Assistant de mixage (mesures et masquage).")
    p.add_argument("--version", action="version", version=f"mixlab {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch-test-data", help="Télécharge les données de test (release GitHub) dans data/")
    f.add_argument("--owner", default="ricchbizness-lab")
    f.add_argument("--repo", default="assistant-Flstudio")
    f.add_argument("--tag", default="test-data-v1")
    f.add_argument("--asset", default="Aquafina")
    f.add_argument("--dest", default="data")

    c = sub.add_parser("copy", help="Crée une copie de travail vérifiée d'un fichier audio")
    c.add_argument("file")
    c.add_argument("--work", default="data/work")

    m = sub.add_parser("measure", help="Mesures de base (format, LUFS, LRA, true-peak, spectre) sur une copie")
    m.add_argument("files", nargs="+")
    m.add_argument("--work", default="data/work")
    m.add_argument("--json", help="Fichier JSON de sortie (un seul fichier mesuré) ou dossier (plusieurs)")

    a = sub.add_parser("analyze", help="Analyse d'un mix stéréo (mud, largeur, dynamique, sections, références)")
    a.add_argument("mix")
    a.add_argument("--ref", action="append", default=[], help="Référence (répéter l'option pour plusieurs)")
    a.add_argument("--sections", help="Frontières imposées en secondes, ex. 15.5,47,79 (sinon détection auto)")
    a.add_argument("--section-threshold", type=float, default=3.0,
                   help="Changement spectral minimal (dB) pour ouvrir une section (défaut 3)")
    a.add_argument("--min-section", type=float, default=8.0, help="Durée minimale d'une section en s (défaut 8, soit environ 4 mesures à 130-140 BPM)")
    a.add_argument("--work", default="data/work")
    a.add_argument("--json", help="Fichier JSON de sortie")

    r = sub.add_parser("roles", help="Rôle détecté pour chaque stem d'un dossier")
    r.add_argument("folder")
    r.add_argument("--roles", help="Fichier roles.yaml (défaut : <dossier>/roles.yaml)")

    args = p.parse_args(argv)
    try:
        if args.cmd == "fetch-test-data":
            folder = fetch_release_asset(args.owner, args.repo, args.tag, args.asset, args.dest)
            print(f"Données extraites dans {folder} (voir MANIFEST.json)")
        elif args.cmd == "copy":
            wc = make_working_copy(args.file, args.work)
            print(f"{wc.path}\nsha256 {wc.sha256}")
        elif args.cmd == "measure":
            _measure(args.files, args.work, args.json)
        elif args.cmd == "analyze":
            _analyze(args)
        elif args.cmd == "roles":
            _roles(args.folder, args.roles)
    except (FetchError, WorkCopyError, RolesError, OSError, ValueError) as e:
        print(f"Erreur : {e}", file=sys.stderr)
        return 1
    return 0


def _measure(files: list[str], work: str, json_out: str | None) -> None:
    import json
    from pathlib import Path

    from .measures.basic import format_summary, measure_file

    for i, f in enumerate(files):
        wc = make_working_copy(f, work)
        result = measure_file(wc.path)
        result["file"]["source"] = str(wc.source)
        result["file"]["sha256"] = wc.sha256
        if i:
            print()
        print(format_summary(result))
        if json_out:
            target = Path(json_out)
            if len(files) > 1:
                target.mkdir(parents=True, exist_ok=True)
                target = target / (Path(f).stem + ".json")
            target.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def _analyze(args) -> None:
    import json
    from pathlib import Path

    from .analyze import analyze_file, format_report

    mix = make_working_copy(args.mix, args.work)
    refs = [make_working_copy(r, args.work).path for r in args.ref]
    bounds = [float(v) for v in args.sections.split(",")] if args.sections else None
    result = analyze_file(mix.path, refs, bounds, section_threshold_db=args.section_threshold,
                          min_section_s=args.min_section)
    result["file"]["source"], result["file"]["sha256"] = str(mix.source), mix.sha256
    print(format_report(result))
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def _roles(folder: str, roles_yaml: str | None) -> None:
    from .roles import detect_folder

    labels = {"yaml": "roles.yaml", "prefix": "préfixe", "guessed": "deviné (casse)", "unknown": "À DÉCRIRE dans roles.yaml"}
    for r in detect_folder(folder, roles_yaml):
        print(f"{r.role:<8} {labels[r.source]:<26} {r.file}")


if __name__ == "__main__":
    raise SystemExit(main())
