"use client";

import { useState } from "react";
import Link from "next/link";
import type {
  AgentOutput,
  AnalysisResponse,
  CriticReview,
  DetectionCandidatePackage,
  GuardrailRemediation,
  InvestigationCaseReview,
  ModelResults,
  PlannerDecision,
  ReportDetailResponse
} from "@/types/api";
import { agents } from "@/lib/catalog";
import { formatLabel } from "@/lib/utils";
import { Badge, Button, Card, EmptyState } from "@/components/ui";

type ReportLike = ReportDetailResponse | AnalysisResponse;

function getAgentOutputs(report: ReportLike): Record<string, AgentOutput> {
  if ("agent_outputs" in report) return report.agent_outputs;
  return report.result.agent_outputs ?? {};
}

function getFinalReport(report: ReportLike): string | null | undefined {
  if ("final_report" in report) return report.final_report;
  return "result" in report ? report.result.final_report : undefined;
}

function getAuditTrace(report: ReportLike) {
  if ("audit_trace" in report) return report.audit_trace;
  return report.result.audit_trace ?? [];
}

function getCandidatePackages(report: ReportLike): DetectionCandidatePackage[] {
  if ("result" in report) return report.result.candidate_packages ?? [];
  return report.candidate_packages ?? [];
}

function getInvestigationCaseReview(report: ReportLike): InvestigationCaseReview | null | undefined {
  if ("result" in report) return report.result.investigation_case_review;
  return report.investigation_case_review;
}

function getModelResults(report: ReportLike): ModelResults | undefined {
  if ("result" in report) return report.result.model_results;
  return report.model_results;
}

function getPlannerDecisions(report: ReportLike): PlannerDecision[] {
  if ("result" in report) return report.result.planner_decisions ?? [];
  return report.planner_decisions ?? [];
}

function getCriticReviews(report: ReportLike): CriticReview[] {
  if ("result" in report) return report.result.critic_reviews ?? [];
  return report.critic_reviews ?? [];
}

function getStopReason(report: ReportLike): string | null | undefined {
  if ("result" in report) return report.result.stop_reason;
  return report.stop_reason;
}

function getRefinementRounds(report: ReportLike): number {
  if ("result" in report) return report.result.refinement_rounds ?? 0;
  return report.refinement_rounds ?? 0;
}

function getGuardrailRemediationRounds(report: ReportLike): number {
  if ("result" in report) return report.result.guardrail_remediation_rounds ?? 0;
  return report.guardrail_remediation_rounds ?? 0;
}

function getGuardrailRemediations(report: ReportLike): GuardrailRemediation[] {
  if ("result" in report) return report.result.guardrail_remediations ?? [];
  return report.guardrail_remediations ?? [];
}

function getGovernanceStatus(report: ReportLike): string {
  if ("result" in report) return report.result.governance_status ?? (report.guardrail_status === "failed" ? "guardrail_failed" : "passed");
  return report.governance_status ?? (report.guardrail_status === "failed" ? "guardrail_failed" : "passed");
}

function getJudgeStatus(report: ReportLike): string {
  if ("result" in report) return report.result.judge_status ?? "passed";
  return report.judge_status ?? "passed";
}

function getJudgeFailureReasons(report: ReportLike): string[] {
  if ("result" in report) return report.result.judge_failure_reasons ?? [];
  return report.judge_failure_reasons ?? [];
}

