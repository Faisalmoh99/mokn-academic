export type AgentName = "Orchestrator" | "Planner" | "Legis" | "Guardian";

export type TurnType =
  | "user_request"
  | "orchestrator_classify"
  | "planner_propose"
  | "legis_review"
  | "legis_veto"
  | "legis_approve"
  | "orchestrator_route"
  | "orchestrator_synthesize"
  | "system_escalate"
  | "system_max_rounds";

export type Outcome =
  | "approved"
  | "escalated"
  | "max_rounds"
  | "regulation_only"
  | "out_of_scope";

export interface NegotiationTurn {
  turn_id: string;
  session_id: string;
  round_number: number;
  turn_type: TurnType;
  agent: AgentName | null;
  content: Record<string, unknown>;
  summary: string;
  timestamp: string;
}

export interface NegotiationSession {
  session_id: string;
  student_id: string | null;
  user_request: string;
  intent: "regulation_question" | "build_schedule" | "unknown";
  turns: NegotiationTurn[];
  outcome: Outcome | null;
  final_answer: string | null;
  final_proposal: Record<string, unknown> | null;
  started_at: string;
  ended_at: string | null;
}

/** Derived UI state for the agent cards on the left rail. */
export type AgentStatus =
  | "idle"
  | "thinking"
  | "active"
  | "vetoing"
  | "approving";

export interface ScenarioRequest {
  request: string;
  student_id?: string;
}

export interface ScheduleCourse {
  course_code: string;
  course_name: string;
  section_id: string;
  credits: number;
  days: string[];
  start_time: string;
  end_time: string;
  instructor: string;
}

export interface ScheduleOption {
  label: string;
  courses: ScheduleCourse[];
  total_credits: number;
  estimated_difficulty: number;
  reasoning: string;
}

export interface ScheduleProposal {
  student_id: string;
  target_semester: string;
  options: ScheduleOption[];
  recommended_option: string | null;
  warnings: string[];
  constraints_considered: string[];
  no_solution?: boolean;
}

// --- Guardian (Session 6) ---------------------------------------------------

export type RiskSeverity = "low" | "medium" | "high" | "critical";

export type RiskFactorType =
  | "attendance_high"
  | "attendance_critical"
  | "weak_grade"
  | "gpa_declining"
  | "prior_dn"
  | "low_gpa_high_load";

export interface RiskFactor {
  factor_type: RiskFactorType;
  course_code: string | null;
  description_ar: string;
  severity: RiskSeverity;
  evidence: Record<string, unknown>;
}

export interface RiskAssessment {
  student_id: string;
  student_name: string;
  overall_severity: RiskSeverity;
  factors: RiskFactor[];
  summary_ar: string;
}

export type GuardianRecommendationAction =
  | "reduce_credit_hours"
  | "drop_at_risk_course"
  | "consult_advisor"
  | "improve_attendance"
  | "review_study_plan";

export type GuardianRecommendationPriority = "info" | "advisory" | "urgent";

export interface GuardianRecommendation {
  title_ar: string;
  rationale_ar: string;
  suggested_action: GuardianRecommendationAction;
  priority: GuardianRecommendationPriority;
}

export interface ProactiveAlert {
  alert_id: string;
  student_id: string;
  student_name: string;
  triggered_at: string;
  assessment: RiskAssessment;
  recommendations: GuardianRecommendation[];
  message_ar: string;
}

export interface GuardianScanReport {
  scan_id: string;
  started_at: string;
  completed_at: string;
  total_students_scanned: number;
  students_at_risk: number;
  alerts: ProactiveAlert[];
}
