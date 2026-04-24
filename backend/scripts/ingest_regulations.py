"""Ingest a regulations PDF (or text file) into a Chroma collection.

Usage:
    python scripts/ingest_regulations.py \\
        --pdf data/regulations/sattam-handbook.pdf \\
        --collection regulations
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow running as a script without installing the package.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mokn.config import configure_logging, get_settings  # noqa: E402
from mokn.memory.knowledge import KnowledgeBase  # noqa: E402

logger = logging.getLogger("ingest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest regulations into Chroma.")
    parser.add_argument("--pdf", required=True, help="Path to PDF or .txt file.")
    parser.add_argument(
        "--collection", default="regulations", help="Chroma collection name."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the collection before ingesting.",
    )
    parser.add_argument(
        "--tag",
        default=None,
        help="Optional metadata tag stored on every chunk (e.g. 'undergrad-bylaws').",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    settings = get_settings()
    configure_logging(settings)

    path = Path(args.pdf).expanduser().resolve()
    if not path.exists():
        logger.error("File not found: %s", path)
        return 1

    kb = KnowledgeBase(
        collection_name=args.collection,
        persist_dir=settings.chroma_persist_dir,
        embedding_model=settings.embedding_model,
    )
    if args.reset:
        logger.info("Resetting collection %s", args.collection)
        kb.reset()

    meta = {"tag": args.tag} if args.tag else None
    count = await kb.ingest_document(str(path), metadata=meta)
    logger.info("Ingested %d chunks from %s into '%s'", count, path.name, args.collection)
    logger.info("Collection size: %d", kb.count())
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
