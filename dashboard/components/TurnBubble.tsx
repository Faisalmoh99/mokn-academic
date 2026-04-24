"use client";
import clsx from "clsx";
import { motion } from "framer-motion";
import type { NegotiationTurn, ScheduleOption } from "@/lib/types";

interface TurnBubbleProps {
  turn: NegotiationTurn;
}

const AGENT_ICON: Record<string, string> = {
  Orchestrator: "🎯",
  Planner: "📅",
  Legis: "⚖️",
  Guardian: "🛡️",
};

export function TurnBubble({ turn }: TurnBubbleProps) {
  const isUser = turn.turn_type === "user_request";
  const isVeto = turn.turn_type === "legis_veto";
  const isApprove = turn.turn_type === "legis_approve";
  const isPlanner = turn.turn_type === "planner_propose";
  const isSynthesize = turn.turn_type === "orchestrator_synthesize";

  const alignment = isUser ? "items-start" : "items-end";

  const bubbleTone = clsx(
    "rounded-2xl px-4 py-3 shadow-sm max-w-[85%]",
    isUser && "bg-sky-500 text-white",
    isVeto && "bg-red-50 border border-red-200 border-r-4 border-r-red-500 text-slate-900",
    isApprove &&
      "bg-emerald-50 border border-emerald-200 border-r-4 border-r-emerald-500 text-slate-900",
    isPlanner && "bg-indigo-50 border border-indigo-200 text-slate-900",
    !isUser && !isVeto && !isApprove && !isPlanner && "bg-white border border-slate-200 text-slate-800",
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className={clsx("flex flex-col gap-1", alignment)}
    >
      <div className="flex items-center gap-2 text-xs text-slate-500">
        {!isUser && turn.agent && (
          <>
            <span aria-hidden>{AGENT_ICON[turn.agent] ?? "•"}</span>
            <span className="font-medium text-slate-700">{turn.agent}</span>
          </>
        )}
        {isUser && <span className="font-medium text-slate-700">الطالب</span>}
        {turn.round_number > 0 && (
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
            جولة {turn.round_number}
          </span>
        )}
        {isVeto && <span className="text-red-600 font-semibold">🚫 اعتراض</span>}
        {isApprove && <span className="text-emerald-600 font-semibold">✅ موافقة</span>}
      </div>
      <div className={bubbleTone}>
        <p className="text-sm leading-relaxed whitespace-pre-wrap">
          {turn.summary}
        </p>
        {isPlanner && <PlannerDetails content={turn.content} />}
        {isSynthesize && <SynthesizeDetails content={turn.content} />}
      </div>
    </motion.div>
  );
}

function PlannerDetails({ content }: { content: Record<string, unknown> }) {
  const options = (content.options as ScheduleOption[] | undefined) ?? [];
  const recommended = content.recommended_option as string | undefined;
  const noSolution = content.no_solution as boolean | undefined;

  if (noSolution || options.length === 0) return null;

  return (
    <div className="mt-3 space-y-2 border-t border-indigo-200 pt-3">
      {options.map((opt) => {
        const courseCodes = (opt.courses ?? []).map((c) => c.course_code).join(" · ");
        return (
          <div
            key={opt.label}
            className={clsx(
              "rounded-lg px-3 py-2 text-xs",
              opt.label === recommended
                ? "bg-indigo-100 text-indigo-900 font-medium"
                : "bg-white text-slate-700",
            )}
          >
            <div className="flex items-center justify-between gap-2">
              <span>
                {opt.label === recommended && "⭐ "}
                الخيار {opt.label} — {opt.total_credits} ساعة
              </span>
            </div>
            <div className="mt-1 text-slate-500 text-[11px]">{courseCodes}</div>
          </div>
        );
      })}
    </div>
  );
}

function SynthesizeDetails({ content }: { content: Record<string, unknown> }) {
  const finalAnswer = content.final_answer as string | undefined;
  if (!finalAnswer) return null;
  return (
    <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-700 leading-relaxed whitespace-pre-wrap">
      {finalAnswer}
    </div>
  );
}
