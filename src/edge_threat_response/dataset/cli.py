from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .audit import audit_registry, write_audit_outputs
from .materialize import materialize_knife_yolo, parse_split_limits
from .registry import RegistryError, load_registry
from .split import parse_ratios, plan_manifest_file
from .audit import read_manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="etr-dataset",
        description="Audit YOLO datasets and plan leakage-safe group splits.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser(
        "audit", help="Build a manifest and validate registered dataset sources."
    )
    audit_parser.add_argument("--registry", type=Path, required=True)
    audit_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    audit_parser.add_argument("--output-dir", type=Path, required=True)
    audit_parser.add_argument(
        "--skip-image-hash",
        action="store_true",
        help="Skip image SHA-256 checks for a faster structural-only audit.",
    )
    audit_parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "never"),
        default="error",
        help="Exit non-zero when this severity (or higher) is present.",
    )

    split_parser = subparsers.add_parser(
        "plan-split", help="Assign source groups to splits without moving data files."
    )
    split_parser.add_argument("--manifest", type=Path, required=True)
    split_parser.add_argument("--output-dir", type=Path, required=True)
    split_parser.add_argument(
        "--ratios",
        required=True,
        help="Comma-separated ratios, for example train=0.7,val=0.15,test=0.15.",
    )
    split_parser.add_argument("--seed", type=int, required=True)

    materialize_parser = subparsers.add_parser(
        "materialize-knife-yolo",
        help="Create a leakage-safe one-class YOLO knife dataset from a planned manifest.",
    )
    materialize_parser.add_argument("--manifest", type=Path, required=True)
    materialize_parser.add_argument("--registry", type=Path, required=True)
    materialize_parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    materialize_parser.add_argument("--output-dir", type=Path, required=True)
    materialize_parser.add_argument(
        "--limits",
        help="Optional split limits, for example train=32,val=8,test=0.",
    )
    materialize_parser.add_argument(
        "--link-mode", choices=("hardlink", "copy"), default="hardlink"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "audit":
            return _run_audit(args)
        if args.command == "plan-split":
            return _run_plan_split(args)
        if args.command == "materialize-knife-yolo":
            return _run_materialize_knife_yolo(args)
    except (RegistryError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"Unsupported command {args.command!r}.")
    return 2


def _run_audit(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry, repo_root=args.repo_root)
    result = audit_registry(registry, hash_images=not args.skip_image_hash)
    write_audit_outputs(result, args.output_dir)
    totals = result.summary["totals"]
    print(
        json.dumps(
            {
                "images": totals["images"],
                "objects": totals["objects"],
                "issues": totals["issue_counts"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    severities = totals["issue_severity_counts"]
    if args.fail_on == "error" and severities.get("error", 0):
        return 1
    if args.fail_on == "warning" and (
        severities.get("error", 0) or severities.get("warning", 0)
    ):
        return 1
    return 0


def _run_plan_split(args: argparse.Namespace) -> int:
    ratios = parse_ratios(args.ratios)
    plan = plan_manifest_file(
        args.manifest,
        ratios=ratios,
        seed=args.seed,
        output_dir=args.output_dir,
    )
    print(
        json.dumps(
            {
                "eligible_images": plan["eligible_images"],
                "excluded_images": plan["excluded_images"],
                "groups": plan["group_count"],
                "image_counts": plan["image_counts"],
                "output_dir": str(args.output_dir),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _run_materialize_knife_yolo(args: argparse.Namespace) -> int:
    registry = load_registry(args.registry, repo_root=args.repo_root)
    records = read_manifest(args.manifest)
    summary = materialize_knife_yolo(
        records,
        registry=registry,
        output_dir=args.output_dir,
        source_manifest=args.manifest,
        limits=parse_split_limits(args.limits),
        link_mode=args.link_mode,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
