# Mokn Academic — Project Context for Future LLM Development

This document captures the current architecture and coding contracts of the `mokn-academic-monorepo` so future code changes remain compatible with the existing system behavior.

## 1) Folder Structure

Concise map of core runtime paths (backend and frontend) and where domain logic lives:

```text
mokn-academic-monorepo/
├── backend/
│   ├── src/mokn/
│   │   ├── main.py                     # FastAPI app bootstrap + router wiring
│   │   ├── config.py                   # pydantic-settings, logging config
│   │   ├── agents/
│   │   │   ├── orchestrator.py         # intent classify + final synthesis
│   │   │   ├── planner.py              # deterministic schedule + LLM ranking
│   │   │   ├── legis.py                # RAG-based regulation QA + veto
│   │   │   ├── guardian.py             # proactive risk messaging (not in graph)
│   │   │   └── base.py                 # shared agent abstraction
│   │   ├── negotiation/
│   │   │   ├── state.py                # LangGraph TypedDict state
│   │   │   ├── nodes.py                # graph node factories
│   │   │   ├── routing.py              # conditional edge routing functions
│   │   │   ├── graph.py                # StateGraph assembly + run/stream entrypoints
│   │   │   ├── constraint_extractor.py # objection -> hard constraints
│   │   │   └── store.py                # session persistence (JSON files)
│   │   ├── schemas/
│   │   │   ├── agent.py                # AgentContext/AgentResponse/VetoDecision
│   │   │   ├── negotiation.py          # turn/session/outcome protocol
│   │   │   ├── student.py              # student academic profile models
│   │   │   ├── course.py               # catalog/course section models
│   │   │   ├── schedule.py             # planner output contract
│   │   │   ├── regulations.py          # Legis RAG answer/chunk contracts
│   │   │   ├── veto_context.py         # Legis review context
│   │   │   └── guardian.py             # proactive risk contracts
│   │   ├── planning/
│   │   │   ├── optimizer.py            # deterministic schedule generation
│   │   │   ├── conflicts.py            # conflict detection primitives
│   │   │   └── errors.py               # planning-specific exceptions
│   │   ├── memory/
│   │   │   └── knowledge.py            # ChromaDB ingestion/query wrapper (RAG)
│   │   ├── data/
│   │   │   └── repository.py           # JSON-backed student/course repos
│   │   ├── llm/
│   │   │   └── gemini.py               # single Gemini client, retry, schema sanitize
│   │   ├── monitoring/
│   │   │   ├── risk_rules.py           # deterministic risk detectors
│   │   │   └── scanner.py              # scan orchestrator + async event stream
│   │   └── api/
│   │       ├── deps.py                 # FastAPI DI for agents/repos/store
│   │       └── routes/
│   │           ├── negotiate.py        # main orchestration API + SSE stream
│   │           ├── legis.py            # direct Legis endpoints
│   │           ├── planner.py          # direct Planner endpoints (plus deprecated path)
│   │           ├── students.py         # student profile endpoint for UI
│   │           └── guardian.py         # Guardian endpoints + SSE scan stream
│   ├── tests/                          # pytest unit/integration suites
│   ├── data/                           # mock data, demo sessions, persisted sessions
│   └── scripts/                        # ingestion/seed/demo helper scripts
├── dashboard/
│   ├── app/
│   │   ├── layout.tsx                  # App Router shell
│   │   └── page.tsx                    # main UI flow and state orchestration
│   ├── components/                     # agent cards/chat/input/sidebar/profile/guardian UI
│   │   ├── GuardianPanel.tsx           # live + offline proactive scan panel
│   │   ├── ProactiveAlertCard.tsx      # rendered Guardian alert card
│   │   └── RiskBadge.tsx               # severity badge used by Guardian cards
│   ├── lib/
│   │   ├── sse.ts                      # streaming client + SSE parser/dispatcher
│   │   ├── guardian.ts                 # Guardian scan SSE client + offline loader
│   │   ├── types.ts                    # TS contracts mirroring backend negotiation models
│   │   ├── negotiate.ts                # sessions list/get HTTP helpers
│   │   └── offline.ts                  # offline demo replay
│   └── public/demo_sessions/           # prerecorded sessions incl. guardian_proactive_scan.json
└── docs/
    └── master-spec.md                  # extended product and architecture spec
```

