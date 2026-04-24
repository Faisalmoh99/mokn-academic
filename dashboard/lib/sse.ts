import type { NegotiationSession, NegotiationTurn } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type SSEHandler<T> = (data: T) => void;

export interface SSEErrorPayload {
  message: string;
  /** True when the failure is environmental (network/5xx) and a fallback
   *  to offline mode is sensible. False for parser/logic bugs. */
  recoverable?: boolean;
}

export interface SSEHandlers {
  onSessionStart?: SSEHandler<{
    session_id: string;
    request: string;
    student_id: string | null;
  }>;
  onTurn?: SSEHandler<NegotiationTurn>;
  onDone?: SSEHandler<NegotiationSession>;
  onError?: SSEHandler<SSEErrorPayload>;
}

/**
 * Open a streaming connection against /api/negotiate/stream and dispatch
 * events as they arrive. Resolves when the stream ends (done, error, or
 * underlying fetch is aborted).
 */
export async function streamNegotiate(
  body: { student_id?: string; request: string; max_rounds?: number },
  handlers: SSEHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/negotiate/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
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

      // SSE frames are separated by a blank line (\n\n). Anything after the
      // last blank line is a partial frame — keep it in the buffer.
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";

      for (const frame of frames) {
        const parsed = parseSSEFrame(frame);
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

function parseSSEFrame(raw: string): { type: string; data: unknown } | null {
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

function dispatch(type: string, data: unknown, h: SSEHandlers): void {
  switch (type) {
    case "session_start":
      h.onSessionStart?.(data as Parameters<NonNullable<SSEHandlers["onSessionStart"]>>[0]);
      return;
    case "turn":
      h.onTurn?.(data as NegotiationTurn);
      return;
    case "done":
      h.onDone?.(data as NegotiationSession);
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
