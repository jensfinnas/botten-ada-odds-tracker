#!/usr/bin/env python3
"""Daily entry point: scrape all sources, then rebuild clean CSVs.

Each scraper fails in isolation; the run succeeds (exit 0) if at least one
source delivered data."""
import argparse
import sys
import traceback

from pipeline.build_clean import build_clean
from scrapers import SCRAPERS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append",
                        help="scrape only this source (repeatable)")
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    args = parser.parse_args(argv)

    succeeded, failed = [], []
    if not args.skip_scrape:
        for name in (args.source or sorted(SCRAPERS)):
            try:
                paths = SCRAPERS[name]()
                print("[%s] OK - %d markets" % (name, len(paths)))
                succeeded.append(name)
            except Exception:
                print("[%s] FAILED" % name, file=sys.stderr)
                traceback.print_exc()
                failed.append(name)

    if not args.skip_clean:
        build_clean()
        print("[clean] rebuilt CSVs")

    if failed:
        print("failed sources: %s" % ", ".join(failed), file=sys.stderr)
    if not args.skip_scrape and not succeeded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