## 2) Tech Stack & Core Decisions

- **Backend framework:** FastAPI (`backend/src/mokn/main.py`) with typed request/response models.
- **Agent orchestration:** LangGraph `StateGraph` with cyclic edges (`backend/src/mokn/negotiation/graph.py`), not linear pipeline orchestration.
- **Validation/contracts:** Pydantic v2 across API payloads and internal contracts (`backend/src/mokn/schemas/*`), plus `pydantic-settings` in `config.py`.
- **LLM provider:** Google Gemini through `google-genai` SDK (`backend/src/mokn/llm/gemini.py`) as a single abstraction point.
- **RAG storage:** ChromaDB persistent local store (`backend/src/mokn/memory/knowledge.py`) using multilingual sentence-transformers embeddings.
- **Frontend:** Next.js (App Router) + TypeScript in `dashboard/`.
- **Realtime communication:** SSE over `POST /api/negotiate/stream`; parsed manually with `ReadableStream` in `dashboard/lib/sse.ts`.
- **Why these choices in code today:**
  - LangGraph chosen explicitly to support retry/veto loops.
  - Deterministic planner + LLM reasoning split prevents hallucinated schedule structures.
  - SSE chosen for one-way, server-to-client turn streaming.
  - Chroma chosen for local/offline-friendly RAG persistence.

## 3) Multi-Agent Flow (LangGraph)

### State definition

LangGraph uses a `TypedDict` state (`NegotiationState` in `backend/src/mokn/negotiation/state.py`) with key fields:

- Identity/input: `session_id`, `student_id`, `user_request`
- Routing: `intent` (`regulation_question` | `build_schedule` | `unknown`)
- Entities: `student`
- Planning controls: `target_hours`, `target_semester`, `round_number`, `max_rounds`
- Negotiation artifacts: `current_proposal`, `legis_objections`, `legis_answer`
- Output transcript/result: `turns`, `outcome`, `final_answer`

### Nodes (implemented)

`backend/src/mokn/negotiation/nodes.py` exposes factories for each graph node:

- `classify` (Orchestrator): classify user intent + extract hours/semester.
- `fetch_student`: hydrate student record for schedule path.
- `legis_only` (Legis): direct regulation QA path (no planner).
- `planner_propose` (Planner): generate schedule proposal each round; can apply hard constraints derived from prior Legis objections.
- `legis_review` (Legis): approve or veto planner’s recommended option.
- `synthesize` (Orchestrator): compose final Arabic student answer and terminal outcome.

### Edges and conditional edges

Graph assembly is in `backend/src/mokn/negotiation/graph.py`, routing logic in `backend/src/mokn/negotiation/routing.py`:

1. Entry: `classify`
2. `route_after_classify`:
   - `regulation_question` -> `legis_only`
   - `build_schedule` -> `fetch_student`
   - `unknown` -> `synthesize`
3. `fetch_student` -> `planner_propose`
4. `route_after_propose`:
   - if `current_proposal.no_solution` -> `synthesize`
   - else -> `legis_review`
5. `route_after_review`:
   - if last turn is `legis_approve` -> `synthesize`
   - if veto and rounds remain -> `planner_propose` (cyclic negotiation loop)
   - if veto and `round_number >= max_rounds` -> `synthesize` (escalation path)
6. `legis_only` -> `synthesize` -> `END`
7. `synthesize` -> `END`

### Veto power and negotiation loop semantics

