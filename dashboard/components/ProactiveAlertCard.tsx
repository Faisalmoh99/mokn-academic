"use client";
import clsx from "clsx";
import { motion } from "framer-motion";
import { useState } from "react";
import { RiskBadge } from "./RiskBadge";
import type {
  GuardianRecommendation,
  GuardianRecommendationPriority,
  ProactiveAlert,
  RiskFactor,
  RiskSeverity,
} from "@/lib/types";

interface ProactiveAlertCardProps {
  alert: ProactiveAlert;
}

const PRIORITY_TONE: Record<GuardianRecommendationPriority, string> = {
  info: "bg-slate-50 text-slate-700 border-slate-200",
  advisory: "bg-indigo-50 text-indigo-800 border-indigo-200",
  urgent: "bg-red-50 text-red-800 border-red-200",
};

const PRIORITY_LABEL: Record<GuardianRecommendationPriority, string> = {
  info: "للعلم",
  advisory: "موصى به",
  urgent: "عاجل",
};

const ACCENT_BORDER: Record<RiskSeverity, string> = {
  low: "border-r-slate-400",
  medium: "border-r-amber-500",
  high: "border-r-orange-500",
  critical: "border-r-red-500",
};

export function ProactiveAlertCard({ alert }: ProactiveAlertCardProps) {
  const [showFactors, setShowFactors] = useState(false);
  const severity = alert.assessment.overall_severity;
  const triggered = new Date(alert.triggered_at).toLocaleTimeString("ar-SA", {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={clsx(
        "rounded-xl bg-white border border-slate-200 border-r-4 shadow-sm overflow-hidden",
        ACCENT_BORDER[severity],
      )}
    >
      <div className="p-4">
        <div className="flex items-center justify-between gap-2 mb-2">
          <div className="flex items-center gap-2 min-w-0">
            <RiskBadge severity={severity} pulse />
            <span className="font-semibold text-slate-800 text-sm truncate">
              {alert.student_name}
            </span>
            <span className="text-[10px] text-slate-400">
              {alert.student_id}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 shrink-0">{triggered}</span>
        </div>

        <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">
          {alert.message_ar}
        </p>

        {alert.recommendations.length > 0 && (
          <div className="mt-3 space-y-2">
            {alert.recommendations.map((rec, idx) => (
              <RecommendationRow key={`${alert.alert_id}-${idx}`} rec={rec} />
            ))}
          </div>
        )}

        {alert.assessment.factors.length > 0 && (
          <div className="mt-3 border-t border-slate-100 pt-3">
            <button
              type="button"
              onClick={() => setShowFactors((s) => !s)}
              className="text-xs font-medium text-slate-500 hover:text-slate-700 flex items-center gap-1"
            >
              <span aria-hidden>{showFactors ? "▾" : "▸"}</span>
              تفاصيل المؤشرات ({alert.assessment.factors.length})
            </button>
            {showFactors && (
              <ul className="mt-2 space-y-1.5">
                {alert.assessment.factors.map((factor, idx) => (
                  <FactorRow
                    key={`${alert.alert_id}-f-${idx}`}
                    factor={factor}
                  />
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function RecommendationRow({ rec }: { rec: GuardianRecommendation }) {
  return (
    <div
      className={clsx(
        "rounded-lg border px-3 py-2",
        PRIORITY_TONE[rec.priority],
      )}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-xs font-semibold">{rec.title_ar}</span>
        <span className="text-[10px] uppercase tracking-wide opacity-75">
          {PRIORITY_LABEL[rec.priority]}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed opacity-90">{rec.rationale_ar}</p>
    </div>
  );
}

function FactorRow({ factor }: { factor: RiskFactor }) {
  return (
    <li className="flex items-start gap-2 text-xs text-slate-600">
      <RiskBadge severity={factor.severity} size="sm" />
      <div className="flex-1 min-w-0">
        <p className="leading-relaxed">{factor.description_ar}</p>
      </div>
    </li>
  );
}
