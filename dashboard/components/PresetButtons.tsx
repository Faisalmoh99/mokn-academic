"use client";
import clsx from "clsx";
import type { ScenarioRequest } from "@/lib/types";

interface PresetButtonsProps {
  onSelect: (req: ScenarioRequest) => void;
  disabled: boolean;
}

const PRESETS: (ScenarioRequest & {
  label: string;
  description: string;
  emoji: string;
  tone: string;
})[] = [
  {
    label: "سؤال عن اللوائح",
    description: "Legis يجيب مباشرة",
    emoji: "⚖️",
    tone: "border-slate-200 hover:border-slate-400 bg-white",
    request: "كم الحد الأقصى للساعات لطالب معدله 3.5؟",
  },
  {
    label: "بناء جدول ناجح",
    description: "طالب ممتاز — جولة واحدة",
    emoji: "✅",
    tone: "border-emerald-200 hover:border-emerald-400 bg-emerald-50/40",
    request: "ابني لي جدول 12 ساعة",
    student_id: "442001234",
  },
  {
    label: "تفاوض حقيقي",
    description: "طالب GPA 2.1 — تفاوض على الحد المسموح",
    emoji: "🔥",
    tone: "border-amber-200 hover:border-amber-400 bg-amber-50/40",
    request: "ابني لي جدول 21 ساعة",
    student_id: "442005678",
  },
];

export function PresetButtons({ onSelect, disabled }: PresetButtonsProps) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3 p-6 border-b border-slate-200 bg-slate-50/50">
      {PRESETS.map((p) => (
        <button
          key={p.label}
          type="button"
          disabled={disabled}
          onClick={() => onSelect({ request: p.request, student_id: p.student_id })}
          className={clsx(
            "group rounded-xl border-2 p-4 text-start transition-all",
            p.tone,
            disabled && "opacity-50 cursor-not-allowed",
            !disabled && "hover:shadow-md",
          )}
        >
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xl" aria-hidden>{p.emoji}</span>
            <span className="font-semibold text-slate-800 text-sm">{p.label}</span>
          </div>
          <p className="text-xs text-slate-500 leading-relaxed">
            {p.description}
          </p>
          <p className="mt-2 text-xs text-slate-600 font-medium line-clamp-1">
            «{p.request}»
          </p>
        </button>
      ))}
    </div>
  );
}