- **Legis has effective veto power** in the schedule path via `legis_review`: a veto appends objections and drives the conditional edge back to planner.
- Planner receives `prior_objections` plus extracted `HardConstraints` from `constraint_extractor.py`, so retries are materially constrained.
- Orchestrator does not override Legis decisions directly; it finalizes messaging/outcome after convergence, no-solution, or max rounds.

### Guardian: parallel proactive layer (not in LangGraph)
Guardian operates as an independent runtime layer outside the negotiation graph by design. The negotiation graph remains: Orchestrator + Planner + Legis.
- **Why outside the graph:** negotiation is reactive (student initiates). Guardian is proactive (system initiates). Forcing Guardian into the cyclic graph would conflate two control flows.
- **Trust split:** `monitoring/risk_rules.py` is pure Python with no LLM — deterministic, fully testable, and the source of truth for who is at risk and why. `agents/guardian.py` only handles LLM prose: turning a precomputed `RiskAssessment` into a warm Arabic message + recommendations.
- **No veto power:** `GuardianAgent.can_veto()` explicitly returns `None`. Guardian suggests, never blocks.
- **Scan orchestration:** `monitoring/scanner.py` loads students from the repository, runs deterministic assessment, filters by severity (>= MEDIUM), then invokes the agent for each at-risk student. Yields events as an async generator for SSE consumption.
- **Failure mode:** If Gemini fails inside Guardian, the agent falls back to a deterministic message/recommendation built from the assessment alone, so a scan never crashes mid-stream.

## 4) Data Models (Schemas)

### Critical backend Pydantic models

From `backend/src/mokn/schemas/`:

- `Student` (`student.py`)
  - Core fields: `student_id`, `name`, `major`, `gpa`, `completed_credits`, `total_credits_required`
  - Academic details: `courses_completed`, `current_courses`, `attendance`, `preferences`, `memory_notes`
- `Course` / `CourseSection` (`course.py`)
  - Course identity and prerequisites, semester offering, sections with meeting days/times/capacity.
- `AgentContext` (`agent.py`)
  - `query`, `student_id`, `conversation_history`, `session_memory`, `metadata`
- `AgentResponse` (`agent.py`)
  - `agent`, `content`, optional `reasoning`, `confidence`, `timestamp`
- `VetoDecision` (`agent.py`)
  - `agent`, `veto`, `reason`, `violated_rules`, `suggestion`
- `ScheduleCourse` / `ScheduleOption` / `ScheduleProposal` (`schedule.py`)
  - Planner’s structured output bundle; includes `recommended_option`, warnings, and `no_solution`.
- `NegotiationTurn` (`negotiation.py`)
  - `turn_id`, `session_id`, `round_number`, `turn_type`, `agent`, `content`, `summary`, `timestamp`
- `NegotiationSession` (`negotiation.py`)
  - Session-level transcript + `intent`, `outcome`, `final_answer`, optional `final_proposal`.
- Guardian models (`schemas/guardian.py`, runtime-active, separate from negotiation graph):
  - `RiskSeverity` enum: `low | medium | high | critical`
  - `RiskFactor`: typed factor with `factor_type`, optional `course_code`, `description_ar`, `severity`, `evidence` dict
  - `RiskAssessment`: aggregate per student with `overall_severity`, `factors[]`, `summary_ar`
  - `GuardianRecommendation`: title/rationale (Arabic), `suggested_action` enum, `priority` (`info | advisory | urgent`)
  - `ProactiveAlert`: full surfaced alert — `alert_id`, student identity, assessment, recommendations, `message_ar`
  - `ScanReport`: scan metadata + `alerts[]`
- **Schema contract preserved:** Guardian was added without mutating `Student`. Prior-semester GPA is derived from `courses_completed` grouped by semester. Per-course current grade is read from existing fields. DN history is detected via substring search in the existing `memory_notes` field (`"محروم"`, `"حرمان"`, `"DN"`).

