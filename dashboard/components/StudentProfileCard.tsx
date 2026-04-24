"use client";
import { useEffect, useState } from "react";
import { GraduationCap, TrendingUp, AlertTriangle } from "lucide-react";
import { API_BASE } from "@/lib/sse";

interface StudentProfile {
  student_id: string;
  name: string;
  major: string;
  progress: {
    completed_credits: number;
    total_credits_required: number;
    completed_percentage: number;
    remaining_credits: number;
  };
  academic_health: {
    gpa: number;
    gpa_tier: "excellent" | "good" | "average" | "at_risk";
    at_risk_courses: string[];
    memory_notes: string[];
  };
}

const TIER_COLORS: Record<StudentProfile["academic_health"]["gpa_tier"], string> = {
  excellent: "text-emerald-700 bg-emerald-50",
  good: "text-blue-700 bg-blue-50",
  average: "text-amber-700 bg-amber-50",
  at_risk: "text-red-700 bg-red-50",
};

const TIER_LABELS: Record<StudentProfile["academic_health"]["gpa_tier"], string> = {
  excellent: "ممتاز",
  good: "جيد جداً",
  average: "متوسط",
  at_risk: "تحت المراقبة",
};

interface Props {
  studentId: string | null;
}

export function StudentProfileCard({ studentId }: Props) {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!studentId) {
      setProfile(null);
      return;
    }
    const controller = new AbortController();
    setLoading(true);
    fetch(`${API_BASE}/api/students/${studentId}/profile`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setProfile(data))
      .catch(() => {
        /* aborted or network error — stay blank */
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [studentId]);

  if (!studentId) return null;
  if (loading && !profile) return <ProfileSkeleton />;
  if (!profile) return null;

  const { progress, academic_health } = profile;
  const hasNotes =
    academic_health.at_risk_courses.length > 0 ||
    academic_health.memory_notes.length > 0;

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs text-slate-500 mb-1">الطالب الحالي</div>
          <div className="font-semibold text-slate-900 truncate">{profile.name}</div>
          <div className="text-xs text-slate-500 truncate">
            {profile.student_id} · {profile.major}
          </div>
        </div>
        <span
          className={`shrink-0 text-xs px-2 py-1 rounded-full font-medium ${TIER_COLORS[academic_health.gpa_tier]}`}
        >
          {TIER_LABELS[academic_health.gpa_tier]}
        </span>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600 flex items-center gap-1.5">
            <TrendingUp className="w-4 h-4" /> المعدل
          </span>
          <span className="font-semibold text-slate-900">
            {academic_health.gpa.toFixed(2)}
          </span>
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-slate-600 flex items-center gap-1.5">
            <GraduationCap className="w-4 h-4" /> التقدم
          </span>
          <span className="font-semibold text-slate-900">
            {progress.completed_credits}/{progress.total_credits_required} ساعة
          </span>
        </div>

        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
          <div
            className="bg-gradient-to-r from-blue-500 to-indigo-600 h-full rounded-full transition-all duration-500"
            style={{ width: `${progress.completed_percentage}%` }}
          />
        </div>
        <div className="text-xs text-slate-500 text-left" dir="ltr">
          {progress.completed_percentage}%
        </div>
      </div>

      {hasNotes && (
        <div className="pt-3 border-t border-slate-100 space-y-2">
          <div className="text-xs font-medium text-amber-700 flex items-center gap-1.5">
            <AlertTriangle className="w-3.5 h-3.5" />
            ملاحظات أكاديمية
          </div>
          <ul className="text-xs text-slate-600 space-y-1 leading-relaxed">
            {academic_health.at_risk_courses.map((code) => (
              <li key={`risk-${code}`}>• غياب مرتفع في {code}</li>
            ))}
            {academic_health.memory_notes.map((note, i) => (
              <li key={`note-${i}`}>• {note}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ProfileSkeleton() {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 space-y-3 animate-pulse">
      <div className="h-3 bg-slate-200 rounded w-20" />
      <div className="h-5 bg-slate-200 rounded w-40" />
      <div className="h-3 bg-slate-200 rounded w-32" />
      <div className="h-2 bg-slate-200 rounded w-full" />
    </div>
  );
}
