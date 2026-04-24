"use client";
import clsx from "clsx";
import type { AgentStatus } from "@/lib/types";

interface AgentCardProps {
  name: string;
  role: string;
  icon: string;
  status: AgentStatus;
  disabled?: boolean;
}

const STATUS_LABEL: Record<AgentStatus, string> = {
  idle: "في الانتظار",
  thinking: "يفكر…",
  active: "نشط",
  vetoing: "اعتراض",
  approving: "موافقة",
};

const STATUS_COLOR: Record<AgentStatus, string> = {
  idle: "bg-slate-300",
  thinking: "bg-indigo-500",
  active: "bg-indigo-500",
  vetoing: "bg-red-500",
  approving: "bg-emerald-500",
};

const STATUS_RING: Record<AgentStatus, string> = {
  idle: "ring-1 ring-slate-200",
  thinking: "ring-2 ring-indigo-300",
  active: "ring-2 ring-indigo-300",
  vetoing: "ring-2 ring-red-300",
  approving: "ring-2 ring-emerald-300",
};

export function AgentCard({ name, role, icon, status, disabled }: AgentCardProps) {
  const isLive = !disabled && status !== "idle";
  return (
    <div
      className={clsx(
        "flex items-center gap-4 rounded-xl bg-white p-4 shadow-sm transition-all duration-300",
        disabled ? "opacity-50" : STATUS_RING[status],
        isLive && status === "thinking" && "animate-thinking",
        isLive && status === "vetoing" && "animate-veto",
      )}
    >
      <div
        className={clsx(
          "flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-2xl",
          disabled ? "bg-slate-100" : "bg-slate-50",
        )}
      >
        <span aria-hidden>{icon}</span>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <h3 className="font-semibold text-slate-800 text-base">{name}</h3>
          {disabled && (
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
              قريباً
            </span>
          )}
        </div>
        <p className="text-sm text-slate-500 truncate">{role}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <span
          className={clsx(
            "h-2.5 w-2.5 rounded-full",
            STATUS_COLOR[status],
            isLive && (status === "thinking" || status === "active") && "animate-pulse",
          )}
        />
        <span className="text-xs text-slate-500 min-w-[3rem] text-start">
          {disabled ? "—" : STATUS_LABEL[status]}
        </span>
      </div>
    </div>
  );
}
