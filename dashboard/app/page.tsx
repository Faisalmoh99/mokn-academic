"use client";
import { useCallback, useRef, useState } from "react";
import { AgentsPanel } from "@/components/AgentsPanel";
import { ChatPanel } from "@/components/ChatPanel";
import { FailoverDialog } from "@/components/FailoverDialog";
import { InputBar } from "@/components/InputBar";
import { OfflineDemoPicker } from "@/components/OfflineDemoPicker";
import { OfflineModeBanner } from "@/components/OfflineModeBanner";
import { PresetButtons } from "@/components/PresetButtons";
import { SessionSidebar } from "@/components/SessionSidebar";
import { StudentProfileCard } from "@/components/StudentProfileCard";
import {
  loadOfflineSession,
  replayOfflineSession,
  type DemoSession,
} from "@/lib/offline";
import { streamNegotiate } from "@/lib/sse";
import type {
  AgentName,
  NegotiationSession,
  NegotiationTurn,
  ScenarioRequest,
  TurnType,
} from "@/lib/types";

const REPLAY_GAP_MS = 1500;

export default function Home() {
  const [turns, setTurns] = useState<NegotiationTurn[]>([]);
  const [session, setSession] = useState<NegotiationSession | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [currentTurn, setCurrentTurn] = useState<TurnType | null>(null);
  const [lastAgent, setLastAgent] = useState<AgentName | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  const [currentStudentId, setCurrentStudentId] = useState<string | null>(null);
  const [isOfflineMode, setIsOfflineMode] = useState(false);
  const [showFailoverDialog, setShowFailoverDialog] = useState(false);

  const abortRef = useRef<AbortController | null>(null);
  const replayCancelRef = useRef<{ cancelled: boolean } | null>(null);
  const offlineAbortRef = useRef<AbortController | null>(null);

  const resetBoard = useCallback(() => {
    abortRef.current?.abort();
    offlineAbortRef.current?.abort();
    if (replayCancelRef.current) replayCancelRef.current.cancelled = true;
    abortRef.current = null;
    offlineAbortRef.current = null;
    replayCancelRef.current = null;
    setTurns([]);
    setSession(null);
    setCurrentTurn(null);
    setLastAgent(null);
    setErrorMsg(null);
    setCurrentStudentId(null);
    setIsOfflineMode(false);
    setShowFailoverDialog(false);
    setStreaming(false);
  }, []);

  const runScenario = useCallback(
    async (body: ScenarioRequest) => {
      resetBoard();
      const controller = new AbortController();
      abortRef.current = controller;
      setStreaming(true);
      setCurrentStudentId(body.student_id ?? null);

      await streamNegotiate(
        { request: body.request, student_id: body.student_id },
        {
          onTurn: (turn) => {
            setTurns((prev) => [...prev, turn]);
            setCurrentTurn(turn.turn_type);
            setLastAgent(turn.agent);
          },
          onDone: (done) => {
            setSession(done);
            setStreaming(false);
            setCurrentTurn(null);
            setLastAgent(null);
            setRefreshToken((t) => t + 1);
          },
          onError: (err) => {
            setErrorMsg(err.message);
            setStreaming(false);
            setCurrentTurn(null);
            setLastAgent(null);
            if (err.recoverable) {
              setShowFailoverDialog(true);
            }
          },
        },
        controller.signal,
      ).catch((err: Error) => {
        if (err.name !== "AbortError") {
          setErrorMsg(err.message);
          setShowFailoverDialog(true);
        }
        setStreaming(false);
      });
    },
    [resetBoard],
  );

  const replaySession = useCallback(
    async (full: NegotiationSession) => {
      resetBoard();
      const cancelToken = { cancelled: false };
      replayCancelRef.current = cancelToken;
      setStreaming(true);
      setCurrentStudentId(full.student_id ?? null);

      for (const turn of full.turns) {
        if (cancelToken.cancelled) return;
        setTurns((prev) => [...prev, turn]);
        setCurrentTurn(turn.turn_type);
        setLastAgent(turn.agent);
        await new Promise((r) => setTimeout(r, REPLAY_GAP_MS));
      }
      if (cancelToken.cancelled) return;

      setSession(full);
      setStreaming(false);
      setCurrentTurn(null);
      setLastAgent(null);
    },
    [resetBoard],
  );

  const runOfflineDemo = useCallback(
    async (demo: DemoSession) => {
      resetBoard();
      const controller = new AbortController();
      offlineAbortRef.current = controller;
      setStreaming(true);
      setIsOfflineMode(true);

      try {
        const saved = await loadOfflineSession(demo.file);
        setCurrentStudentId(saved.student_id);

        for await (const turn of replayOfflineSession(saved, 1.0, controller.signal)) {
          setTurns((prev) => [...prev, turn]);
          setCurrentTurn(turn.turn_type);
          setLastAgent(turn.agent);
        }

        if (!controller.signal.aborted) {
          setSession(saved);
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setErrorMsg(err instanceof Error ? err.message : "Offline replay failed");
      } finally {
        setStreaming(false);
        setCurrentTurn(null);
        setLastAgent(null);
      }
    },
    [resetBoard],
  );

  const exitOfflineMode = useCallback(() => {
    resetBoard();
  }, [resetBoard]);

  const hasActivity = turns.length > 0 || streaming || session !== null;

  return (
    <main className="flex h-screen overflow-hidden">
      <section className="flex-1 flex flex-col min-w-0">
        {isOfflineMode && <OfflineModeBanner onExit={exitOfflineMode} />}
        <header className="px-6 py-4 border-b border-slate-200 bg-white">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-bold text-slate-900">مُكِن أكاديمي</h1>
              <p className="text-xs text-slate-500">
                نظام تفاوضي متعدد الوكلاء للإرشاد الأكاديمي
              </p>
            </div>
            <div className="flex items-center gap-2">
              {errorMsg && (
                <span className="rounded-lg bg-red-50 border border-red-200 px-3 py-1.5 text-xs text-red-700">
                  ⚠️ {errorMsg}
                </span>
              )}
              <button
                type="button"
                onClick={resetBoard}
                disabled={!hasActivity}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-30 disabled:cursor-not-allowed"
              >
                🔄 إعادة تعيين
              </button>
            </div>
          </div>
        </header>
        <PresetButtons onSelect={runScenario} disabled={streaming} />
        <ChatPanel turns={turns} session={session} streaming={streaming} />
        <InputBar onSubmit={runScenario} disabled={streaming} />
      </section>
      <div className="w-[38%] max-w-md border-l border-slate-200 bg-white flex flex-col">
        <div className="flex-1 overflow-y-auto">
          <AgentsPanel
            currentTurn={currentTurn}
            lastAgent={lastAgent}
            streaming={streaming}
          />
          {currentStudentId && (
            <div className="px-6 pb-6">
              <StudentProfileCard studentId={currentStudentId} />
            </div>
          )}
          <OfflineDemoPicker onSelect={runOfflineDemo} disabled={streaming} />
        </div>
        <SessionSidebar
          onReplay={replaySession}
          disabled={streaming}
          refreshToken={refreshToken}
        />
      </div>
      <FailoverDialog
        open={showFailoverDialog}
        onClose={() => setShowFailoverDialog(false)}
        onSelectOffline={runOfflineDemo}
      />
    </main>
  );
}
