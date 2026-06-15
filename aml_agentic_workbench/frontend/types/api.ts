export type SupportedRole = "data_scientist" | "investigator" | "model_validator" | "compliance_strategy";

export type TaskType =
  | "generate_model_driven_candidates"
  | "investigate_model_prioritized_candidate"
  | "customer_behaviour_analysis"
  | "model_risk_explanation"
  | "typology_mapping"
  | "feature_quality_review"
  | "full_intelligence_report"
  | "investigator_summary"
  | "model_validation_review"
  | "compliance_typology_review";

export type AgentName =
  | "candidate_ranking_agent"
  | "case_investigation_agent"
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

export interface CustomerDataSource {
  source: string;
  label: string;
  source_type: "transaction" | "kyc" | "model_context" | string;
  row_count: number;
  columns: string[];
  customer_search_supported: boolean;
}

export interface CustomerDataSourcesResponse {
  sources: CustomerDataSource[];
}

export interface CustomerDataSection {
  source: string;
  label: string;
  source_type: string;
  row_count: number;
  returned_count: number;
  columns: string[];
  records: CustomerDataRecord[];
  summary: Record<string, unknown>;
  truncated: boolean;
}

export interface CustomerDataRecord {
  [key: string]: string | number | boolean | null;
}

export interface CustomerDataResponse {
  customer_id: string;
  source: string;
  limit: number;
  summary: {
    customer_type?: string | null;
    available_sources: string[];
    transaction_source_count: number;
    total_records: number;
    feature_available: boolean;
  };
  sections: CustomerDataSection[];
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
    model_run_summary?: ModelRunSummary | null;
    model_comparison?: ModelComparisonItem[];
    model_results?: ModelResults;
    candidate_packages?: DetectionCandidatePackage[];
    investigation_case_review?: InvestigationCaseReview | null;
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

export interface ModelRunSummary {
  model_run_id: string;
  selected_model_family: string;
  candidate_count: number;
  threshold_method: string;
  status: string;
}

export interface ModelComparisonItem {
  model_family: string;
  status: string;
  comparison_type?: string;
  mathematical_objective: string;
}

export interface FeatureDriver {
  feature_name: string;
  value?: string | number | null;
  baseline?: string | number | null;
  direction: string;
  explanation: string;
  feature_display_name?: string | null;
  feature_definition?: string | null;
  engineering_formula?: string | null;
  customer_value?: string | number | null;
  population_baseline?: string | number | null;
  z_score?: number | null;
  shap_value?: number | null;
  shap_direction?: string | null;
  reconstruction_contribution?: number | null;
  investigator_interpretation?: string | null;
  suggested_evidence_to_review?: string | null;
  explanation_method?: string | null;
}

export interface DetectionCandidatePackage {
  candidate_id: string;
  customer_id: string;
  model_run_id: string;
  model_version: string;
  model_family: string;
  rank: number;
  score: number;
  score_percentile: number;
  threshold: number;
  threshold_reason: string;
  alert_recommendation: string;
  top_feature_drivers: FeatureDriver[];
  model_specific_driver_details: Record<string, unknown>[];
  feature_driver_explanations: string[];
  llm_explanation?: CandidateExplanation | null;
  guardrail_status: "passed" | "fallback_used" | "llm_unavailable" | "not_generated";
  guardrail_flags: string[];
  fallback_explanation?: CandidateExplanation | null;
  supporting_transaction_slices: Record<string, unknown>[];
  peer_group_baseline: Record<string, unknown>;
  model_limitations: string[];
  missing_data: string[];
  suggested_investigation_focus: string[];
  disclaimer: string;
}

export interface CandidateExplanation {
  summary: string;
  model_reasoning: string;
  feature_driver_explanation: string;
  suggested_investigator_focus: string[];
  limitations: string[];
}

export interface ModelResults {
  isolation_forest: DetectionCandidatePackage[];
  autoencoder: DetectionCandidatePackage[];
  variational_autoencoder: DetectionCandidatePackage[];
  conditional_variational_autoencoder: DetectionCandidatePackage[];
  intersection: DetectionCandidatePackage[];
}

export interface InvestigatorFeedback {
  case_disposition: string;
  typology_assessment: string;
  false_positive_reason?: string | null;
  useful_model_drivers: string[];
  misleading_model_drivers: string[];
  missing_features: string[];
  investigator_notes: string;
  label_for_model_evaluation: string;
}

export interface InvestigationCaseReview {
  candidate_package: DetectionCandidatePackage;
  behaviour_review: string;
  typology_review: string;
  missing_evidence: string[];
  disposition_recommendation: string;
  investigator_feedback: InvestigatorFeedback;
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
  model_run_summary?: ModelRunSummary | null;
  model_comparison?: ModelComparisonItem[];
  model_results?: ModelResults;
  candidate_packages?: DetectionCandidatePackage[];
  investigation_case_review?: InvestigationCaseReview | null;
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
