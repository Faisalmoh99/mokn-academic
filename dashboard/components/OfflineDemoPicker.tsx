"use client";
import { OFFLINE_DEMOS, type DemoSession } from "@/lib/offline";

interface Props {
  onSelect: (demo: DemoSession) => void;
  disabled?: boolean;
}

export function OfflineDemoPicker({ onSelect, disabled }: Props) {
  return (
    <div className="p-4 border-t border-slate-200 bg-slate-50">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-700">
          📂 جلسات محفوظة (Offline)
        </h3>
        <span className="text-xs text-slate-500">للعرض بدون اتصال</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {OFFLINE_DEMOS.map((demo) => (
          <button
            key={demo.file}
            type="button"
            onClick={() => onSelect(demo)}
            disabled={disabled}
            className="text-right p-3 rounded-lg border border-slate-200 bg-white hover:border-amber-300 hover:bg-amber-50 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div className="text-xl mb-1" aria-hidden>
              {demo.emoji}
            </div>
            <div className="text-sm font-medium text-slate-800">{demo.label}</div>
            <div className="text-xs text-slate-500 mt-1">{demo.description}</div>
          </button>
        ))}
      </div>
    </div>
  );
}
