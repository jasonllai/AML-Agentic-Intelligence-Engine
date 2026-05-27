"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { AgentProgressTimeline } from "@/components/agent-progress-timeline";
import { ReportView } from "@/components/report-view";
import { RoutePreview } from "@/components/route-preview";
import { Badge, Button, Card, FieldLabel } from "@/components/ui";
import { agents, defaultRoute, roles, tasks } from "@/lib/catalog";
import { api } from "@/lib/api";
import { formatLabel } from "@/lib/utils";
import type { AgentName, AnalysisRequest, AnalysisResponse, SupportedRole, TaskType } from "@/types/api";

export function RoleWorkspace({ role }: { role: SupportedRole }) {
  const roleDetail = roles[role];
  const [task, setTask] = useState<TaskType>(roleDetail.defaultTask);
  const [customerId, setCustomerId] = useState(roleDetail.defaultCustomerId);
  const [query, setQuery] = useState(roleDetail.defaultQuery);
  const [requireFullReport, setRequireFullReport] = useState(false);

  const route = useMemo(() => defaultRoute(role, task), [role, task]);
  const mutation = useMutation<AnalysisResponse, Error, AnalysisRequest>({ mutationFn: api.runAnalysis });
  const runPhase = mutation.isPending ? "running" : mutation.isError ? "failed" : mutation.data ? "completed" : "idle";

  function selectTask(nextTask: TaskType) {
    setTask(nextTask);
    setRequireFullReport(nextTask === "full_intelligence_report");
    setQuery(queryFor(role, nextTask));
  }

  function submit() {
    mutation.mutate({
      role,
      task_type: task,
      customer_id: customerId || undefined,
      query,
      require_full_report: requireFullReport
    });
  }

  return (
    <div className="grid gap-6">
      <section className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr]">
        <Card>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <Badge>{formatLabel(role)}</Badge>
              <h1 className="mt-4 text-3xl font-semibold text-ink">{roleDetail.label} Workspace</h1>
              <p className="mt-3 text-sm leading-6 text-slate-600">{roleDetail.focus}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-4">
            <div>
              <FieldLabel>Available actions</FieldLabel>
              <div className="grid gap-2 md:grid-cols-3">
                {roleDetail.actions.map((action) => (
                  <button
                    key={action}
                    type="button"
                    onClick={() => selectTask(action)}
                    className={[
                      "rounded-md border p-3 text-left text-sm transition",
                      task === action ? "border-red-200 bg-red-50 text-bankred" : "border-slate-200 bg-white text-slate-700 hover:border-slate-300"
                    ].join(" ")}
                  >
                    <span className="font-semibold">{tasks[action]}</span>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-[0.7fr_1.3fr]">
              <div>
                <FieldLabel>Customer ID</FieldLabel>
                <input
                  value={customerId}
                  onChange={(event) => setCustomerId(event.target.value)}
                  placeholder={role === "compliance_strategy" ? "Optional" : "Customer ID"}
                  className="w-full rounded-md border border-slate-300 p-2 text-sm"
                />
              </div>
              <label className="mt-7 flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={requireFullReport}
                  onChange={(event) => setRequireFullReport(event.target.checked)}
                />
                Full intelligence package
              </label>
            </div>

            <div>
              <FieldLabel>Question for the agents</FieldLabel>
              <textarea
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                rows={5}
                className="w-full rounded-md border border-slate-300 p-3 text-sm leading-6"
              />
            </div>

            <Button onClick={submit} disabled={mutation.isPending || !query.trim()}>
              {mutation.isPending ? "Agents are working..." : `Run ${tasks[task]}`}
            </Button>
            {mutation.isError && (
              <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-danger">
                {friendlyError(mutation.error.message)}
              </div>
            )}
          </div>
        </Card>

        <div className="grid gap-6">
          <RoutePreview route={route} />
          <AgentProgressTimeline route={route} executedAgents={mutation.data?.executed_agents as AgentName[] | undefined} phase={runPhase} />
        </div>
      </section>

      {mutation.data ? (
        <ReportView report={mutation.data} />
      ) : (
        <Card>
          <h2 className="text-xl font-semibold text-ink">Output will appear here</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            The completed package will be rendered as readable AML sections, evidence cards, citation tables,
            judge scores, and audit events. Raw structured payloads stay out of the primary view.
          </p>
          <div className="mt-5 grid gap-2 md:grid-cols-2">
            {route.map((agent) => (
              <div key={agent} className="rounded-md border border-slate-200 bg-slate-50 p-3 text-sm">
                <div className="font-semibold text-ink">{agents[agent]?.label}</div>
                <div className="mt-1 text-slate-600">{agents[agent]?.sections.join(", ")}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

function queryFor(role: SupportedRole, task: TaskType): string {
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