export function ReportView({ report }: { report: ReportLike }) {
  const agentOutputs = getAgentOutputs(report);
  const finalReport = getFinalReport(report);
  const judgeScores = report.judge_scores ?? {};
  const governanceStatus = getGovernanceStatus(report);
  const judgeStatus = getJudgeStatus(report);
  const judgeFailureReasons = getJudgeFailureReasons(report);
  const exportAllowed = report.guardrail_status === "passed" && report.status === "completed";
  const exportLabel = judgeStatus === "warning" ? "Export with warning" : "Export governed report";
  const citations = Object.values(agentOutputs).flatMap((output) => output.citations ?? []);
  const candidatePackages = getCandidatePackages(report);
  const investigationCaseReview = getInvestigationCaseReview(report);
  const modelResults = getModelResults(report);
  const plannerDecisions = getPlannerDecisions(report);
  const criticReviews = getCriticReviews(report);
  const guardrailRemediations = getGuardrailRemediations(report);

  if (modelResults) {
    return (
      <DataScientistModelResults
        report={report}
        modelResults={modelResults}
        agentOutputs={agentOutputs}
        auditTrace={getAuditTrace(report)}
      />
    );
  }

  return (
    <div className="grid gap-6">
      <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft">
        <div className="grid gap-0 xl:grid-cols-[1fr_320px]">
          <div className="p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="flex flex-wrap gap-2">
                  <Badge tone={report.guardrail_status === "passed" ? "success" : "danger"}>
                    Guardrail {report.guardrail_status}
                  </Badge>
                  {judgeStatus === "warning" && <Badge tone="warning">Judge warning</Badge>}
                  {governanceStatus === "judge_warning" && <Badge tone="warning">Governance warning</Badge>}
                </div>
                <h1 className="mt-4 text-3xl font-semibold text-ink">AML Intelligence Package</h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                  Human-review output. Model scores and typology indicators are decision-support signals, not proof
                  of suspicious or criminal activity.
                </p>
              </div>
              <Button disabled={!exportAllowed}>{exportLabel}</Button>
            </div>

            <div className="mt-6 grid gap-3 md:grid-cols-4">
              <ScoreCard label="Overall judge" value={judgeScores.overall_score} />
              <ScoreCard label="Faithfulness" value={judgeScores.faithfulness} />
              <ScoreCard label="Citations" value={judgeScores.citation} />
              <ScoreCard label="Compliance" value={judgeScores.compliance} />
            </div>
          </div>

          <aside className="border-t border-slate-200 bg-[#111827] p-6 text-white xl:border-l xl:border-t-0">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-300">Package status</div>
            <div className="mt-4 grid gap-3">
              <StatusLine label="Run status" value={formatLabel(report.status)} />
              <StatusLine label="Governance" value={formatLabel(governanceStatus)} />
              <StatusLine label="Judge" value={formatLabel(judgeStatus)} />
              <StatusLine label="Agents completed" value={String(Object.keys(agentOutputs).length)} />
              <StatusLine label="Citations" value={String(citations.length)} />
            </div>
          </aside>
        </div>
      </section>

      {finalReport ? (
        <section className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
          <Card className="p-6">
            <ReadableMarkdown text={finalReport} />
          </Card>
          <div className="grid content-start gap-6">
            <DecisionRefinementPanel
              decisions={plannerDecisions}
              criticReviews={criticReviews}
              stopReason={getStopReason(report)}
              refinementRounds={getRefinementRounds(report)}
              guardrailRemediationRounds={getGuardrailRemediationRounds(report)}
              guardrailRemediations={guardrailRemediations}
              judgeStatus={judgeStatus}
              judgeFailureReasons={judgeFailureReasons}
            />
            <CandidatePackagePanel packages={candidatePackages} />
            <InvestigationFeedbackPanel review={investigationCaseReview} />
            <AgentSummary outputs={agentOutputs} />
            <CitationPanel citations={citations} />
          </div>
        </section>
      ) : (
        <EmptyState title="No report content" body="Run an analysis to generate a governed report." />
      )}

      <EvidencePanel outputs={agentOutputs} />
      <AuditPanel events={getAuditTrace(report)} />
    </div>
  );
}

type ModelResultKey = keyof ModelResults;

const MODEL_RESULT_LABELS: Record<ModelResultKey, string> = {
  isolation_forest: "Isolation Forest",
  autoencoder: "Autoencoder",
  variational_autoencoder: "Variational Autoencoder",
  conditional_variational_autoencoder: "Conditional Variational Autoencoder",
  intersection: "Intersection of all models"
};

