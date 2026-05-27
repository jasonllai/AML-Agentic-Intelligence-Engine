export type SupportedRole = "data_scientist" | "investigator" | "model_validator" | "compliance_strategy";

export type TaskType =
  | "customer_behaviour_analysis"
  | "model_risk_explanation"
  | "typology_mapping"
  | "feature_quality_review"
  | "full_intelligence_report"
  | "investigator_summary"
  | "model_validation_review"
  | "compliance_typology_review";

export type AgentName =
  | "transaction_behaviour_agent"
  | "model_explanation_agent"
  | "typology_mapping_agent"
  | "feature_critic_agent"
  | "evidence_assembly_agent"
  | "guardrail_agent"
  | "judge_panel_agent";

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
}

export interface RoleCatalogResponse {
  roles: SupportedRole[];
}

export interface AnalysisRequest {
  role: SupportedRole;
  task_type: TaskType;
  customer_id?: string;
  alert_id?: string;
  query: string;
  selected_agents?: AgentName[];
  require_full_report: boolean;
}

export interface AnalysisResponse {
  run_id: string;
  role: SupportedRole;
  executed_agents: AgentName[];
  status: string;
  result: {
    message?: string;
    query?: string;
    final_report?: string;
    agent_outputs?: Record<string, AgentOutput>;
    audit_trace?: AuditTraceItem[];
    judge_panel?: unknown;
    guardrail_failure_reasons?: string[];
  };
  guardrail_status: string;
  judge_scores?: Record<string, number>;
  route_explanation?: string;
}

export interface AgentOutput {
  summary?: string;
  findings?: string[];
  evidence?: Record<string, unknown>[];
  limitations?: string[];
  confidence?: number;
  citations?: Record<string, unknown>[];
  structured_output?: Record<string, unknown>;
}

export interface AuditTraceItem {
  event: string;
  agent?: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface ReportSummary {
  run_id: string;
  title: string;
  role: SupportedRole;
  task_type: TaskType;
  status: string;
  overall_judge_score?: number | null;
  guardrail_status: string;
  created_at: string;
}

export interface ReportListResponse {
  reports: ReportSummary[];
}

export interface ReportDetailResponse {
  run_id: string;
  role: SupportedRole;
  task_type: TaskType;
  status: string;
  guardrail_status: string;
  final_report?: string | null;
  executed_agents: AgentName[];
  judge_scores?: Record<string, number> | null;
  route_explanation?: string | null;
  agent_outputs: Record<string, AgentOutput>;
  audit_trace: AuditTraceItem[];
  created_at: string;
}

export interface GoldenCase {
  case_id: string;
  role: SupportedRole;
  task_type: TaskType;
  customer_id?: string | null;
  query: string;
  expected_agents: AgentName[];
  expected_evidence: string[];
  expected_guardrail_outcome: "allowed" | "blocked";
  requires_citations: boolean;
  tags: string[];
}

export interface GoldenDatasetResponse {
  case_count: number;
  cases: GoldenCase[];
}

export interface EvaluationCaseResult {
  case_id: string;
  role: SupportedRole;
  task_type: TaskType;
  query: string;
  passed: boolean;
  metrics: Record<string, number>;
  expected_agents: AgentName[];
  actual_agents: AgentName[];
  expected_guardrail_outcome: "allowed" | "blocked";
  actual_guardrail_outcome: "allowed" | "blocked";
  judge_rationale: Record<string, string>;
  retrieved_citations: Record<string, unknown>[];
  failure_reasons: string[];
}

export interface EvaluationRunSummary {
  run_id: string;
  status: string;
  case_count: number;
  passed_count: number;
  failed_count: number;
  overall_score: number;
  metrics: Record<string, number>;
  cases: EvaluationCaseResult[];
  created_at: string;
}
