"""Seed a tiny synthetic regulations corpus into Chroma for local dev.

Writes a handful of representative Arabic passages so devs can exercise
Legis end-to-end before the real handbook PDFs are available.
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from textwrap import dedent

_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from mokn.config import configure_logging, get_settings  # noqa: E402
from mokn.memory.knowledge import KnowledgeBase  # noqa: E402

SAMPLE_PASSAGES = [
    (
        "credit-hours.txt",
        dedent(
            """
            المادة 14: العبء الدراسي
            يحدد العبء الدراسي للطالب المنتظم بين 12 و 18 ساعة معتمدة في الفصل.
            لا يُسمح للطالب بتسجيل 18 ساعة إلا إذا كان معدله التراكمي 3.0 أو أعلى.
            الطالب الذي معدله التراكمي بين 2.0 و 2.99 يُسمح له بحد أقصى 15 ساعة.
            الطالب الذي معدله أقل من 2.0 يقتصر على 12 ساعة كحد أقصى.
            """
        ).strip(),
    ),
    (
        "prerequisites.txt",
        dedent(
            """
            المادة 22: المتطلبات السابقة
            لا يجوز للطالب تسجيل مادة قبل اجتيازه المتطلب السابق لها بنجاح.
            يُستثنى من ذلك الطالب في الفصل الأخير من التخرج بموافقة عميد الكلية.
            مادة "برمجة 2" يشترط لها اجتياز "برمجة 1" بتقدير لا يقل عن مقبول.
            """
        ).strip(),
    ),
    (
        "attendance.txt",
        dedent(
            """
            المادة 31: الحرمان بسبب الغياب
            يُحرم الطالب من دخول الاختبار النهائي إذا تجاوزت نسبة غيابه 25% من مجموع المحاضرات.
            يُنبّه الطالب كتابياً عند وصول الغياب إلى 15%، ثم عند 20%.
            يحق للطالب تقديم عذر خلال أسبوع من تاريخ الغياب.
            """
        ).strip(),
    ),
    (
        "summer-term.txt",
        dedent(
            """
            المادة 40: الفصل الصيفي
            العبء الأقصى في الفصل الصيفي 8 ساعات معتمدة لأي طالب بصرف النظر عن معدله.
            يُسمح للطالب بتسجيل 10 ساعات في الصيفي فقط لغرض التخرج في الفصل ذاته.
            """
        ).strip(),
    ),
]


async def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    kb = KnowledgeBase(
        collection_name="regulations",
        persist_dir=settings.chroma_persist_dir,
        embedding_model=settings.embedding_model,
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        total = 0
        for filename, text in SAMPLE_PASSAGES:
            p = tmp_path / filename
            p.write_text(text, encoding="utf-8")
            added = await kb.ingest_document(
                str(p), metadata={"tag": "seed"}
            )
            total += added
    print(f"Seeded {total} chunks across {len(SAMPLE_PASSAGES)} synthetic documents.")
    print(f"Collection size now: {kb.count()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