function DataScientistModelResults({
  report,
  modelResults,
  agentOutputs,
  auditTrace
}: {
  report: ReportLike;
  modelResults: ModelResults;
  agentOutputs: Record<string, AgentOutput>;
  auditTrace: Array<Record<string, unknown>>;
}) {
  const [selectedModel, setSelectedModel] = useState<ModelResultKey>("isolation_forest");
  const [expandedCandidate, setExpandedCandidate] = useState<string | null>(null);
  const candidates = modelResults[selectedModel] ?? [];

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-slate-200 bg-white p-6 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge tone="success">Model explanations guardrailed</Badge>
            <h1 className="mt-4 text-3xl font-semibold text-ink">Model Candidate Results</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Four unsupervised anomaly models ranked customers for investigation prioritization. Scores and
              explanations are not proof of suspicious activity.
            </p>
          </div>
          <div className="rounded-md border border-slate-200 bg-slate-50 px-4 py-3 text-sm">
            <div className="text-xs font-semibold uppercase text-slate-500">Run status</div>
            <div className="mt-1 font-semibold text-ink">{formatLabel(report.status)}</div>
          </div>
        </div>

        <div className="mt-6 max-w-sm">
          <label className="mb-1 block text-sm font-medium text-slate-700" htmlFor="model-result-select">
            Result list
          </label>
          <select
            id="model-result-select"
            value={selectedModel}
            onChange={(event) => {
              setSelectedModel(event.target.value as ModelResultKey);
              setExpandedCandidate(null);
            }}
            className="w-full rounded-md border border-slate-300 bg-white p-2.5 text-sm"
          >
            {(Object.keys(MODEL_RESULT_LABELS) as ModelResultKey[]).map((key) => (
              <option key={key} value={key}>{MODEL_RESULT_LABELS[key]}</option>
            ))}
          </select>
        </div>
      </section>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-xl font-semibold text-ink">{MODEL_RESULT_LABELS[selectedModel]}</h2>
            <p className="mt-1 text-sm text-slate-600">Top ranked customers for this result set.</p>
          </div>
          <Badge>{candidates.length} customers</Badge>
        </div>

        <div className="mt-5 grid gap-3">
          {candidates.length === 0 ? (
            <EmptyState title="No overlapping customers" body="No customers appeared in every model top-10 list." />
          ) : (
            candidates.map((candidate) => (
              <CandidateResultRow
                key={`${selectedModel}-${candidate.customer_id}`}
                candidate={candidate}
                expanded={expandedCandidate === candidate.customer_id}
                onToggle={() => {
                  setExpandedCandidate(expandedCandidate === candidate.customer_id ? null : candidate.customer_id);
                }}
              />
            ))
          )}
        </div>
      </Card>

      <AgentSummary outputs={agentOutputs} />
      <AuditPanel events={auditTrace} />
    </div>
  );
}

