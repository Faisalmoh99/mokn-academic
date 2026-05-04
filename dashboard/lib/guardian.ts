import { API_BASE } from "./sse";
import type { GuardianScanReport, ProactiveAlert, RiskSeverity } from "./types";

export const GUARDIAN_OFFLINE_FILE = "guardian_proactive_scan.json";

/** Load a pre-captured scan report from /public/demo_sessions/ for offline demo. */
export async function loadOfflineGuardianScan(): Promise<GuardianScanReport> {
  const response = await fetch(`/demo_sessions/${GUARDIAN_OFFLINE_FILE}`);
  if (!response.ok) {
    throw new Error(`Failed to load offline scan: ${response.status}`);
  }
  return response.json();
}

export interface GuardianScanStartedData {
  scan_id: string;
  total_students: number;
  started_at: string;
}

export interface GuardianStudentAssessedData {
  student_id: string;
  severity: RiskSeverity;
  factor_count: number;
}

export interface GuardianHandlers {
  onScanStarted?: (data: GuardianScanStartedData) => void;
  onStudentAssessed?: (data: GuardianStudentAssessedData) => void;
  onAlert?: (alert: ProactiveAlert) => void;
  onScanCompleted?: (report: GuardianScanReport) => void;
  onError?: (err: { message: string; recoverable?: boolean }) => void;
}

/**
 * Stream a Guardian scan from /api/guardian/scan/stream. Mirrors the SSE
 * frame-parsing approach in lib/sse.ts so we don't fork the parser.
 */
export async function streamGuardianScan(
  handlers: GuardianHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/guardian/scan/stream`, {
      method: "GET",
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    handlers.onError?.({
      message: err instanceof Error ? err.message : "Network error",
      recoverable: true,
    });
    return;
  }

  if (!response.ok || !response.body) {
    handlers.onError?.({
      message: `HTTP ${response.status}`,
      recoverable: true,
    });
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const parsed = parseFrame(frame);
        if (!parsed) continue;
        dispatch(parsed.type, parsed.data, handlers);
      }
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    handlers.onError?.({
      message: err instanceof Error ? err.message : "Stream error",
      recoverable: true,
    });
  }
}

function parseFrame(raw: string): { type: string; data: unknown } | null {
  let eventType = "";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event: ")) eventType = line.slice(7).trim();
    else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
  }
  if (!eventType || dataLines.length === 0) return null;
  try {
    return { type: eventType, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

function dispatch(type: string, data: unknown, h: GuardianHandlers): void {
  switch (type) {
    case "scan_started":
      h.onScanStarted?.(data as GuardianScanStartedData);
      return;
    case "student_assessed":
      h.onStudentAssessed?.(data as GuardianStudentAssessedData);
      return;
    case "alert":
      h.onAlert?.(data as ProactiveAlert);
      return;
    case "scan_completed":
      h.onScanCompleted?.(data as GuardianScanReport);
      return;
    case "error": {
      const payload = data as { message?: string };
      h.onError?.({
        message: payload.message ?? "Unknown error",
        recoverable: true,
      });
      return;
    }
  }
}