> Note on naming in request examples: `NegotiationTurn` and `AgentContext` exist exactly as named; `Student` and `Course` exist exactly as named.

### TypeScript interfaces and contract alignment

Main shared frontend contracts are in `dashboard/lib/types.ts`:

- `AgentName`, `TurnType`, `Outcome`
- `NegotiationTurn` and `NegotiationSession` (mirrors backend negotiation models)
- `ScheduleCourse`, `ScheduleOption`, `ScheduleProposal` (frontend representation of planner output)

Additional TS interface:

- `StudentProfile` in `dashboard/components/StudentProfileCard.tsx` mirrors `GET /api/students/{id}/profile` response shape from `students.py`.

Contract strategy in practice:

- Negotiation and schedule contracts are centralized in `dashboard/lib/types.ts`.
- Student profile contract is currently component-local, not exported from `lib/types.ts`.

## 5) API & Communication
### FastAPI endpoints
App includes routers from `main.py`:
- `GET /health`

Negotiation routes (`backend/src/mokn/api/routes/negotiate.py`):

- `POST /api/negotiate`
  - Runs full graph (`run_negotiation`) and returns one `NegotiationSession`.
- `POST /api/negotiate/stream`
  - SSE streaming endpoint using `StreamingResponse`.
  - Event sequence:
    - `session_start`
    - repeated `turn` events (each `NegotiationTurn`)
    - `done` with full `NegotiationSession`
    - or `error` on failure
- `GET /api/negotiate/sessions?limit=...`
- `GET /api/negotiate/sessions/{session_id}`
- `POST /api/negotiate/sessions/{session_id}/replay`

Legis routes (`api/routes/legis.py`):

- `POST /api/legis/ask`
- `POST /api/legis/validate-proposal`

Planner routes (`api/routes/planner.py`):

- `POST /api/planner/build-schedule`
- `POST /api/planner/validate-with-legis` (deprecated precursor)

Guardian routes (`api/routes/guardian.py`):
- `GET /api/guardian/health`
- `POST /api/guardian/assess/{student_id}`
  - Returns `ProactiveAlert | null`. Null when student is below MEDIUM severity.
- `POST /api/guardian/scan/run`
  - Synchronous full scan. Returns `ScanReport`.
- `GET /api/guardian/scan/stream`
  - SSE streaming variant. Event sequence:
    - `scan_started` — `{ scan_id, total_students, started_at }`
    - `student_assessed` — `{ student_id, severity, factor_count }` (one per student)
    - `alert` — full `ProactiveAlert` (only for at-risk students)
    - `scan_completed` — full `ScanReport`
    - or `error` on failure
  - Same SSE framing convention as `/api/negotiate/stream` (data: <json>\n\n).

Student routes (`api/routes/students.py`):

- `GET /api/students/{student_id}/profile`

### SSE transport and Next.js consumption
Frontend stream logic in `dashboard/lib/sse.ts`:
- Uses `fetch(.../api/negotiate/stream)` with `POST`.
- Reads `response.body.getReader()` and incrementally decodes chunks.
- Splits SSE frames by blank line (`\n\n`), parses `event:` and `data:`.
- Dispatches to handlers: `onSessionStart`, `onTurn`, `onDone`, `onError`.

Consumption path in `dashboard/app/page.tsx`:

- `runScenario()` calls `streamNegotiate(...)`.
- Each `turn` updates chat transcript and agent status indicators in real time.
- `done` stores the final session, refreshes session sidebar list.
- `error` marks stream failure and can trigger failover to offline demo sessions.

Persistence:

- Backend saves finalized sessions via `NegotiationStore` (`negotiation/store.py`) as one JSON file per session.
- Frontend replays historical sessions via `dashboard/lib/negotiate.ts`.

