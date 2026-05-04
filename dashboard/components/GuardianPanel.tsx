"use client";
import clsx from "clsx";
import { useCallback, useRef, useState } from "react";
import { ProactiveAlertCard } from "./ProactiveAlertCard";
import { loadOfflineGuardianScan, streamGuardianScan } from "@/lib/guardian";
import type { GuardianScanReport, ProactiveAlert } from "@/lib/types";

interface Props {
  /** When the host page wants to inject a pre-recorded scan (offline mode). */
  injectedAlerts?: ProactiveAlert[];
  injectedReport?: GuardianScanReport | null;
  disabled?: boolean;
}

type ScanState = "idle" | "scanning" | "completed";

export function GuardianPanel({ injectedAlerts, injectedReport, disabled }: Props) {
  const [state, setState] = useState<ScanState>("idle");
  const [alerts, setAlerts] = useState<ProactiveAlert[]>([]);
  const [progress, setProgress] = useState<{ scanned: number; total: number }>({
    scanned: 0,
    total: 0,
  });
  const [report, setReport] = useState<GuardianScanReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Allow the host page to inject offline alerts without re-running a scan.
  const renderedAlerts = injectedAlerts ?? alerts;
  const renderedReport = injectedReport ?? report;

  const startScan = useCallback(async () => {
    if (disabled) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState("scanning");
    setAlerts([]);
    setReport(null);
    setError(null);
    setProgress({ scanned: 0, total: 0 });

    await streamGuardianScan(
      {
        onScanStarted: ({ total_students }) =>
          setProgress({ scanned: 0, total: total_students }),
        onStudentAssessed: () =>
          setProgress((p) => ({ ...p, scanned: p.scanned + 1 })),
        onAlert: (alert) => setAlerts((prev) => [alert, ...prev]),
        onScanCompleted: (r) => {
          setReport(r);
          setState("completed");
        },
        onError: (err) => {
          setError(err.message);
          setState("idle");
        },
      },
      controller.signal,
    ).catch((err: Error) => {
      if (err.name !== "AbortError") setError(err.message);
      setState("idle");
    });
  }, [disabled]);

  const playOffline = useCallback(async () => {
    if (disabled) return;
    abortRef.current?.abort();
    setState("scanning");
    setAlerts([]);
    setReport(null);
    setError(null);
    try {
      const offline = await loadOfflineGuardianScan();
      setProgress({
        scanned: 0,
        total: offline.total_students_scanned,
      });
      // Animate alerts in one-by-one to mimic a live stream.
      const queued = [...offline.alerts];
      let scanned = 0;
      while (scanned < offline.total_students_scanned) {
        await new Promise((r) => setTimeout(r, 350));
        scanned += 1;
        setProgress({ scanned, total: offline.total_students_scanned });
        // Drop one alert into the feed at progress milestones.
        const portion = Math.ceil(
          offline.total_students_scanned / Math.max(queued.length, 1),
        );
        if (queued.length > 0 && scanned % portion === 0) {
          const next = queued.shift();
          if (next) setAlerts((prev) => [next, ...prev]);
        }
      }
      // Flush any leftovers.
      for (const remaining of queued) {
        setAlerts((prev) => [remaining, ...prev]);
      }
      setReport(offline);
      setState("completed");
    } catch (err) {
      setError(err instanceof Error ? err.message : "offline replay failed");
      setState("idle");
    }
  }, [disabled]);

  const buttonLabel = (() => {
    if (state === "scanning") {
      return progress.total > 0
        ? `جاري الفحص… (${progress.scanned}/${progress.total})`
        : "جاري الفحص…";
    }
    if (state === "completed") return "إعادة تشغيل الفحص";
    return "تشغيل فحص الطلاب";
  })();

  return (
    <section className="border-t border-slate-200 bg-gradient-to-b from-white to-slate-50">
      <div className="px-6 py-5">
        <div className="flex items-start justify-between gap-3 mb-1">
          <div>
            <h3 className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <span aria-hidden>🛡️</span>
              <span>Guardian — الفحص الاستباقي</span>
            </h3>
            <p className="text-xs text-slate-500 mt-1 leading-relaxed">
              المراقب يفحص سجلات الطلاب بشكل دوري ويرفع التنبيهات قبل أن تتفاقم
              المشكلة. لا يفرض قراراً — يقترح فقط.
            </p>
          </div>
        </div>

        <div className="mt-3 grid grid-cols-1 sm:grid-cols-[1fr_auto] gap-2">
          <button
            type="button"
            onClick={startScan}
            disabled={disabled || state === "scanning"}
            className={clsx(
              "w-full rounded-lg px-4 py-2.5 text-sm font-medium transition-all",
              state === "scanning"
                ? "bg-slate-100 text-slate-500 cursor-wait"
                : "bg-slate-900 text-white hover:bg-slate-800",
              disabled && "opacity-50 cursor-not-allowed",
            )}
          >
            {buttonLabel}
          </button>
          <button
            type="button"
            onClick={playOffline}
            disabled={disabled || state === "scanning"}
            title="عرض جلسة محفوظة بدون اتصال"
            className={clsx(
              "rounded-lg px-3 py-2.5 text-xs font-medium border transition-all",
              "border-slate-200 bg-white text-slate-600 hover:border-amber-300 hover:bg-amber-50",
              (disabled || state === "scanning") && "opacity-50 cursor-not-allowed",
            )}
          >
            📂 عرض Offline
          </button>
        </div>

        {error && (
          <p className="mt-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
            ⚠️ {error}
          </p>
        )}

        {renderedReport && state === "completed" && !injectedReport && (
          <p className="mt-2 text-xs text-slate-500">
            اكتمل الفحص — {renderedReport.students_at_risk} من{" "}
            {renderedReport.total_students_scanned} طالباً يحتاجون متابعة.
          </p>
        )}
      </div>

      <div className="px-6 pb-6 space-y-3">
        {renderedAlerts.length === 0 ? (
          <EmptyState scanning={state === "scanning"} />
        ) : (
          renderedAlerts.map((alert) => (
            <ProactiveAlertCard key={alert.alert_id} alert={alert} />
          ))
        )}
      </div>
    </section>
  );
}

function EmptyState({ scanning }: { scanning: boolean }) {
  return (
    <div className="rounded-lg border border-dashed border-slate-200 bg-white px-4 py-6 text-center">
      <p className="text-xs text-slate-500 leading-relaxed">
        {scanning
          ? "جاري فحص السجلات… ستظهر التنبيهات هنا فور رصدها."
          : "لا توجد تنبيهات حالياً. اضغط الزر لبدء الفحص الاستباقي."}
      </p>
    </div>
  );
}
