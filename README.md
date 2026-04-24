<div align="center">

# 🎓 مُكِن أكاديمي
### Mokn Academic

**أول مرشد أكاديمي تفاوضي مبني على نظام Multi-Agent**

نظام يحاكي فريق المرشدين الأكاديميين البشريين عبر ثلاثة وكلاء ذكيين يتفاوضون فيما بينهم لاتخاذ قرارات أكاديمية مدروسة.

[التقنيات](#️-التقنيات) • [التشغيل السريع](#-التشغيل-السريع) • [المعمارية](#️-المعمارية) • [الفريق](#-الفريق)

</div>

---

## ❓ المشكلة

في الجامعات السعودية، يتحمل المرشد الأكاديمي الواحد مسؤولية **150-250 طالب**. خلال أسبوع التسجيل المزدحم:

- **15-25%** من الطلاب يسجلون مواد خاطئة
- **8-12%** يُحرمون من اختبارات سنوياً بسبب غيابات لم يتم التنبيه إليها
- ساعات هائلة تُهدر في أسئلة متكررة

المشكلة الجوهرية: الإرشاد الحالي **ردّ فعلي** و**موسمي** — يعمل فقط حين يطلبه الطالب، ولا يستطيع التوسع طبيعياً لخدمة آلاف الطلاب يومياً.

## 💡 الحل

نظام Multi-Agent يُحاكي فريقاً من المرشدين البشريين:

| الوكيل | الدور | حق النقض |
|--------|------|-----------|
| 🎯 **Orchestrator** | يستقبل الطالب، يصنّف نيته، يدير التفاوض | — |
| ⚖️ **Legis** | حارس اللوائح الأكاديمية (RAG على وثائق الجامعة) | ✓ |
| 📅 **Planner** | مهندس الجداول (Constraint Solver + LLM) | — |

### ⚡ الميزة الجوهرية: التفاوض الحقيقي

الوكلاء **لا يعملون بالتتابع** كـ pipeline. هم يتجادلون فعلياً عبر LangGraph cyclic graph:

```
الطالب: "ابني لي جدول 21 ساعة"
   │
   ↓
🎯 Orchestrator: يصنّف النية → بناء جدول
   │
   ↓
📅 Planner: يقترح 17 ساعة (الحد الأقصى لمعدل الطالب)
   │
   ↓
⚖️ Legis: 🚫 اعتراض — معدل الطالب 2.1، الحد المسموح 15 ساعة
   │
   ↓
📅 Planner: يعيد البناء → 15 ساعة (يتفاعل مع اعتراض Legis)
   │
   ↓
⚖️ Legis: ✅ موافقة
   │
   ↓
🎯 Orchestrator: يصيغ الرد النهائي
```

**النتيجة:** قرار ناشئ (emergent) لا يستطيع أي وكيل بمفرده الوصول إليه.

## 🎬 العرض

[🎥 شاهد فيديو الديمو (3 دقائق)](LINK_TO_BE_ADDED)

### 4 سيناريوهات جاهزة للعرض

1. **سؤال عن اللوائح** — Legis يجيب مباشرة مع citations
2. **بناء جدول ناجح** — موافقة في جولة واحدة
3. **تفاوض حقيقي** — اعتراض وإعادة بناء (الـ wow moment)
4. **طالب في خطر** — تحذيرات استباقية حول الغياب

كلها **محفوظة كملفات JSON** ليعمل النظام حتى بدون اتصال بالإنترنت.

## 🛠️ التقنيات

**Backend:**
`Python 3.11` `FastAPI` `LangGraph` `Google Gemini` `ChromaDB` `Sentence Transformers` `Pydantic v2` `pytest`

**Frontend:**
`Next.js 16` `TypeScript` `Tailwind CSS v4` `Framer Motion` `Server-Sent Events`

**Infrastructure:**
`Docker` `Uvicorn` `Server-Sent Events`

## 🚀 التشغيل السريع

### المتطلبات

- Python 3.11+
- Node.js 18+
- Google Gemini API key (مجاني من [Google AI Studio](https://aistudio.google.com/))

### الـ Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# إعداد الـ API key
cp .env.example .env
# عدّل .env وأضف GEMINI_API_KEY

# تحميل البيانات الأولية
python scripts/seed_test_data.py

# شغّل الـ server
uvicorn mokn.main:app --app-dir src --reload --reload-dir src
# يفتح على http://localhost:8000
```

### الـ Dashboard

```bash
cd dashboard
npm install
npm run dev
# يفتح على http://localhost:3000
```

افتح المتصفح على `http://localhost:3000` واختر سيناريو من الأعلى.

### وضع Offline (بدون API)

لو ما عندك Gemini API key أو الإنترنت غير مستقر:
- الـ dashboard يعمل بـ pre-recorded sessions موجودة في `dashboard/public/demo_sessions/`
- اختر أي سيناريو من قسم "📂 جلسات محفوظة" في اللوحة

## 🏗️ المعمارية

```
┌──────────────────────────────────────────────────────┐
│                  Next.js Dashboard                   │
│  ┌───────────────────┐  ┌──────────────────────────┐ │
│  │  Agents Panel     │  │  Chat Panel              │ │
│  │  (real-time       │  │  (streaming turns +      │ │
│  │   status)         │  │   final answer)          │ │
│  └───────────────────┘  └──────────────────────────┘ │
└────────────────────────┬─────────────────────────────┘
                         │ Server-Sent Events
                         ↓
┌──────────────────────────────────────────────────────┐
│                  FastAPI Backend                     │
│  ┌────────────────────────────────────────────────┐  │
│  │             LangGraph Orchestration            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐     │  │
│  │  │Orchestr- │→│  Planner  │↔│   Legis  │     │  │
│  │  │  ator    │  │  (Solver)│  │   (RAG)  │     │  │
│  │  └──────────┘  └──────────┘  └──────────┘     │  │
│  └────────────────────────────────────────────────┘  │
│                    │              │                   │
│                    ↓              ↓                   │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Google Gemini   │  │     ChromaDB     │          │
│  │     (LLM)        │  │   (RAG Store)    │          │
│  └──────────────────┘  └──────────────────┘          │
└──────────────────────────────────────────────────────┘
```

## 📁 هيكلة المشروع

```
mokn-academic/
├── backend/                    # نظام الوكلاء
│   ├── src/mokn/
│   │   ├── agents/             # Orchestrator, Legis, Planner
│   │   ├── negotiation/        # LangGraph + state + nodes
│   │   ├── memory/             # ChromaDB wrapper (RAG)
│   │   ├── planning/           # Constraint solver للجداول
│   │   ├── schemas/            # Pydantic models
│   │   ├── api/                # FastAPI routes
│   │   └── llm/                # Gemini client + retry logic
│   ├── tests/                  # 82 tests
│   ├── data/
│   │   ├── mock/               # 5 طلاب + 33 مادة
│   │   └── demo_sessions/      # 4 جلسات محفوظة للديمو
│   └── scripts/                # CLI utilities
│
├── dashboard/                  # واجهة Next.js
│   ├── app/                    # Pages (Next.js App Router)
│   ├── components/             # React components
│   ├── lib/                    # SSE client, types, offline player
│   └── public/demo_sessions/   # نسخ JSON للـ offline mode
│
└── docs/
    └── master-spec.md          # المواصفات التفصيلية الكاملة
```

## 🧪 الاختبارات

```bash
cd backend
pytest tests/ -v
# 82 tests passing
```

تشمل:
- ✅ Unit tests للوكلاء وكل أدواتهم
- ✅ Integration tests للـ negotiation graph
- ✅ Edge cases للحالات النادرة
- ✅ Schema sanitization للتوافق مع Gemini

## 🗺️ الخارطة المستقبلية

- [ ] **Guardian Agent** — وكيل استباقي يراقب الغياب والدرجات ويبادر بالتنبيه قبل الحرمان
- [ ] **Telegram/WhatsApp Integration** — قنوات تواصل طبيعية للطالب
- [ ] **Multi-University Support** — Banner integration + admin dashboard
- [ ] **Memory Layer 2.0** — تذكر تفاعلات الطالب عبر الفصول
- [ ] **Voice Interface** — TTS للوكلاء في الديمو

## 👥 الفريق

| الاسم | الدور |
|-------|-------|
| **فيصل** | Founder & Lead Engineer |

## 🙏 شكر خاص

- جامعة الأمير سطام بن عبدالعزيز — استضافة الهاكاثون
- Beyond Information Technology — رعاية فعالية Agenticthon

---

<div align="center">

**صُنع بشغف في المملكة العربية السعودية 🇸🇦**

</div>