function DecisionRefinementPanel({
  decisions,
  criticReviews,
  stopReason,
  refinementRounds,
  guardrailRemediationRounds,
  guardrailRemediations,
  judgeStatus,
  judgeFailureReasons
}: {
  decisions: PlannerDecision[];
  criticReviews: CriticReview[];
  stopReason?: string | null;
  refinementRounds: number;
  guardrailRemediationRounds: number;
  guardrailRemediations: GuardrailRemediation[];
  judgeStatus: string;
  judgeFailureReasons: string[];
}) {
  if (
    decisions.length === 0 &&
    criticReviews.length === 0 &&
    !stopReason &&
    refinementRounds === 0 &&
    guardrailRemediationRounds === 0 &&
    judgeStatus !== "warning"
  ) return null;
  const latestReview = criticReviews[criticReviews.length - 1];
  const latestGuardrailRemediation = guardrailRemediations[guardrailRemediations.length - 1];
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">Decision & Refinement</h2>
      <div className="mt-4 grid gap-2 text-sm">
        <FeedbackLine label="Stop reason" value={stopReason || "Planner finalized evidence gathering"} />
        <FeedbackLine label="Refinements" value={String(refinementRounds)} />
        <FeedbackLine label="Guardrail remediation" value={String(guardrailRemediationRounds)} />
        {judgeStatus === "warning" && <FeedbackLine label="Judge warning" value={judgeFailureReasons[0] || "Quality gate warning"} />}
        {latestReview && <FeedbackLine label="Critic status" value={formatLabel(latestReview.status)} />}
      </div>
      {decisions.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase text-slate-500">Planner decisions</div>
          <div className="mt-2 grid gap-2">
            {decisions.slice(-4).map((decision, index) => (
              <div key={`${decision.next_action}-${index}`} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <div className="font-semibold text-ink">{formatLabel(String(decision.next_action))}</div>
                <p className="mt-1 leading-6 text-slate-600">{decision.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {latestReview?.issues && latestReview.issues.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase text-slate-500">Critic feedback</div>
          <ul className="mt-2 grid gap-1 text-sm text-slate-600">
            {latestReview.issues.slice(0, 3).map((issue) => <li key={issue}>- {issue}</li>)}
          </ul>
        </div>
      )}
      {latestGuardrailRemediation && (
        <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
          <div className="font-semibold text-ink">Latest guardrail remediation</div>
          <p className="mt-1 leading-6 text-slate-600">{latestGuardrailRemediation.instruction}</p>
          {latestGuardrailRemediation.flags.length > 0 && (
            <p className="mt-2 text-xs leading-5 text-slate-500">
              Flags: {latestGuardrailRemediation.flags.join(", ")}
            </p>
          )}
        </div>
      )}
    </Card>
  );
}

function CandidateResultRow({
  candidate,
  expanded,
  onToggle
}: {
  candidate: DetectionCandidatePackage;
  expanded: boolean;
  onToggle: () => void;
}) {
  const explanation = candidate.llm_explanation ?? candidate.fallback_explanation;
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3 text-left"
      >
        <div>
          <div className="font-semibold text-ink">#{candidate.rank} {candidate.customer_id}</div>
          <div className="mt-1 text-sm text-slate-600">
            {formatLabel(candidate.model_family)} · {formatLabel(candidate.alert_recommendation)}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge>{Math.round(candidate.score * 100)} score</Badge>
          <Badge tone={candidate.guardrail_status === "passed" ? "success" : "warning"}>
            {candidateGuardrailLabel(candidate.guardrail_status)}
          </Badge>
        </div>
      </button>

      {expanded && (
        <div className="border-t border-slate-200 bg-white px-4 py-4">
          <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
            <div className="grid gap-4">
              {explanation && (
                <div>
                  <h3 className="text-sm font-semibold uppercase text-slate-500">Guarded explanation</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{explanation.summary}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{explanation.model_reasoning}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{explanation.feature_driver_explanation}</p>
                </div>
              )}

              <div>
                <h3 className="text-sm font-semibold uppercase text-slate-500">Feature drivers</h3>
                <ul className="mt-2 grid gap-2 text-sm text-slate-700">
                  {candidate.top_feature_drivers.map((driver) => {
                    const attributionMetric = driverAttributionMetric(driver);
                    return (
                      <li key={driver.feature_name} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div>
                            <div className="font-semibold text-ink">
                              {driver.feature_display_name ?? formatLabel(driver.feature_name)}
                            </div>
                            <div className="mt-0.5 font-mono text-xs text-slate-500">{driver.feature_name}</div>
                          </div>
                          {driver.explanation_method && (
                            <Badge>{formatLabel(driver.explanation_method)}</Badge>
                          )}
                        </div>
                        {driver.feature_definition && (
                          <p className="mt-2 leading-6 text-slate-700">{driver.feature_definition}</p>
                        )}
                        {driver.engineering_formula && (
                          <p className="mt-1 text-xs leading-5 text-slate-500">
                            Engineered as: {driver.engineering_formula}
                          </p>
                        )}
                        <div className="mt-3 grid gap-2 sm:grid-cols-3">
                          <DriverMetric label="Customer value" value={driver.customer_value ?? driver.value} />
                          <DriverMetric label="Population baseline" value={driver.population_baseline ?? driver.baseline} />
                          <DriverMetric label={attributionMetric.label} value={attributionMetric.value} />
                        </div>
                        {driver.z_score != null && (
                          <p className="mt-2 text-xs leading-5 text-slate-500">
                            Standardized deviation: {formatSignedNumber(driver.z_score)}
                            {driver.shap_direction ? ` · ${formatLabel(driver.shap_direction)}` : ""}
                          </p>
                        )}
                        {(driver.suggested_evidence_to_review || driver.investigator_interpretation) && (
                          <p className="mt-2 leading-6 text-slate-700">
                            Investigator focus: {driver.suggested_evidence_to_review ?? driver.investigator_interpretation}
                          </p>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>

              {candidate.model_limitations.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold uppercase text-slate-500">Model limitations</h3>
                  <ul className="mt-2 grid gap-1 text-sm text-slate-600">
                    {candidate.model_limitations.map((item) => <li key={item}>- {item}</li>)}
                  </ul>
                </div>
              )}
            </div>

            <aside className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm">
              <FeedbackLine label="Score" value={candidate.score.toFixed(3)} />
              <div className="mt-2">
                <FeedbackLine label="Threshold" value={candidate.threshold.toFixed(3)} />
              </div>
              <Link
                href={`/roles/investigator?customerId=${encodeURIComponent(candidate.customer_id)}&modelFamily=${encodeURIComponent(candidate.model_family)}`}
                className="mt-4 inline-flex w-full justify-center rounded-md bg-bankred px-3 py-2 text-xs font-semibold text-white hover:bg-red-800"
              >
                Open investigator review
              </Link>
            </aside>
          </div>
          <p className="mt-4 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-500">{candidate.disclaimer}</p>
        </div>
      )}
    </div>
  );
}

function DriverMetric({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-2.5 py-2">
      <div className="text-[11px] font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-semibold text-ink">{formatDriverValue(value)}</div>
    </div>
  );
}

function candidateGuardrailLabel(status: DetectionCandidatePackage["guardrail_status"]): string {
  if (status === "passed") return "LLM Passed";
  if (status === "fallback_used") return "Safe Fallback";
  if (status === "llm_unavailable") return "LLM Unavailable";
  return "Not Generated";
}

function formatDriverValue(value?: string | number | null): string {
  if (value == null || value === "") return "n/a";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  return String(value);
}

function formatSignedNumber(value?: number | null): string {
  if (value == null) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
}

function driverAttributionMetric(driver: DetectionCandidatePackage["top_feature_drivers"][number]): {
  label: string;
  value: string;
} {
  if (driver.shap_value != null) {
    return { label: "SHAP contribution", value: formatSignedNumber(driver.shap_value) };
  }
  if (driver.reconstruction_contribution != null) {
    return {
      label: "Reconstruction contribution",
      value: formatSignedNumber(driver.reconstruction_contribution)
    };
  }
  return { label: "Model contribution", value: "n/a" };
}

function CandidatePackagePanel({ packages }: { packages: DetectionCandidatePackage[] }) {
  if (packages.length === 0) return null;
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-ink">Detection candidate packages</h2>
        <Badge>{packages.length}</Badge>
      </div>
      <div className="mt-4 grid gap-3">
        {packages.slice(0, 5).map((item) => (
          <div key={item.candidate_id} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="font-semibold text-ink">#{item.rank} {item.customer_id}</div>
              <Badge>{Math.round(item.score * 100)} score</Badge>
            </div>
            <div className="mt-2 text-slate-600">
              {formatLabel(item.model_family)} · {formatLabel(item.alert_recommendation)}
            </div>
            {item.feature_driver_explanations.length > 0 && (
              <ul className="mt-2 grid gap-1 text-slate-600">
                {item.feature_driver_explanations.slice(0, 3).map((driver) => (
                  <li key={driver}>- {driver}</li>
                ))}
              </ul>
            )}
            <Link
              href={`/roles/investigator?customerId=${encodeURIComponent(item.customer_id)}`}
              className="mt-3 inline-flex rounded-md bg-bankred px-3 py-2 text-xs font-semibold text-white hover:bg-red-800"
            >
              Open investigator review
            </Link>
            <p className="mt-3 border-t border-slate-200 pt-3 text-xs leading-5 text-slate-500">{item.disclaimer}</p>
          </div>
        ))}
      </div>
    </Card>
  );
}

function InvestigationFeedbackPanel({ review }: { review?: InvestigationCaseReview | null }) {
  if (!review) return null;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">Investigator feedback</h2>
      <div className="mt-4 grid gap-2 text-sm">
        <FeedbackLine label="Disposition" value={formatLabel(review.disposition_recommendation)} />
        <FeedbackLine label="Model label" value={formatLabel(review.investigator_feedback.label_for_model_evaluation)} />
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-700">{review.typology_review}</p>
      {review.missing_evidence.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-semibold uppercase text-slate-500">Missing evidence</div>
          <ul className="mt-2 grid gap-1 text-sm text-slate-600">
            {review.missing_evidence.map((item) => <li key={item}>- {item}</li>)}
          </ul>
        </div>
      )}
    </Card>
  );
}

function FeedbackLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <span className="text-slate-500">{label}</span>
      <span className="font-semibold text-ink">{value}</span>
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value?: number }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value == null ? "n/a" : `${Math.round(value * 100)}%`}</div>
    </div>
  );
}

function StatusLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 rounded-md bg-white/10 px-3 py-2 text-sm">
      <span className="text-slate-300">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </div>
  );
}

function ReadableMarkdown({ text }: { text: string }) {
  const blocks = parseMarkdown(text);
  return (
    <article className="grid gap-4 text-sm leading-7 text-slate-700">
      {blocks.map((block, index) => {
        if (block.type === "heading") {
          return <h2 key={index} className="mt-2 border-b border-slate-200 pb-2 text-xl font-semibold text-ink">{block.text}</h2>;
        }
        if (block.type === "list") {
          return (
            <ul key={index} className="grid gap-2">
              {block.items.map((item) => <li key={item} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">{item}</li>)}
            </ul>
          );
        }
        if (block.type === "table") {
          return <MarkdownTable key={index} headers={block.headers} rows={block.rows} />;
        }
        return <p key={index}>{block.text}</p>;
      })}
    </article>
  );
}

function AgentSummary({ outputs }: { outputs: Record<string, AgentOutput> }) {
  const rows = Object.entries(outputs);
  if (rows.length === 0) return null;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">Agent findings</h2>
      <div className="mt-4 grid gap-3">
        {rows.map(([agent, output]) => (
          <div key={agent} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold text-ink">{agents[agent as keyof typeof agents]?.label ?? formatLabel(agent)}</h3>
              {typeof output.confidence === "number" && <Badge>{Math.round(output.confidence * 100)}% confidence</Badge>}
            </div>
            {output.summary && <p className="mt-2 text-sm leading-6 text-slate-700">{output.summary}</p>}
            {output.findings && output.findings.length > 0 && (
              <ul className="mt-3 grid gap-1 text-sm text-slate-600">
                {output.findings.slice(0, 4).map((finding) => <li key={finding}>- {finding}</li>)}
              </ul>
            )}
          </div>
        ))}
      </div>
    </Card>
  );
}

function CitationPanel({ citations }: { citations: Record<string, unknown>[] }) {
  return (
    <Card>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-semibold text-ink">Citations</h2>
        <Badge>{citations.length}</Badge>
      </div>
      {citations.length === 0 ? (
        <p className="mt-4 text-sm text-slate-600">No citations were required or returned for this route.</p>
      ) : (
        <div className="mt-4 grid gap-3">
          {citations.map((citation, index) => (
            <div key={index} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
              <div className="font-semibold text-ink">{stringValue(citation.title) || `Citation ${index + 1}`}</div>
              {stringValue(citation.url) && (
                <a className="mt-1 block break-words text-bankred hover:underline" href={stringValue(citation.url)} target="_blank">
                  {stringValue(citation.url)}
                </a>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function EvidencePanel({ outputs }: { outputs: Record<string, AgentOutput> }) {
  const rows = Object.entries(outputs).flatMap(([agent, output]) =>
    ["judge_panel_agent", "guardrail_agent"].includes(agent)
      ? []
      : (output.evidence ?? []).map((item, index) => ({ agent, index, item }))
  );
  if (rows.length === 0) return null;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">Evidence reviewed</h2>
      <div className="mt-3 overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-slate-500">
            <tr>
              <th className="py-2 pr-4">Agent</th>
              <th className="py-2 pr-4">Evidence summary</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.agent}-${row.index}`} className="border-b border-slate-100">
                <td className="py-3 pr-4 font-medium text-ink">{formatLabel(row.agent)}</td>
                <td className="py-3 pr-4 text-slate-700">{summarizeEvidence(row.item)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function AuditPanel({ events }: { events: Array<Record<string, unknown>> }) {
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">Audit trail</h2>
      <div className="mt-4 grid gap-2">
        {events.map((event, index) => (
          <div key={index} className="grid gap-1 rounded-md border border-slate-200 bg-slate-50 p-3 text-sm md:grid-cols-[0.4fr_1fr]">
            <div className="font-medium text-ink">{formatLabel(stringValue(event.event) || `Event ${index + 1}`)}</div>
            <div className="text-slate-600">{summarizeAuditEvent(event)}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

type MarkdownBlock =
  | { type: "heading"; text: string }
  | { type: "paragraph"; text: string }
  | { type: "list"; items: string[] }
  | { type: "table"; headers: string[]; rows: string[][] };

function parseMarkdown(text: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  let listItems: string[] = [];
  let tableRows: string[][] = [];
  for (const rawLine of text.split("\n")) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      flushTable();
      continue;
    }
    if (isMarkdownTableLine(line)) {
      flushList();
      const cells = line
        .split("|")
        .map((cell) => cleanInline(cell.trim()))
        .filter(Boolean);
      if (cells.length > 0 && !cells.every((cell) => /^-+$/.test(cell))) {
        tableRows.push(cells);
      }
      continue;
    }
    if (line.startsWith("#")) {
      flushList();
      flushTable();
      blocks.push({ type: "heading", text: line.replace(/^#+\s*/, "") });
      continue;
    }
    if (line.startsWith("- ") || line.startsWith("* ")) {
      listItems.push(cleanInline(line.slice(2)));
      continue;
    }
    flushList();
    flushTable();
    blocks.push({ type: "paragraph", text: cleanInline(line) });
  }
  flushList();
  flushTable();
  return blocks;

  function flushList() {
    if (listItems.length > 0) {
      blocks.push({ type: "list", items: listItems });
      listItems = [];
    }
  }

  function flushTable() {
    if (tableRows.length > 0) {
      const [headers, ...rows] = tableRows;
      blocks.push({ type: "table", headers, rows });
      tableRows = [];
    }
  }
}

function cleanInline(value: string): string {
  return value
    .replace(/&rsquo;/g, "'")
    .replace(/&ldquo;|&rdquo;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\*\*/g, "")
    .replace(/`/g, "")
    .replace(/\s+#\s+/g, " ")
    .replace(/\b[a-z]+(?:_[a-z]+)+\b/g, (match) => formatLabel(match));
}

function isMarkdownTableLine(line: string): boolean {
  return line.startsWith("|") && line.endsWith("|") && line.includes("|");
}

function MarkdownTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return (
    <div className="overflow-auto rounded-md border border-slate-200">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            {headers.map((header) => <th key={header} className="px-3 py-2 font-semibold">{header}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-t border-slate-100">
              {headers.map((header, columnIndex) => (
                <td key={`${header}-${columnIndex}`} className="px-3 py-2 text-slate-700">
                  {row[columnIndex] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function summarizeValue(value: unknown): string {
  if (value == null) return "No value";
  if (typeof value === "string") return cleanInline(value);
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map(summarizeValue).join("; ");
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !["structured_output", "citations"].includes(key))
      .slice(0, 8)
      .map(([key, item]) => `${formatLabel(key)}: ${summarizeValue(item)}`);
    return entries.join(" | ");
  }
  return String(value);
}

function summarizeEvidence(value: unknown): string {
  if (!value || typeof value !== "object" || Array.isArray(value)) return summarizeValue(value);
  const record = value as Record<string, unknown>;
  const metadata = isRecord(record.metadata) ? record.metadata : {};
  const title = firstString(record.title, metadata.title, record.source, metadata.source, record.reference);
  const section = firstString(record.section, metadata.section);
  const organization = firstString(record.organization, metadata.organization, record.source_organization);
  const url = firstString(record.url, metadata.url);
  const excerpt = firstString(record.text, record.description, metadata.text, record.evidence);
  const score = typeof record.score === "number" ? `Relevance ${Math.round(record.score * 100)}%` : "";
  const parts = [
    title && `Source: ${cleanInline(title)}`,
    organization && `Organization: ${cleanInline(organization)}`,
    section && `Section: ${cleanInline(section)}`,
    excerpt && `Excerpt: ${truncate(cleanInline(excerpt), 260)}`,
    url && `URL: ${url}`,
    score,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(". ") : summarizeValue(value);
}

function summarizeAuditEvent(event: Record<string, unknown>): string {
  const entries = Object.entries(event)
    .filter(([key]) => key !== "event")
    .map(([key, value]) => {
      const displayValue = key === "agent" ? formatLabel(String(value)) : summarizeValue(value);
      return `${formatLabel(key)}: ${displayValue}`;
    });
  return entries.length > 0 ? entries.join(" | ") : "No additional audit detail";
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function firstString(...values: unknown[]): string {
  return values.find((value): value is string => typeof value === "string" && value.trim().length > 0) ?? "";
}

function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1).trim()}...` : value;
}
