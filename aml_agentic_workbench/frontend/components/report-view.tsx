"use client";

import type { AgentOutput, AnalysisResponse, ReportDetailResponse } from "@/types/api";
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
  if ("result" in report) return report.result.final_report;
  return undefined;
}

export function ReportView({ report }: { report: ReportLike }) {
  const agentOutputs = getAgentOutputs(report);
  const finalReport = getFinalReport(report);
  const judgeScores = report.judge_scores ?? {};
  const exportAllowed = report.guardrail_status === "passed" && report.status === "completed";

  return (
    <div className="grid gap-6">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-ink">Generated AML Intelligence Report</h1>
            <p className="mt-2 text-sm text-slate-600">
              Model score is not proof of suspicious activity. Outputs require human review before action.
            </p>
          </div>
          <div className="flex gap-2">
            <Badge tone={report.guardrail_status === "passed" ? "success" : "danger"}>{report.guardrail_status}</Badge>
            <Button disabled={!exportAllowed}>Export report</Button>
          </div>
        </div>
      </Card>

      {finalReport ? (
        <Card>
          <pre className="whitespace-pre-wrap font-sans text-sm leading-6 text-slate-800">{finalReport}</pre>
        </Card>
      ) : (
        <EmptyState title="No report content" body="Run an analysis to generate a governed report." />
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        {Object.entries(judgeScores).map(([key, value]) => (
          <Card key={key}>
            <div className="text-sm text-slate-500">{formatLabel(key)}</div>
            <div className="mt-2 text-3xl font-semibold text-ink">{Math.round(value * 100)}%</div>
          </Card>
        ))}
      </div>

      <Card>
        <h2 className="text-lg font-semibold text-ink">Executed Agents</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {report.executed_agents.map((agent) => <Badge key={agent}>{agents[agent]?.label ?? formatLabel(agent)}</Badge>)}
        </div>
      </Card>

      <AgentSection title="Evidence Table" outputs={agentOutputs} field="evidence" />
      <StructuredSection title="Typology Mapping Table" output={agentOutputs.typology_mapping_agent} />
      <StructuredSection title="Model Explanation Table" output={agentOutputs.model_explanation_agent} />
      <StructuredSection title="Feature Critique Table" output={agentOutputs.feature_critic_agent} />

      <Card>
        <h2 className="text-lg font-semibold text-ink">Audit Metadata</h2>
        <pre className="mt-3 overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-100">
          {JSON.stringify("audit_trace" in report ? report.audit_trace : report.result.audit_trace ?? [], null, 2)}
        </pre>
      </Card>
    </div>
  );
}

function AgentSection({ title, outputs, field }: { title: string; outputs: Record<string, AgentOutput>; field: "evidence" }) {
  const rows = Object.entries(outputs).flatMap(([agent, output]) =>
    (output[field] ?? []).map((item, index) => ({ agent, index, item }))
  );
  if (rows.length === 0) return null;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-3 overflow-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b text-slate-500">
            <tr><th className="py-2">Agent</th><th className="py-2">Evidence</th></tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.agent}-${row.index}`} className="border-b border-slate-100">
                <td className="py-2 pr-4 font-medium">{formatLabel(row.agent)}</td>
                <td className="py-2"><code className="text-xs">{JSON.stringify(row.item)}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function StructuredSection({ title, output }: { title: string; output?: AgentOutput }) {
  if (!output?.structured_output) return null;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <pre className="mt-3 overflow-auto rounded-md bg-slate-50 p-4 text-xs text-slate-700">
        {JSON.stringify(output.structured_output, null, 2)}
      </pre>
    </Card>
  );
}
