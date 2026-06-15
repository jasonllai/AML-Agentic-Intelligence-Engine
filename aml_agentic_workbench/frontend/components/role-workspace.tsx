"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AgentProgressTimeline } from "@/components/agent-progress-timeline";
import { ReportView } from "@/components/report-view";
import { Badge, Button, Card, FieldLabel } from "@/components/ui";
import { agents, defaultRoute, roles, tasks } from "@/lib/catalog";
import { api } from "@/lib/api";
import { formatLabel } from "@/lib/utils";
import type { AgentName, AnalysisRequest, AnalysisResponse, AnalysisStreamEvent, SupportedRole, TaskType } from "@/types/api";

export function RoleWorkspace({
  role,
  initialCustomerId,
  initialModelFamily
}: {
  role: SupportedRole;
  initialCustomerId?: string;
  initialModelFamily?: string;
}) {
  const roleDetail = roles[role];
  const handoffCustomerId = initialCustomerId ?? "";
  const [task, setTask] = useState<TaskType>(roleDetail.defaultTask);
  const [customerId, setCustomerId] = useState(handoffCustomerId || roleDetail.defaultCustomerId);
  const [query, setQuery] = useState(
    handoffCustomerId && role === "investigator"
      ? `Investigate ${initialModelFamily ? `${formatLabel(initialModelFamily)} ` : ""}model-prioritized candidate ${handoffCustomerId} and return case feedback.`
      : roleDetail.defaultQuery
  );

  const route = useMemo(() => defaultRoute(role, task), [role, task]);
  const mutation = useMutation<AnalysisResponse, Error, AnalysisRequest>({ mutationFn: api.runAnalysis });
  const runPhase = mutation.isPending ? "running" : mutation.isError ? "failed" : mutation.data ? "completed" : "idle";
  const isDataScientist = role === "data_scientist";
  const usesStream = role === "investigator" && task === "investigate_model_prioritized_candidate";
  const [streamEvents, setStreamEvents] = useState<AnalysisStreamEvent[]>([]);
  const [streamReport, setStreamReport] = useState<AnalysisResponse | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const activeReport = usesStream ? streamReport : mutation.data;
  const activePhase = usesStream
    ? isStreaming ? "running" : streamError ? "failed" : streamReport ? "completed" : "idle"
    : runPhase;
  const isRunning = mutation.isPending || isStreaming;

  function selectTask(nextTask: TaskType) {
    setTask(nextTask);
    setQuery(queryFor(role, nextTask));
    setStreamEvents([]);
    setStreamReport(null);
    setStreamError(null);
  }

  function submit() {
    const payload = {
      role,
      task_type: task,
      customer_id: customerId || undefined,
      query,
      require_full_report: false
    };
    if (usesStream) {
      void submitStream(payload);
      return;
    }
    mutation.mutate(payload);
  }

  async function submitStream(payload: AnalysisRequest) {
    setIsStreaming(true);
    setStreamEvents([]);
    setStreamReport(null);
    setStreamError(null);
    try {
      await api.runAnalysisStream(payload, {
        onEvent: (event) => setStreamEvents((current) => [...current, event]),
        onComplete: (response) => setStreamReport(response)
      });
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : "Streaming analysis failed.");
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <div className="grid gap-6">
      <section className="rounded-lg border border-slate-200 bg-white shadow-soft">
        <div className="grid gap-0 xl:grid-cols-[360px_1fr]">
          <aside className="border-b border-slate-200 bg-slate-50 p-5 xl:border-b-0 xl:border-r">
            <Badge tone="danger">{formatLabel(role)}</Badge>
            <h1 className="mt-4 text-3xl font-semibold text-ink">{roleDetail.label}</h1>
            <p className="mt-3 text-sm leading-6 text-slate-600">{roleDetail.focus}</p>

            <div className="mt-6">
              <FieldLabel>Primary role function</FieldLabel>
              <div className="grid gap-2">
                {roleDetail.actions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => selectTask(action)}
                    className={[
                      "rounded-md border p-3 text-left text-sm transition",
                      task === action
                        ? "border-red-200 bg-white text-bankred shadow-sm"
                        : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    ].join(" ")}
                  >
                    <span className="block font-semibold">{tasks[action]}</span>
                    <span className="mt-1 block text-xs leading-5 text-slate-500">{roleDetail.reportStyle}</span>
                  </button>
                ))}
              </div>
            </div>
          </aside>

          <div className="grid gap-5 p-5 lg:p-6">
            <div className="grid gap-4">
              <Card className="border-slate-200 shadow-none">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-xl font-semibold text-ink">Workflow request</h2>
                    <p className="mt-1 text-sm text-slate-600">{requestHelp(role)}</p>
                  </div>
                  <Badge>{route.length} workflow steps</Badge>
                </div>

                <div className="mt-5 grid gap-4">
                  {!isDataScientist && (
                    <>
                      <div>
                        <FieldLabel>Customer ID</FieldLabel>
                        <input
                          value={customerId}
                          onChange={(event) => setCustomerId(event.target.value)}
                          placeholder="Customer ID"
                          className="w-full rounded-md border border-slate-300 bg-white p-2.5 text-sm"
                        />
                      </div>

                      <details className="rounded-md border border-slate-200 bg-slate-50 p-3">
                        <summary className="cursor-pointer text-sm font-semibold text-ink">Advanced</summary>
                        <div className="mt-3">
                          <FieldLabel>Workflow instruction</FieldLabel>
                          <textarea
                            value={query}
                            onChange={(event) => setQuery(event.target.value)}
                            rows={5}
                            className="w-full rounded-md border border-slate-300 bg-white p-3 text-sm leading-6"
                          />
                        </div>
                      </details>
                    </>
                  )}

                  <Button onClick={submit} disabled={isRunning || !query.trim()} className="w-full md:w-auto">
                    {isRunning ? "Workflow is running..." : `Run ${tasks[task]}`}
                  </Button>
                  {(mutation.isError || streamError) && (
                    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-danger">
                      {friendlyError(streamError ?? mutation.error?.message ?? "Workflow failed.")}
                    </div>
                  )}
                </div>
              </Card>

            </div>

            <div className="grid gap-5">
              <AgentProgressTimeline
                route={route}
                executedAgents={activeReport?.executed_agents as AgentName[] | undefined}
                phase={activePhase}
                streamEvents={usesStream ? streamEvents : []}
                streamMode={usesStream}
              />
            </div>
          </div>
        </div>
      </section>

      {activeReport ? (
        <ReportView report={activeReport} />
      ) : (
        <Card className="border-dashed bg-white/70">
          <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
            <div>
              <h2 className="text-2xl font-semibold text-ink">Report workspace is ready</h2>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                After execution, this area becomes the governed workflow report with candidate packages,
                investigation feedback, judge scores, evidence, and audit history.
              </p>
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {route.map((agent) => (
                <div key={agent} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                  <div className="font-semibold text-ink">{agents[agent]?.label}</div>
                  <div className="mt-1 text-slate-600">{agents[agent]?.sections.join(", ")}</div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function queryFor(role: SupportedRole, task: TaskType): string {
  if (task === "generate_model_driven_candidates") {
    return "Generate ranked model-driven AML investigation candidates for investigator handoff.";
  }
  if (task === "investigate_model_prioritized_candidate") {
    return "Investigate this model-prioritized candidate and return case feedback.";
  }
  if (task === "typology_mapping" || task === "compliance_typology_review") {
    return "Map this activity to official AML typology indicators with citations and non-conclusive wording.";
  }
  if (task === "feature_quality_review") {
    return "Review feature quality, stability, leakage risk, and useful feature improvements.";
  }
  if (task === "model_risk_explanation" || task === "model_validation_review") {
    return "Explain the model score, uncertainty, strongest drivers, and validation concerns.";
  }
  if (task === "customer_behaviour_analysis" || task === "investigator_summary") {
    return "Summarize unusual customer behaviour, evidence, limitations, and next review steps.";
  }
  return roles[role].defaultQuery;
}

function requestHelp(role: SupportedRole): string {
  if (role === "data_scientist") {
    return "Run population scoring and produce a ranked candidate handoff for investigators.";
  }
  if (role === "investigator") {
    return "Review one model-prioritized customer and return evidence, disposition, and model feedback.";
  }
  return "Configure the governed workflow before the route runs.";
}

function friendlyError(message: string): string {
  if (message.includes("ingest_pgvector")) {
    return "The RAG knowledge base is not ready. Start PostgreSQL/pgvector and run the RAG ingestion command before typology routes.";
  }
  try {
    const parsed = JSON.parse(message);
    return parsed.detail ?? message;
  } catch {
    return message;
  }
}
