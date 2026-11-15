"""Interface en ligne de commande. Les commandes d'analyse arrivent à partir de l'étape 2."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .fetch import FetchError, fetch_release_asset
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
    except (FetchError, WorkCopyError, OSError, ValueError) as e:
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


if __name__ == "__main__":
    raise SystemExit(main())
