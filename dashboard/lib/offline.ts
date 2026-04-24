import type { NegotiationSession, NegotiationTurn } from "./types";

export interface DemoSession {
  file: string;
  label: string;
  description: string;
  emoji: string;
}

export const OFFLINE_DEMOS: DemoSession[] = [
  {
    file: "01_regulation_question.json",
    label: "سؤال لوائح",
    description: "Legis يجيب مباشرة",
    emoji: "⚖️",
  },
  {
    file: "02_happy_schedule.json",
    label: "جدول ناجح",
    description: "طالب ممتاز — جولة واحدة",
    emoji: "✅",
  },
  {
    file: "03_real_negotiation.json",
    label: "تفاوض حقيقي",
    description: "Legis يعترض — Planner يعدل",
    emoji: "🔥",
  },
  {
    file: "04_at_risk_student.json",
    label: "طالب في خطر",
    description: "تنبيهات الغياب",
    emoji: "⚠️",
  },
];

export async function loadOfflineSession(
  file: string,
): Promise<NegotiationSession> {
  const response = await fetch(`/demo_sessions/${file}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${file}: ${response.status}`);
  }
  return response.json();
}

/**
 * Replay a saved NegotiationSession, yielding each turn with pacing derived
 * from the original timestamps (capped so replay never feels boring or
 * unreadable). Respects an AbortSignal so the caller can cancel mid-stream.
 */
export async function* replayOfflineSession(
  session: NegotiationSession,
  speedMultiplier = 1.0,
  abortSignal?: AbortSignal,
): AsyncGenerator<NegotiationTurn> {
  if (!session.turns.length) return;

  for (let i = 0; i < session.turns.length; i++) {
    if (abortSignal?.aborted) return;

    const turn = session.turns[i];

    if (i > 0) {
      const prevTs = new Date(session.turns[i - 1].timestamp).getTime();
      const currTs = new Date(turn.timestamp).getTime();
      const realGap = currTs - prevTs;
      const cappedGap = Math.min(Math.max(realGap, 500), 3000) / speedMultiplier;

      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(resolve, cappedGap);
        const onAbort = () => {
          clearTimeout(timeout);
          reject(new DOMException("Aborted", "AbortError"));
        };
        abortSignal?.addEventListener("abort", onAbort, { once: true });
      });
    }

    yield turn;
  }
}
