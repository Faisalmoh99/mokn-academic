<div align="center">

# 🎓 مُكِن أكاديمي
### Mokn Academic

**أول مرشد أكاديمي تفاوضي مبني على نظام Multi-Agent**

نظام يحاكي فريق المرشدين الأكاديميين البشريين عبر ثلاثة وكلاء ذكيين يتفاوضون فيما بينهم لاتخاذ قرارات أكاديمية مدروسة.

[التقنيات](#️-التقنيات) • [التشغيل السريع](#-التشغيل-السريع) • [المعمارية](#️-المعمارية) • [الفريق](#-الفريق)

</div>

---

## ❓ المشكلة

**فترة التسجيل المبكر = أزمة أكاديمية متكررة**

في كل جامعة سعودية، تفتح فترة التسجيل المبكر للفصل القادم في منتصف الفصل الحالي. خلال هذه الفترة، يواجه الطالب ثلاث مهام مصيرية في وقت ضيق:

1. **فهم اللوائح:** ما الحد الأقصى لساعاتي بناءً على معدلي؟ ما متطلبات هذه المادة السابقة؟
2. **بناء الجدول:** كيف أتجنب التعارض الزمني؟ هل سجلي يسمح بتسجيل المادة المتقدمة؟
3. **اتخاذ قرار مستقبلي:** هل هذا الجدول يناسب وضعي الأكاديمي الحالي؟ ماذا لو كنت متعثراً في مادة سابقة قد أحرم منها؟

**الواقع الحالي:**

- المرشد الأكاديمي يخدم عدداً كبيراً من الطلاب في نفس الفترة
- مواعيد مكتبية محدودة، ورسائل لا تُرد في الوقت المناسب
- الطالب يتخذ قرارات مصيرية تحت ضغط الوقت، أحياناً دون معرفة كافية بسجله الكامل
- النتيجة: تسجيل مواد غير مناسبة، تعارضات تكتشف متأخراً، أو تكرار للأخطاء السابقة

**المشكلة الجوهرية:** الإرشاد الأكاديمي الحالي **ردّ فعلي** و**بشري بحت** — يعمل فقط حين يطلبه الطالب، ولا يستطيع التوسع طبيعياً ليخدم كل طالب بالعمق المطلوب لاتخاذ قرار سليم.

## 💡 الحل

نظام Multi-Agent يُحاكي فريقاً من المرشدين البشريين:

| الوكيل | الدور | حق النقض |
|--------|------|-----------|
| 🎯 **Orchestrator** | يستقبل الطالب، يصنّف نيته، يدير التفاوض | — |
| ⚖️ **Legis** | حارس اللوائح الأكاديمية (RAG على وثائق الجامعة) | ✓ |
| 📅 **Planner** | مهندس الجداول (Constraint Solver + LLM) — يقرأ السجل الأكاديمي والغياب ويصدر تحذيرات استباقية أثناء بناء الجدول | — |

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

[🎥 شاهد فيديو الديمو (3 دقائق)](https://www.loom.com/share/5a576296b95241b79ac007e5ecd51498)

### 4 سيناريوهات جاهزة للعرض

1. **سؤال عن اللوائح** — Legis يجيب مباشرة مع citations
2. **بناء جدول ناجح** — موافقة في جولة واحدة
3. **تفاوض حقيقي** — اعتراض وإعادة بناء (الـ wow moment)
4. **جدول لطالب حرج** — Planner يقرأ سجل الغياب من فصول سابقة وتاريخ التعثر، فيقترح جدولاً محتاطاً مع تحذيرات أكاديمية مفصّلة

كلها **محفوظة كملفات JSON** ليعمل النظام حتى بدون اتصال بالإنترنت.

## 🛠️ التقنيات

**Backend:**
`Python 3.11` `FastAPI` `LangGraph` `Google Gemini` `ChromaDB` `Sentence Transformers` `Pydantic v2` `pytest`

**Frontend:**
`Next.js 16` `TypeScript` `Tailwind CSS v4` `Framer Motion` `Server-Sent Events`

**Infrastructure:**
`Docker` `Uvicorn` `Server-Sent Events`

## 🔬 تفصيل التقنيات والقرارات المعمارية

### لماذا LangGraph وليس CrewAI أو AutoGen؟

LangGraph يدعم **الرسوم البيانية السيكلية (Cyclic Graphs)** — وهذا جوهر التفاوض الحقيقي. CrewAI و AutoGen تركّز على pipelines خطية حيث ينفذ كل وكيل دوره بالترتيب. أما عندنا، عندما يعترض Legis على اقتراح Planner، نحتاج العودة لـ Planner مع context الاعتراض — وهذي حلقة (loop). LangGraph يعبر عن هذي البنية بـ `add_conditional_edges` بشكل طبيعي.

**البديل المرفوض:** كتابة state machine يدوياً. ينجح في البداية لكن يصبح فوضى مع 3+ وكلاء وحالات تفاوض معقدة.

### لماذا Google Gemini وليس GPT-4 أو Claude؟

ثلاثة أسباب:
1. **الدعم العربي الممتاز:** Gemini مدرّب على كم كبير من النصوص العربية، وهذا حاسم لمشروع يخدم طلاب جامعات سعودية
2. **التكلفة:** Gemini Flash مجاني للاستخدام بحدود معقولة، مهم للـ MVP
3. **Structured Output:** Gemini يدعم Pydantic schemas مباشرة، وهذا يضمن إخراج LLM متوافق مع الـ schemas المعرّفة

**القيد:** اضطررنا لكتابة `_sanitize_schema_for_gemini()` لإزالة `additionalProperties` الذي يضيفه Pydantic v2 ولا يقبله Gemini. تم توثيقه في `backend/src/mokn/llm/gemini.py`.

### لماذا ChromaDB وليس Pinecone أو Weaviate؟

ChromaDB يعمل **محلياً بدون سيرفر منفصل**. للـ MVP الذي يعمل على لاب توب طالب، هذا حاسم. Pinecone و Weaviate يحتاجان سيرفر مدفوع. ChromaDB يحفظ البيانات في ملفات محلية مع `PersistentClient`.

**Embeddings:** نستخدم `paraphrase-multilingual-MiniLM-L12-v2` من sentence-transformers — يدعم 50+ لغة منها العربية، وحجمه 400MB فقط (مقابل 7GB لنماذج أكبر).

### لماذا Server-Sent Events (SSE) وليس WebSockets؟

التفاوض **أحادي الاتجاه** — السيرفر يرسل الـ turns للعميل، والعميل لا يرد أثناء الجلسة. SSE أبسط بكثير من WebSockets ويستخدم HTTP عادي (يعمل عبر أي proxy).

```python
# Backend (FastAPI)
@router.post("/stream")
async def negotiate_stream(req: NegotiateRequest):
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

```typescript
// Frontend (Next.js)
const reader = response.body!.getReader();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  // parse event and update UI
}
```

### لماذا Constraint Solver + LLM وليس LLM فقط للجداول؟

التعارضات الزمنية مشكلة **رياضية** بحتة (Constraint Satisfaction Problem). LLM قد يهلوس ويعطي جدولاً فيه تعارض. لذا نستخدم:

- **Constraint Solver (Python pure logic):** يضمن **ضمانة رياضية** بعدم وجود تعارضات
- **LLM:** يستخدم لـ **التفسير والترتيب** فقط (لماذا هذا الجدول أفضل من ذاك)

النتيجة: ذكاء LLM + موثوقية الخوارزميات الكلاسيكية.

### لماذا Next.js 16 وليس Vite + React عادي؟

- **App Router:** يدعم RTL بشكل أصلي عبر `<html dir="rtl">` في `layout.tsx`
- **Streaming:** يعمل بانسجام مع SSE من الـ backend
- **Turbopack:** أسرع من Webpack في الـ dev mode
- **API Routes:** ممكن نضيفها لاحقاً للـ caching الجانبي

### لماذا Pydantic v2 وليس dataclasses عادية؟

- **Validation تلقائي:** أي field نضع له type، Pydantic يتحقق منه
- **JSON serialization:** `.model_dump_json()` و `.model_validate_json()` سريع جداً (مكتوب بـ Rust)
- **Settings management:** `BaseSettings` يقرأ من `.env` تلقائياً
- **التوافق مع FastAPI:** FastAPI مبني على Pydantic، يعطينا OpenAPI docs مجاناً

### بنية الذاكرة (Memory Architecture)

ثلاث طبقات منفصلة عمداً:

| الطبقة | المحتوى | المدى الزمني |
|--------|---------|----------------|
| **Session State** (LangGraph) | حالة التفاوض الحالية، جولة بجولة | حتى نهاية الـ session |
| **Knowledge Base** (ChromaDB) | لوائح الجامعة كـ embeddings | دائم، يعاد بناؤه عند تحديث اللوائح |
| **Student Records** (JSON files حالياً) | السجل الأكاديمي والـ memory_notes | دائم — مصمم للهجرة لـ Postgres لاحقاً |

### المعالجة عند فشل Gemini

طبقتان للحماية:

1. **داخل الـ backend:** `tenacity` يعيد المحاولة 3 مرات بـ exponential backoff
2. **داخل الـ frontend:** `FailoverDialog` يقترح تشغيل sessions محفوظة من JSON عند فشل الاتصال

```python
# backend/src/mokn/llm/gemini.py
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
async def _call_with_retry(...):
    ...
```

### الـ Schemas كعقود (Contracts)

كل تواصل بين المكونات يمر عبر Pydantic schema. هذا يعني:

- **التغيير في schema = خطأ مرئي فوراً** (compile-time في TypeScript، runtime في Python)
- **التوثيق التلقائي** عبر FastAPI's OpenAPI
- **Type safety** بين الـ backend والـ frontend (نسخة TypeScript من الـ schemas)

أمثلة من الكود:
- `NegotiationTurn` — وحدة المحادثة الواحدة بين الوكلاء
- `VetoDecision` — قرار النقض من Legis
- `ScheduleProposal` — اقتراح جدول من Planner مع warnings و constraints
- `AgentContext` — السياق الكامل المرسل لأي وكيل

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

### المرحلة التالية (v2) — الأشهر القادمة

- [ ] **Guardian Agent (الوكيل الرابع):** فصل مراقبة الغياب والدرجات في وكيل مستقل يعمل في الخلفية 24/7. حالياً Planner يقرأ السجل **عند طلب الطالب**، لكن Guardian سيبادر بالتنبيه **قبل** أن يطلب الطالب — مثلاً عند وصول الغياب لـ 75% من الحد المسموح. **البنية التحتية مصممة لاستقباله دون إعادة هيكلة.**

- [ ] **Memory Layer متقدم:** ربط القرارات السابقة للطالب مع التوصيات الحالية ("في الترم الماضي اقترحنا عليك مادة X ولم تأخذها — هل تريد أن نقترحها مجدداً؟")

- [ ] **Telegram Bot:** قناة تواصل طبيعية للطلاب (الـ dashboard مناسب للديمو لكن Telegram أنسب للاستخدام اليومي)

### المرحلة اللاحقة (v3) — العام القادم

- [ ] **Banner/SIS Integration:** ربط مباشر بأنظمة التسجيل الحقيقية بدلاً من mock data
- [ ] **Multi-University Support:** نسخة لكل جامعة بلوائحها الخاصة، إدارة مركزية للنظام
- [ ] **Admin Dashboard:** لوحة للعمداء ورؤساء الأقسام لمتابعة استخدام النظام والاتجاهات
- [ ] **Voice Interface:** TTS للوكلاء + إدخال صوتي للطلاب (مهم للجاذبية في الديمو)

### الرؤية طويلة المدى

نظام إرشاد أكاديمي وطني يخدم ملايين الطلاب بجودة مرشد خبير، متاح على مدار الساعة، **دون أن يحل محل المرشد البشري** — بل يمكّنه من التركيز على الحالات الصعبة التي تحتاج تدخلاً إنسانياً حقيقياً (طلاب على وشك الفصل، حالات نفسية، استثناءات إدارية).

## 👥 الفريق

| الاسم | الدور | المسؤوليات |
|-------|-------|-------------|
| **فيصل** | Team Lead & AI Engineer | المعمارية الكاملة، نظام الوكلاء، LangGraph، الـ backend والـ frontend، تكامل Gemini و RAG |
| **عادل** | Domain Research & Validation | تحليل اللوائح الأكاديمية الحقيقية، التحقق من واقعية السيناريوهات، توثيق متطلبات المستخدم النهائي، اختبار النظام من منظور المستخدم |

## 🙏 شكر خاص

- جامعة الأمير سطام بن عبدالعزيز — استضافة الهاكاثون
- Beyond Information Technology — رعاية فعالية Agenticthon

---

<div align="center">

**صُنع بشغف في المملكة العربية السعودية 🇸🇦**

</div>
