"use client";
import clsx from "clsx";
import type { RiskSeverity } from "@/lib/types";

interface RiskBadgeProps {
  severity: RiskSeverity;
  pulse?: boolean;
  size?: "sm" | "md";
}

const SEVERITY_LABEL: Record<RiskSeverity, string> = {
  low: "منخفض",
  medium: "متوسط",
  high: "مرتفع",
  critical: "حرج",
};

const SEVERITY_TONE: Record<RiskSeverity, string> = {
  low: "bg-slate-100 text-slate-700 border-slate-200",
  medium: "bg-amber-100 text-amber-800 border-amber-200",
  high: "bg-orange-100 text-orange-800 border-orange-200",
  critical: "bg-red-100 text-red-800 border-red-300",
};

export function RiskBadge({ severity, pulse, size = "md" }: RiskBadgeProps) {
  const isCritical = severity === "critical";
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-2.5 py-1 text-xs",
        SEVERITY_TONE[severity],
        pulse && isCritical && "animate-pulse",
      )}
    >
      <span
        className={clsx(
          "rounded-full",
          size === "sm" ? "h-1.5 w-1.5" : "h-2 w-2",
          severity === "low" && "bg-slate-400",
          severity === "medium" && "bg-amber-500",
          severity === "high" && "bg-orange-500",
          severity === "critical" && "bg-red-500",
        )}
        aria-hidden
      />
      {SEVERITY_LABEL[severity]}
    </span>
  );
}
