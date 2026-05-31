#!/usr/bin/env python3
"""scrub.py — Metadata Scrubber Tool CLI."""

import argparse
import sys
from pathlib import Path

from scrubber.worker  import collect_files, batch_scrub
from scrubber.metadata import read_metadata
from scrubber.display  import (print_progress, print_summary,
                                print_before_after, print_error, console)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scrub",
        description="Strip EXIF and privacy metadata from files.",
    )
    parser.add_argument(
        "targets", nargs="+", type=Path,
        help="Files or directories to scrub",
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true",
        help="Recurse into subdirectories",
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true",
        help="Preview what would be removed without modifying files",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Show before/after metadata comparison for each file",
    )
    parser.add_argument(
        "-j", "--workers", type=int, default=8,
        help="Number of concurrent worker threads (default 8)",
    )
    args = parser.parse_args()

    # Collect all files from the given targets
    all_files: list[Path] = []
    for target in args.targets:
        all_files.extend(collect_files(target, recursive=args.recursive))

    if not all_files:
        print_error("No files found at the given path(s).")
        return 1

    dry_label = " [DRY RUN]" if args.dry_run else ""
    console.print(
        f"\n[bold]Metadata Scrubber[/bold][dim]{dry_label}[/dim]"
        f"  [dim]{len(all_files)} file(s)[/dim]\n"
    )

    # Read BEFORE metadata for files that will be verified
    before_meta: dict[Path, dict] = {}
    if args.verify or args.dry_run:
        for f in all_files:
            before_meta[f] = read_metadata(f)

    # Run the batch scrubber with live progress output
    results = batch_scrub(
        all_files,
        dry_run=args.dry_run,
        max_workers=args.workers,
        on_progress=print_progress,
    )

    console.print()

    # If --verify, show before/after comparison for each processed file
    if args.verify:
        for result in results:
            if result.get("success") and not result.get("skipped"):
                path = result["path"]
                after = read_metadata(path) if not args.dry_run else {}
                print_before_after(path, before_meta.get(path, {}), after)

    print_summary(results, dry_run=args.dry_run)

    # Exit 1 if any file failed (for CI/scripting use)
    errors = [r for r in results if not r.get("success") and not r.get("skipped")]
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
