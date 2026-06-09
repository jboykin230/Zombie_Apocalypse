#!/usr/bin/env python3
"""Clear the app's local state: the SQLite store and the ChromaDB index.

Usage:
    python reset.py        # asks for confirmation first
    python reset.py -y     # skip the confirmation prompt

Deletes:
  - zombie_events.db   (events, users, queries)
  - chroma_db/         (the vector index built from Zombie_Plan.pdf)

The next `streamlit run app.py` (or `python ingest.py`) rebuilds the Chroma
index automatically. The ~80 MB embedding model lives in a separate cache and
is NOT removed, so it won't be re-downloaded.
"""
import shutil
import sys
from pathlib import Path

import db
import rag

DB_PATH = Path(db.DB_PATH)
CHROMA_PATH = Path(rag.CHROMA_PATH)


def _clear_path(path, label):
    if not path.exists():
        print(f"• {label} already absent: {path}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    print(f"✔ Cleared {label}: {path}")


def main():
    force = any(arg in ("-y", "--yes") for arg in sys.argv[1:])

    print("This will permanently delete:")
    print(f"  - {DB_PATH}")
    print(f"  - {CHROMA_PATH}")

    if not force:
        if input("Proceed? [y/N] ").strip().lower() not in ("y", "yes"):
            print("Aborted — nothing was deleted.")
            return

    _clear_path(DB_PATH, "SQLite store")
    _clear_path(CHROMA_PATH, "ChromaDB index")
    print("Done. Both stores cleared.")


if __name__ == "__main__":
    main()