### Guardian SSE consumption
Frontend stream logic in `dashboard/lib/guardian.ts`:
- Reuses the same `ReadableStream` chunk-decoding pattern as `lib/sse.ts`.
- Async generator yields typed events: `scan_started | student_assessed | alert | scan_completed | error`.
- `dashboard/components/GuardianPanel.tsx` consumes the stream, prepends `ProactiveAlertCard` instances on each `alert` event, and shows scan progress on `student_assessed`.
- Offline fallback: `GuardianPanel` exposes a separate "📂 عرض Offline" entry that loads `dashboard/public/demo_sessions/guardian_proactive_scan.json` and replays alerts with staggered timing to mirror the live stream experience when backend is unreachable.

## 6) Code Conventions (Error Handling, Retries, Sanitization)
### Error handling style

- Route layer:
  - Uses `HTTPException` with semantic status codes (e.g., 404 for student/session missing, 400 for invalid `limit`, 502 for unparsable downstream agent payloads).
  - SSE endpoint catches broad exceptions, logs with `logger.exception`, and emits `error` SSE event to keep protocol stable.
- Domain/repository layer:
  - Custom exceptions (`StudentNotFound`, `CourseNotFound`, planner errors) for typed failure semantics.
  - Defensive fallbacks in loop-critical logic (e.g., no-solution handling, guard clauses on missing proposal/student in node functions).

### Retry and resiliency

- Gemini retries are centralized in `GeminiClient._call_with_retry` (`llm/gemini.py`) using Tenacity:
  - `stop_after_attempt(3)`
  - `wait_exponential(multiplier=1, min=1, max=8)`
  - retries all exceptions, then wraps failure as `GeminiError`.
- Additional resilience patterns:
  - Guardian resilience: Risk detection (`monitoring/risk_rules.py`) is LLM-free, so a Gemini outage cannot prevent a student from being flagged. If Gemini fails specifically during prose generation in `GuardianAgent.process()`, the agent returns a deterministic message + recommendations derived solely from the precomputed `RiskAssessment`; the scan continues as a degraded message, not a failed scan.
  - Constraint extraction failures return empty `HardConstraints` (do not crash negotiation).
  - Frontend stream handlers mark network/HTTP failures as recoverable and support offline demo failover.

### Gemini schema sanitization and structured-output discipline

- `GeminiClient.generate(...)` is the single LLM entrypoint for all agents.
- When `response_schema` is provided, it:
  - Builds Pydantic v2 JSON schema,
  - Applies `_sanitize_schema_for_gemini(...)`,
  - sends `response_mime_type="application/json"` and sanitized schema.
- Sanitizer behavior (`_sanitize_schema_for_gemini`):
  - Recursively removes `additionalProperties` keys to avoid Gemini structured-output validation errors.
- Structured-output convention:
  - Agents ask Gemini for typed schema responses where possible.
  - `AgentResponse.content` carries serialized structured payloads, not raw ad-hoc strings.
  - Free-text generation is primarily used for final Arabic student-facing synthesis (Orchestrator) or Guardian message prose.

---
## Quick Compatibility Checklist for Future Contributors

- Reuse existing Pydantic schemas first; avoid introducing parallel payload shapes.
- Keep new LangGraph routing pure in `routing.py` and side-effectful logic in `nodes.py`.
- Preserve Legis veto loop semantics for schedule negotiation unless intentionally redesigning governance.
- Route all Gemini calls through `GeminiClient`; do not instantiate SDK clients inside agents/routes.
- Maintain SSE event contract (`session_start`, `turn`, `done`, `error`) to avoid frontend breakage.
- If extending Guardian into runtime negotiation, explicitly update both graph wiring and frontend contracts.
- Guardian's risk decisions live in `risk_rules.py` (pure functions). Add new factor types there, not in the LLM prompt.
- If extending Guardian into runtime negotiation (e.g., letting Guardian inject risk context into a planner round), wire it through a new graph node — do not invoke Guardian from inside an existing node.
