"""Pack every CSV in data/historical/raw into ONE small file: data/historical/matches.csv.gz

Why: GitHub's web upload accepts at most 100 files at a time, and the hosted server needs the whole
match history. Upload this single file instead of the 280 raw CSVs. Re-run it after you refresh the raw CSVs.

    python build_history.py
"""
import sys
from pathlib import Path

from app.services.history_loader import HISTORY_ARCHIVE, load_all_matches, write_archive


def main():
    try:
        matches = load_all_matches(include_overlay=False)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1
    n = write_archive(matches)
    size = Path(HISTORY_ARCHIVE).stat().st_size / 1e6
    print(f"Wrote {HISTORY_ARCHIVE}: {n:,} matches, {size:.1f} MB "
          f"({matches[0]['date']} to {matches[-1]['date']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
