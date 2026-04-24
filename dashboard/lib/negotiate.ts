import { API_BASE } from "./sse";
import type { NegotiationSession } from "./types";

export async function listSessions(limit = 20): Promise<NegotiationSession[]> {
  const res = await fetch(`${API_BASE}/api/negotiate/sessions?limit=${limit}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const body = (await res.json()) as { sessions: NegotiationSession[] };
  return body.sessions;
}

export async function getSession(id: string): Promise<NegotiationSession> {
  const res = await fetch(`${API_BASE}/api/negotiate/sessions/${id}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as NegotiationSession;
}
