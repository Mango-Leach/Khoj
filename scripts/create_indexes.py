"""Create the three Atlas search/vector indexes (the free tier allows exactly three).

    kb_vec      vector index on kb_chunks (knowledge-hub retrieval)
    mentor_vec  vector index on teacher_profiles (mentor matching)
    opp_text    Atlas Search index on opportunities (exact scheme / job names)

Idempotent: an index that already exists by name is skipped. Needs MONGODB_URI in the
repo-root .env. NOT YET TESTED against a real Atlas cluster (none existed when written).

Note on opp_text: the spec says "opportunities and schemes", but an Atlas Search index
covers one collection. Scheme rules (about 8 records) are looked up by id or name with
ordinary indexes instead, so the three-index budget still holds.

    python scripts/create_indexes.py [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymongo import MongoClient
from pymongo.operations import SearchIndexModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import get_settings  # noqa: E402

EMBEDDING_DIMS = 384  # intfloat/multilingual-e5-small

INDEXES: list[tuple[str, str, dict, str]] = [
    (
        "kb_chunks",
        "kb_vec",
        {
            "fields": [
                {"type": "vector", "path": "embedding", "numDimensions": EMBEDDING_DIMS, "similarity": "cosine"},
                {"type": "filter", "path": "doc_type"},
                {"type": "filter", "path": "language"},
                {"type": "filter", "path": "state"},
                {"type": "filter", "path": "grade_band"},
            ]
        },
        "vectorSearch",
    ),
    (
        "teacher_profiles",
        "mentor_vec",
        {
            "fields": [
                {"type": "vector", "path": "skills_embedding", "numDimensions": EMBEDDING_DIMS, "similarity": "cosine"},
            ]
        },
        "vectorSearch",
    ),
    (
        "opportunities",
        "opp_text",
        {"mappings": {"dynamic": True}},
        "search",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="print what would be created")
    args = parser.parse_args()

    if args.dry_run:
        for collection, name, _, kind in INDEXES:
            print(f"[dry-run] {collection}.{name} ({kind})")
        return 0

    settings = get_settings()
    if not settings.mongodb_uri:
        print("MONGODB_URI is empty. Set it in .env first.", file=sys.stderr)
        return 1

    client = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    db = client[settings.db_name]

    for collection, name, definition, kind in INDEXES:
        if collection not in db.list_collection_names():
            db.create_collection(collection)  # search indexes need the collection to exist
        existing = {ix["name"] for ix in db[collection].list_search_indexes()}
        if name in existing:
            print(f"skip   {collection}.{name} (already exists)")
            continue
        db[collection].create_search_index(SearchIndexModel(definition=definition, name=name, type=kind))
        print(f"create {collection}.{name} ({kind})")
    print("Done. Atlas builds indexes asynchronously; check status in the Atlas UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
