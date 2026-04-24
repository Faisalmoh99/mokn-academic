"use client";
import { OFFLINE_DEMOS, type DemoSession } from "@/lib/offline";

interface Props {
  open: boolean;
  onClose: () => void;
  onSelectOffline: (demo: DemoSession) => void;
}

export function FailoverDialog({ open, onClose, onSelectOffline }: Props) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 bg-slate-900/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="text-4xl mb-3 text-center" aria-hidden>⚠️</div>
        <h2 className="text-lg font-bold text-slate-900 text-center mb-2">
          تعذّر الاتصال بالخادم
        </h2>
        <p className="text-sm text-slate-600 text-center mb-4 leading-relaxed">
          قد يكون الخادم مشغولاً أو الإنترنت غير مستقر. يمكنك عرض إحدى الجلسات
          المحفوظة بدلاً من ذلك:
        </p>
        <div className="space-y-2">
          {OFFLINE_DEMOS.map((demo) => (
            <button
              key={demo.file}
              type="button"
              onClick={() => {
                onClose();
                onSelectOffline(demo);
              }}
              className="w-full text-right p-3 rounded-lg border border-slate-200 hover:border-amber-300 hover:bg-amber-50 transition"
            >
              <span className="text-xl ml-2" aria-hidden>{demo.emoji}</span>
              <span className="font-medium text-slate-800">{demo.label}</span>
              <div className="text-xs text-slate-500 mt-1">{demo.description}</div>
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={onClose}
          className="w-full mt-4 py-2 text-sm text-slate-500 hover:text-slate-700"
        >
          إغلاق
        </button>
      </div>
    </div>
  );
}
