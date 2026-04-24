"use client";
import { useState } from "react";
import type { ScenarioRequest } from "@/lib/types";

interface InputBarProps {
  onSubmit: (req: ScenarioRequest) => void;
  disabled: boolean;
}

export function InputBar({ onSubmit, disabled }: InputBarProps) {
  const [request, setRequest] = useState("");
  const [studentId, setStudentId] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = request.trim();
    if (!trimmed || disabled) return;
    onSubmit({
      request: trimmed,
      student_id: studentId.trim() || undefined,
    });
    setRequest("");
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="border-t border-slate-200 bg-white p-4 flex items-center gap-3"
    >
      <input
        type="text"
        value={studentId}
        onChange={(e) => setStudentId(e.target.value)}
        placeholder="الرقم الجامعي (اختياري)"
        disabled={disabled}
        className="w-40 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-300 disabled:opacity-50"
      />
      <input
        type="text"
        value={request}
        onChange={(e) => setRequest(e.target.value)}
        placeholder="اكتب طلبك بالعربية…"
        disabled={disabled}
        className="flex-1 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-slate-400 disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !request.trim()}
        className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {disabled ? "…" : "إرسال"}
      </button>
    </form>
  );
}
