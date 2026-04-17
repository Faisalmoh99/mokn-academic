# Mokn Academic (مُكِن أكاديمي)

Multi-agent academic advisor for Agenticthon 2026. Four autonomous agents
(Orchestrator, Legis, Planner, Guardian) negotiate to replace 80% of an
academic advisor's workload — delivered over WhatsApp.

Full architecture, scenarios, and timeline: [`docs/master-spec.md`](docs/master-spec.md).

## Current status — Session 1

- Project scaffolding
- `Legis` agent (regulations-of-record, Arabic RAG over university handbook PDFs)
- FastAPI surface for `/api/legis/ask` and `/api/legis/validate-proposal`
- Chroma-backed KnowledgeBase with multilingual embeddings
- Gemini 1.5 Pro client with structured Pydantic output
- Test suite with mocked LLM

The other three agents, the negotiation protocol, WhatsApp, and the dashboard
are scheduled for Sessions 2–4.

## Quick start

```bash
git clone <repo> && cd mokn-academic
cp .env.example .env                # then edit: set GEMINI_API_KEY
pip install -r requirements.txt
python scripts/ingest_regulations.py --pdf data/regulations/handbook.pdf --collection regulations
uvicorn src.mokn.main:app --reload
```

Ask Legis a question:

```bash
curl -X POST http://localhost:8000/api/legis/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "كم الحد الأقصى للساعات المسموح بها للطالب بمعدل 2.8؟"}'
```

Run tests:

```bash
pytest tests/ -v
```

## Layout

```
src/mokn/
  agents/       # BaseAgent + Legis
  api/routes/   # FastAPI routes per agent
  llm/          # GeminiClient — single LLM entrypoint
  memory/       # Chroma-backed KnowledgeBase
  schemas/      # Pydantic models (agent, negotiation, regulations)
  config.py     # pydantic-settings
  main.py       # FastAPI app
```
