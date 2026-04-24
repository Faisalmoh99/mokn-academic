"use client";

interface Props {
  onExit: () => void;
}

export function OfflineModeBanner({ onExit }: Props) {
  return (
    <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between text-sm">
      <div className="flex items-center gap-2 text-amber-900">
        <span aria-hidden>📂</span>
        <span>الوضع: جلسة محفوظة (بدون اتصال بالخادم)</span>
      </div>
      <button
        type="button"
        onClick={onExit}
        className="text-amber-700 hover:text-amber-900 underline"
      >
        العودة للوضع المباشر
      </button>
    </div>
  );
}
