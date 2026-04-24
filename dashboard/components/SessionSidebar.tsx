"use client";
import { useEffect, useState } from "react";
import clsx from "clsx";
import { listSessions, getSession } from "@/lib/negotiate";
import type { NegotiationSession } from "@/lib/types";

interface SessionSidebarProps {
  onReplay: (session: NegotiationSession) => void;
  disabled: boolean;
  refreshToken: number;
}

const OUTCOME_BADGE: Record<string, { label: string; tone: string }> = {
  approved: { label: "موافقة", tone: "bg-emerald-100 text-emerald-800" },
  escalated: { label: "تصعيد", tone: "bg-amber-100 text-amber-800" },
  max_rounds: { label: "استُنفدت", tone: "bg-amber-100 text-amber-800" },
  regulation_only: { label: "لائحة", tone: "bg-slate-100 text-slate-700" },
  out_of_scope: { label: "غير واضح", tone: "bg-slate-100 text-slate-500" },
};

export function SessionSidebar({ onReplay, disabled, refreshToken }: SessionSidebarProps) {
  const [sessions, setSessions] = useState<NegotiationSession[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    listSessions(20)
      .then((items) => {
        if (!cancelled) setSessions(items);
      })
      .catch(() => {
        /* ignore */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, refreshToken]);

  const handleClick = async (id: string) => {
    try {
      const full = await getSession(id);
      onReplay(full);
    } catch {
      /* ignore */
    }
  };

  return (
    <div className="border-t border-slate-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-6 py-3 text-sm font-medium text-slate-700 hover:bg-slate-50"
      >
        <span className="flex items-center gap-2">
          <span aria-hidden>📂</span>
          <span>الجلسات السابقة</span>
        </span>
        <span className="text-slate-400 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="max-h-64 overflow-y-auto chat-scroll px-4 pb-4 space-y-2">
          {loading && <p className="text-xs text-slate-400 px-2">جارٍ التحميل…</p>}
          {!loading && sessions.length === 0 && (
            <p className="text-xs text-slate-400 px-2">لا توجد جلسات سابقة بعد.</p>
          )}
          {sessions.map((s) => {
            const badge = s.outcome ? OUTCOME_BADGE[s.outcome] : null;
            const ts = new Date(s.started_at);
            return (
              <button
                key={s.session_id}
                type="button"
                disabled={disabled}
                onClick={() => handleClick(s.session_id)}
                className={clsx(
                  "w-full text-start rounded-lg border border-slate-200 bg-white p-3 transition-all",
                  disabled ? "opacity-50 cursor-not-allowed" : "hover:border-slate-400 hover:shadow-sm",
                )}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-[10px] text-slate-400">
                    {ts.toLocaleString("ar-SA", { dateStyle: "short", timeStyle: "short" })}
                  </span>
                  {badge && (
                    <span className={clsx("rounded-full px-2 py-0.5 text-[10px]", badge.tone)}>
                      {badge.label}
                    </span>
                  )}
                </div>
                <p className="text-xs text-slate-700 line-clamp-2 leading-relaxed">
                  {s.user_request}
                </p>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
