# مُكِن أكاديمي — Mokn Academic

**Multi-agent academic advisor for Saudi universities — delivered over WhatsApp.**

Four autonomous AI agents negotiate on a student's behalf to build a valid course schedule, answer regulation questions, and flag at-risk patterns — handling 80% of a human advisor's workload without a single form or office visit.

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-purple)
![Gemini](https://img.shields.io/badge/Gemini-1.5_Pro-blue?logo=google&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5+-orange)
![License](https://img.shields.io/badge/License-MIT-green)

> Built at **Agenticthon 2026** — a hackathon focused on agentic AI systems.

---

## The Problem

University academic advisors in Saudi Arabia are overwhelmed. Students queue for hours to ask simple registration questions, get schedule approvals, or understand why they're flagged for academic probation — all of which follow deterministic rules that exist in a PDF handbook no one reads.

Mokn Academic automates the rules, not the exceptions.

---

## How It Works

A student sends a WhatsApp message. The system routes it through a **LangGraph cyclic negotiation graph** where three specialist agents collaborate:

```
Student request
     │
     ▼
 Orchestrator  ──classifies──► Legis only (regulation Q&A)
     │
     ├──► fetch student data
     │         │
     │         ▼
     │      Planner  ──proposes schedule──► Legis review
     │                                          │
     │                              (veto + objections)
     │                                          │
     │                             Planner revises ◄──┘
     │                             (up to max_rounds)
     │                                          │
     │                              (approved or exhausted)
     │                                          │
     └──────────────────────► Orchestrator synthesizes
                                       │
                                       ▼
                              WhatsApp reply to student
```

The Planner↔Legis cycle is what makes this "true multi-agent": Planner proposes, Legis vetoes with cited regulation text, Planner revises in light of the objection, and Legis sees the revised proposal. Only when Legis approves (or the round cap is hit) does Orchestrator synthesize a final answer.

---

## The Four Agents

| Agent | Role | How it works |
|---|---|---|
| **Orchestrator** | Classifies intent, synthesizes final reply | Gemini structured output → `Intent` enum routing |
| **Legis** | Regulation guardian + veto authority | Arabic RAG over university handbook PDFs → cited `RegulationAnswer` |
| **Planner** | Course schedule builder + constraint solver | Reads student record, proposes `ScheduleProposal`, revises on objection |
| **Guardian** *(planned)* | Early-warning for at-risk students | GPA trend + credit load analysis |

---

## Arabic RAG Pipeline

The university regulation handbook (Arabic PDF) is chunked and embedded into **ChromaDB** using a multilingual sentence-transformer model (`paraphrase-multilingual-MiniLM-L12-v2`). Every Legis answer is grounded in retrieved chunks — the LLM is explicitly forbidden from using prior knowledge.

- **Chunking:** 500-token chunks, 50-token overlap, Arabic section headings (`المادة`, `الفصل`, `الباب`) preserved as metadata
- **Confidence tiers:** cosine distance < 0.35 = strong match, < 0.65 = weak match, above = "not found in regulations"
- **Veto citations:** every objection includes the exact regulation article number and text that was violated

---

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph `StateGraph` (cyclic, async) |
| LLM | Google Gemini 1.5 Pro (`google-genai` SDK) |
| Vector store | ChromaDB (local persist) |
| Embeddings | `sentence-transformers` multilingual model |
| API | FastAPI + Server-Sent Events for streaming |
| Data validation | Pydantic v2 throughout |
| WhatsApp | Meta Cloud API / Evolution API |
| Infrastructure | Docker Compose, Render |

---

## Quickstart

```bash
git clone https://github.com/Faisalmoh99/mokn-academic.git
cd mokn-academic
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set GEMINI_API_KEY

# Ingest university handbook PDF into ChromaDB
python scripts/ingest_regulations.py --pdf data/regulations/handbook.pdf --collection regulations

# Start the API
uvicorn mokn.main:app --app-dir src --reload --reload-dir src
```

**Ask Legis a regulation question (Arabic):**
```bash
curl -X POST http://localhost:8000/api/legis/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "كم الحد الأقصى للساعات المسموح بها للطالب بمعدل 2.8؟"}'
```

**Run a full negotiation:**
```bash
curl -X POST http://localhost:8000/api/negotiate \
  -H "Content-Type: application/json" \
  -d '{"student_id": "s001", "request": "أريد تسجيل 18 ساعة هذا الفصل"}'
```

**Run tests:**
```bash
pytest tests/ -v
```

---

## Project Layout

```
src/mokn/
  agents/
    base.py              BaseAgent ABC
    legis.py             Regulation guardian — RAG + veto
    orchestrator.py      Intent classifier + reply synthesizer
    planner.py           Schedule builder + constraint-aware reviser
  negotiation/
    graph.py             LangGraph StateGraph — build + run_negotiation + streaming
    nodes.py             Graph node factories (classify, planner_propose, legis_review, …)
    routing.py           Conditional edge logic (route_after_classify, route_after_review)
    state.py             NegotiationState TypedDict
    store.py             Session persistence
    constraint_extractor.py  Pulls credit/semester constraints from free text
  memory/
    knowledge.py         ChromaDB KnowledgeBase — ingest, chunk, query
  llm/
    gemini.py            GeminiClient — single LLM entrypoint, retry, structured output
  api/routes/
    negotiate.py         POST /api/negotiate + SSE /api/negotiate/stream
    legis.py             POST /api/legis/ask + /api/legis/validate-proposal
    planner.py           POST /api/planner/propose
    students.py          CRUD /api/students
  schemas/               Pydantic v2 models for every domain object
  config.py              pydantic-settings — single config source
  main.py                FastAPI app factory

tests/                   pytest suite — LLM calls mocked
scripts/
  ingest_regulations.py  PDF → ChromaDB ingestion CLI
  seed_students.py       Populate mock student data
  capture_demo_sessions.py  Record demo sessions for offline replay
data/
  mock/                  Sample courses + students (JSON)
  demo_sessions/         Pre-recorded negotiation transcripts for live demo
```

---

## Negotiation State

Every graph node reads and writes a `NegotiationState` TypedDict:

```python
{
  "session_id": str,
  "student_id": str | None,
  "user_request": str,
  "intent": "regulation_question" | "build_schedule" | "unknown",
  "student": StudentRecord | None,
  "current_proposal": ScheduleProposal | None,
  "legis_objections": list[str],       # filled by legis_review
  "round_number": int,                 # increments on each Planner→Legis cycle
  "max_rounds": int,                   # configurable cap (default 3)
  "turns": list[NegotiationTurn],      # full transcript, streamed via SSE
  "outcome": "approved" | "no_solution" | "out_of_scope" | None,
  "final_answer": str | None,
}
```

---

## Demo Scenarios

Four pre-recorded sessions are included for offline/hackathon demo:

| File | Scenario |
|---|---|
| `01_regulation_question.json` | Student asks about max credit hours at GPA 2.8 |
| `02_happy_schedule.json` | Clean registration — Planner proposes, Legis approves in round 1 |
| `03_real_negotiation.json` | Planner proposes 18h, Legis vetoes (GPA too low), Planner revises to 15h |
| `04_at_risk_student.json` | Student on academic probation — Guardian flags, Legis enforces stricter rules |
