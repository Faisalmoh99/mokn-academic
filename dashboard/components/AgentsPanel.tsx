"use client";
import { AgentCard } from "./AgentCard";
import type { AgentName, AgentStatus, TurnType } from "@/lib/types";

interface AgentsPanelProps {
  currentTurn: TurnType | null;
  lastAgent: AgentName | null;
  streaming: boolean;
}

const AGENTS: {
  name: AgentName;
  role: string;
  icon: string;
  disabled?: boolean;
}[] = [
  { name: "Orchestrator", role: "المنسق — يفهم الطلب ويصوغ الرد", icon: "🎯" },
  { name: "Legis", role: "حارس اللوائح — يراجع كل جدول", icon: "⚖️" },
  { name: "Planner", role: "مهندس الجداول — يرشح الخيارات", icon: "📅" },
  { name: "Guardian", role: "المراقب الاستباقي — يفحص ويُنبّه", icon: "🛡️" },
];

export function AgentsPanel({ currentTurn, lastAgent, streaming }: AgentsPanelProps) {
  return (
    <aside className="h-full overflow-y-auto p-6 space-y-4">
      <div className="mb-2">
        <h2 className="text-lg font-semibold text-slate-800">فريق الوكلاء</h2>
        <p className="text-sm text-slate-500">
          {streaming ? "النقاش جارٍ…" : "النظام جاهز للانطلاق"}
        </p>
      </div>
      {AGENTS.map((a) => (
        <AgentCard
          key={a.name}
          name={a.name}
          role={a.role}
          icon={a.icon}
          disabled={a.disabled}
          status={resolveStatus({
            agent: a.name,
            currentTurn,
            lastAgent,
            streaming,
            disabled: a.disabled,
          })}
        />
      ))}
    </aside>
  );
}

function resolveStatus({
  agent,
  currentTurn,
  lastAgent,
  streaming,
  disabled,
}: {
  agent: AgentName;
  currentTurn: TurnType | null;
  lastAgent: AgentName | null;
  streaming: boolean;
  disabled?: boolean;
}): AgentStatus {
  if (disabled) return "idle";
  if (!streaming || !currentTurn || lastAgent !== agent) return "idle";

  if (agent === "Legis") {
    if (currentTurn === "legis_veto") return "vetoing";
    if (currentTurn === "legis_approve") return "approving";
  }
  if (
    currentTurn === "orchestrator_classify" ||
    currentTurn === "orchestrator_synthesize" ||
    currentTurn === "planner_propose" ||
    currentTurn === "legis_review"
  ) {
    return "thinking";
  }
  return "active";
}
