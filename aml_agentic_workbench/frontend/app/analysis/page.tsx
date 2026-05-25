"use client";

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Shell } from "@/components/shell";
import { Badge, Button, Card, FieldLabel } from "@/components/ui";
import { RoutePreview } from "@/components/route-preview";
import { ReportView } from "@/components/report-view";
import { agents, defaultRoute, roles, tasks } from "@/lib/catalog";
import { api } from "@/lib/api";
import type { AgentName, AnalysisRequest, AnalysisResponse, SupportedRole, TaskType } from "@/types/api";

const allAgents = Object.keys(agents) as AgentName[];

export default function AnalysisPage() {
  const [role, setRole] = useState<SupportedRole>("investigator");
  const [task, setTask] = useState<TaskType>("investigator_summary");
  const [customerId, setCustomerId] = useState("CUST003");
  const [query, setQuery] = useState("Summarize velocity spike and new counterparty behaviour with careful AML wording.");
  const [requireFullReport, setRequireFullReport] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<AgentName[]>([]);

  const route = useMemo(
    () =>
      selectedAgents.length > 0
        ? ([...selectedAgents.filter((agent) => agent !== "guardrail_agent"), "guardrail_agent"] as AgentName[])
        : defaultRoute(role, task),
    [role, task, selectedAgents]
  );

  const mutation = useMutation<AnalysisResponse, Error, AnalysisRequest>({
    mutationFn: api.runAnalysis
  });

  function submit() {
    mutation.mutate({
      role,
      task_type: task,
      customer_id: customerId || undefined,
      query,
      selected_agents: selectedAgents.length > 0 ? selectedAgents : undefined,
      require_full_report: requireFullReport
    });
  }

  return (
    <Shell>
      <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="grid gap-6">
          <Card>
            <h1 className="text-2xl font-semibold text-ink">Analysis Workspace</h1>
            <p className="mt-2 text-sm text-slate-600">
              Configure a role-aware run. The route preview shows which agents will execute before the backend runs.
            </p>
            <div className="mt-6 grid gap-4">
              <div>
                <FieldLabel>Role</FieldLabel>
                <select value={role} onChange={(event) => setRole(event.target.value as SupportedRole)} className="w-full rounded-md border border-slate-300 p-2">
                  {Object.entries(roles).map(([value, detail]) => <option key={value} value={value}>{detail.label}</option>)}
                </select>
              </div>
              <div>
                <FieldLabel>Task type</FieldLabel>
                <select value={task} onChange={(event) => setTask(event.target.value as TaskType)} className="w-full rounded-md border border-slate-300 p-2">
                  {Object.entries(tasks).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </div>
              <div>
                <FieldLabel>Customer ID</FieldLabel>
                <input value={customerId} onChange={(event) => setCustomerId(event.target.value)} className="w-full rounded-md border border-slate-300 p-2" />
              </div>
              <div>
                <FieldLabel>Query</FieldLabel>
                <textarea value={query} onChange={(event) => setQuery(event.target.value)} rows={5} className="w-full rounded-md border border-slate-300 p-2" />
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input type="checkbox" checked={requireFullReport} onChange={(event) => setRequireFullReport(event.target.checked)} />
                Full intelligence report requested
              </label>
              <details open={advancedOpen} onToggle={(event) => setAdvancedOpen(event.currentTarget.open)} className="rounded-md border border-slate-200 p-3">
                <summary className="cursor-pointer text-sm font-semibold text-ink">Advanced: manual agent selection</summary>
                <div className="mt-3 grid gap-2">
                  {allAgents.filter((agent) => !["judge_panel_agent", "guardrail_agent", "evidence_assembly_agent"].includes(agent)).map((agent) => (
                    <label key={agent} className="flex items-start gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={selectedAgents.includes(agent)}
                        onChange={(event) => {
                          setSelectedAgents((current) =>
                            event.target.checked ? [...current, agent] : current.filter((item) => item !== agent)
                          );
                        }}
                      />
                      <span>{agents[agent].label}</span>
                    </label>
                  ))}
                </div>
              </details>
              <Button onClick={submit} disabled={mutation.isPending || !query.trim()}>
                {mutation.isPending ? "Running Analysis..." : "Run Analysis"}
              </Button>
              {mutation.isError && <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-danger">{mutation.error.message}</div>}
            </div>
          </Card>
          <RoutePreview route={route} />
        </div>
        <div>
          {mutation.data ? (
            <ReportView report={mutation.data} />
          ) : (
            <Card>
              <div className="flex items-center gap-2"><Badge>Empty state</Badge></div>
              <h2 className="mt-4 text-xl font-semibold text-ink">No run executed yet</h2>
              <p className="mt-2 text-sm text-slate-600">
                Results will show the governed report, judge scores, guardrail status, evidence, and audit trace.
              </p>
            </Card>
          )}
        </div>
      </div>
    </Shell>
  );
}
