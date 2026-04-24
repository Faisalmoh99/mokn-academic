"use client";

export function WelcomeSplash() {
  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-lg text-center space-y-6">
        <div className="text-6xl" aria-hidden>🎓</div>
        <div>
          <h1 className="text-3xl font-bold text-slate-900">مُكِن أكاديمي</h1>
          <p className="text-slate-500 mt-2">
            نظام تفاوضي متعدد الوكلاء للإرشاد الأكاديمي
          </p>
        </div>

        <div className="bg-gradient-to-br from-indigo-50 to-amber-50 rounded-xl p-6 text-right space-y-3">
          <div className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden>🎯</span>
            <div>
              <div className="font-semibold text-slate-800">Orchestrator</div>
              <div className="text-sm text-slate-600">
                يستقبل طلبك ويقود التفاوض
              </div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden>⚖️</span>
            <div>
              <div className="font-semibold text-slate-800">Legis</div>
              <div className="text-sm text-slate-600">
                حارس اللوائح ويملك حق النقض
              </div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden>📅</span>
            <div>
              <div className="font-semibold text-slate-800">Planner</div>
              <div className="text-sm text-slate-600">
                يبني الجداول ويستجيب للاعتراضات
              </div>
            </div>
          </div>
        </div>

        <p className="text-sm text-slate-500">اختر سيناريو من الأعلى لبدء العرض</p>
      </div>
    </div>
  );
}
