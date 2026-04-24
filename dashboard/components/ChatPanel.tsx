"use client";
import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { TurnBubble } from "./TurnBubble";
import { WelcomeSplash } from "./WelcomeSplash";
import type { NegotiationSession, NegotiationTurn } from "@/lib/types";

interface ChatPanelProps {
  turns: NegotiationTurn[];
  session: NegotiationSession | null;
  streaming: boolean;
}

const OUTCOME_LABEL: Record<string, string> = {
  approved: "✅ تمت الموافقة",
  escalated: "⚠️ تصعيد — يحتاج مرشد بشري",
  max_rounds: "⚠️ استُنفدت الجولات",
  regulation_only: "📖 إجابة لائحية",
  out_of_scope: "❓ خارج النطاق",
};

export function ChatPanel({ turns, session, streaming }: ChatPanelProps) {
  const endRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, session?.final_answer]);

  if (turns.length === 0 && !streaming && !session) {
    return <WelcomeSplash />;
  }

  return (
    <div className="chat-scroll flex-1 overflow-y-auto p-6 space-y-4">
      {turns.map((t) => (
        <TurnBubble key={t.turn_id} turn={t} />
      ))}
      {streaming && <ThinkingIndicator />}
      {session && session.final_answer && (
        <FinalAnswerCard session={session} />
      )}
      <div ref={endRef} />
    </div>
  );
}

function ThinkingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex items-center gap-2 text-sm text-slate-400"
    >
      <span className="flex gap-1">
        <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: "0s" }} />
        <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: "0.15s" }} />
        <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: "0.3s" }} />
      </span>
      <span>الوكلاء يتناقشون…</span>
    </motion.div>
  );
}

function FinalAnswerCard({ session }: { session: NegotiationSession }) {
  const label = session.outcome ? OUTCOME_LABEL[session.outcome] : null;
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-2xl border-2 border-slate-900 bg-slate-900 text-white p-5 shadow-md"
    >
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-base">الرد النهائي للطالب</h3>
        {label && (
          <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-medium">
            {label}
          </span>
        )}
      </div>
      <div className="text-sm leading-relaxed text-slate-200 space-y-3 [&_strong]:text-white [&_strong]:font-semibold [&_em]:text-amber-200 [&_ul]:list-disc [&_ul]:pr-5 [&_ul]:space-y-1 [&_ol]:list-decimal [&_ol]:pr-5 [&_ol]:space-y-1 [&_a]:text-sky-300 [&_a]:underline [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {session.final_answer}
        </ReactMarkdown>
      </div>
    </motion.div>
  );
}
