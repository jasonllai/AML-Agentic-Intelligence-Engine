"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Shell } from "@/components/shell";
import { Badge, Button, Card, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { formatLabel } from "@/lib/utils";
import type { EvaluationCaseResult, EvaluationRunSummary } from "@/types/api";

function pct(value: number | undefined) {
  if (value == null) return "n/a";
  return `${Math.round(value * 100)}%`;
}

export default function EvaluationsPage() {
  const queryClient = useQueryClient();
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const runsQuery = useQuery({ queryKey: ["evaluations"], queryFn: api.evaluations });
  const generateMutation = useMutation({
    mutationFn: () => api.generateGoldenDataset(100)
  });
  const runMutation = useMutation({
    mutationFn: () => api.runEvaluation(20),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["evaluations"] });
    }
  });

  const latestRun: EvaluationRunSummary | undefined = runMutation.data ?? runsQuery.data?.[0];
  const failures = latestRun?.cases.filter((testCase) => !testCase.passed) ?? [];
  const selectedCase = useMemo(() => {
    const cases = latestRun?.cases ?? [];
    return cases.find((testCase) => testCase.case_id === selectedCaseId) ?? failures[0] ?? cases[0];
  }, [failures, latestRun?.cases, selectedCaseId]);

  return (
    <Shell>
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-ink">System Evaluations</h1>
          <p className="mt-2 text-sm text-slate-600">
            Golden-dataset regression checks for routing, guardrails, citations, RAG relevance, and judge metrics.
          </p>
        </div>
        <div className="flex gap-3">
          <Button onClick={() => generateMutation.mutate()} disabled={generateMutation.isPending}>
            {generateMutation.isPending ? "Generating..." : "Generate Golden Dataset"}
          </Button>
          <Button onClick={() => runMutation.mutate()} disabled={runMutation.isPending}>
            {runMutation.isPending ? "Running..." : "Run Evaluation"}
          </Button>
        </div>
      </div>

      {(generateMutation.isError || runMutation.isError || runsQuery.isError) && (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-danger">
          {generateMutation.error?.message ?? runMutation.error?.message ?? runsQuery.error?.message}
        </div>
      )}

      {!latestRun && runsQuery.isLoading && <EmptyState title="Loading evaluations" body="Checking recent evaluation runs." />}
      {!latestRun && !runsQuery.isLoading && (
        <EmptyState title="No evaluation runs" body="Generate a golden dataset or run the default suite." />
      )}

      {latestRun && (
        <div className="grid gap-6">
          <div className="grid gap-4 md:grid-cols-4">
            <MetricCard label="Overall" value={pct(latestRun.overall_score)} />
            <MetricCard label="Cases" value={`${latestRun.passed_count}/${latestRun.case_count}`} />
            <MetricCard label="Route" value={pct(latestRun.metrics.route_correctness)} />
            <MetricCard label="Guardrails" value={pct(latestRun.metrics.guardrail_correctness)} />
            <MetricCard label="Citations" value={pct(latestRun.metrics.citation_presence)} />
            <MetricCard label="RAG relevance" value={pct(latestRun.metrics.rag_retrieval_relevance)} />
            <MetricCard label="Faithfulness" value={pct(latestRun.metrics.faithfulness)} />
            <MetricCard label="Answer relevance" value={pct(latestRun.metrics.answer_relevance)} />
          </div>

          <div className="grid gap-6 lg:grid-cols-[1.1fr_0.9fr]">
            <Card>
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-ink">Failures</h2>
                <Badge tone={failures.length === 0 ? "success" : "danger"}>{failures.length} failing</Badge>
              </div>
              <CaseTable cases={failures.length ? failures : latestRun.cases} onSelect={setSelectedCaseId} />
            </Card>

            <Card>
              <h2 className="text-lg font-semibold text-ink">Case Detail</h2>
              {selectedCase ? <CaseDetail testCase={selectedCase} /> : <p className="mt-3 text-sm text-slate-600">No case selected.</p>}
            </Card>
          </div>
        </div>
      )}
    </Shell>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
    </Card>
  );
}

function CaseTable({ cases, onSelect }: { cases: EvaluationCaseResult[]; onSelect: (caseId: string) => void }) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b text-slate-500">
          <tr>
            <th className="py-3 pr-4">Case</th>
            <th className="py-3 pr-4">Role</th>
            <th className="py-3 pr-4">Task</th>
            <th className="py-3 pr-4">Route</th>
            <th className="py-3 pr-4">Guardrail</th>
            <th className="py-3 pr-4">Status</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((testCase) => (
            <tr key={testCase.case_id} className="border-b border-slate-100">
              <td className="py-3 pr-4 font-mono text-xs">
                <button onClick={() => onSelect(testCase.case_id)} className="text-left text-bankred hover:underline">
                  {testCase.case_id}
                </button>
              </td>
              <td className="py-3 pr-4">{formatLabel(testCase.role)}</td>
              <td className="py-3 pr-4">{formatLabel(testCase.task_type)}</td>
              <td className="py-3 pr-4">{pct(testCase.metrics.route_correctness)}</td>
              <td className="py-3 pr-4">{pct(testCase.metrics.guardrail_correctness)}</td>
              <td className="py-3 pr-4"><Badge tone={testCase.passed ? "success" : "danger"}>{testCase.passed ? "pass" : "fail"}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CaseDetail({ testCase }: { testCase: EvaluationCaseResult }) {
  return (
    <div className="mt-4 grid gap-4 text-sm">
      <div>
        <div className="text-xs font-medium uppercase text-slate-500">Query</div>
        <p className="mt-1 text-slate-800">{testCase.query}</p>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <DetailBlock label="Expected route" value={formatRoute(testCase.expected_agents)} />
        <DetailBlock label="Actual route" value={formatRoute(testCase.actual_agents) || "none"} />
        <DetailBlock label="Expected guardrail" value={testCase.expected_guardrail_outcome} />
        <DetailBlock label="Actual guardrail" value={testCase.actual_guardrail_outcome} />
      </div>
      <div>
        <div className="text-xs font-medium uppercase text-slate-500">Judge rationale</div>
        <div className="mt-2 grid gap-2">
          {Object.entries(testCase.judge_rationale).map(([criterion, rationale]) => (
            <div key={criterion} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="font-medium text-ink">{formatLabel(criterion)}</div>
              <p className="mt-1 text-slate-600">{rationale}</p>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="text-xs font-medium uppercase text-slate-500">Retrieved citations</div>
        <div className="mt-2 grid max-h-56 gap-2 overflow-auto">
          {testCase.retrieved_citations.length === 0 && <p className="text-slate-600">No citations returned for this case.</p>}
          {testCase.retrieved_citations.map((citation, index) => (
            <div key={index} className="rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="font-medium text-ink">{stringValue(citation.title) || `Citation ${index + 1}`}</div>
              {stringValue(citation.url) && <div className="mt-1 break-words text-bankred">{stringValue(citation.url)}</div>}
            </div>
          ))}
        </div>
      </div>
      {testCase.failure_reasons.length > 0 && (
        <div>
          <div className="text-xs font-medium uppercase text-slate-500">Failure reasons</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {testCase.failure_reasons.map((reason) => <Badge key={reason} tone="danger">{reason}</Badge>)}
          </div>
        </div>
      )}
    </div>
  );
}

function DetailBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 p-3">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-1 break-words text-slate-800">{value}</div>
    </div>
  );
}

function formatRoute(route: string[]) {
  return route.map((agent) => formatLabel(agent)).join(" -> ");
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}
