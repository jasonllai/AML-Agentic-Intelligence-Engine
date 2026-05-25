"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/shell";
import { Badge, Card, EmptyState } from "@/components/ui";
import { api } from "@/lib/api";
import { formatLabel } from "@/lib/utils";

export default function HistoryPage() {
  const query = useQuery({ queryKey: ["reports"], queryFn: api.reports });

  return (
    <Shell>
      <div className="mb-6">
        <h1 className="text-3xl font-semibold text-ink">Run History</h1>
        <p className="mt-2 text-slate-600">Previous analysis runs from the local workbench backend.</p>
      </div>
      {query.isLoading && <EmptyState title="Loading runs" body="Checking report history." />}
      {query.isError && <EmptyState title="History unavailable" body={query.error.message} />}
      {query.data?.reports.length === 0 && <EmptyState title="No previous runs" body="Run an analysis to populate this table." />}
      {query.data && query.data.reports.length > 0 && (
        <Card>
          <div className="overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b text-slate-500">
                <tr>
                  <th className="py-3">Run ID</th>
                  <th className="py-3">Role</th>
                  <th className="py-3">Task</th>
                  <th className="py-3">Status</th>
                  <th className="py-3">Judge</th>
                  <th className="py-3">Guardrail</th>
                  <th className="py-3">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {query.data.reports.map((run) => (
                  <tr key={run.run_id} className="border-b border-slate-100">
                    <td className="py-3 pr-4 font-mono text-xs">
                      <Link href={`/reports/${run.run_id}`} className="text-bankred hover:underline">{run.run_id}</Link>
                    </td>
                    <td className="py-3 pr-4">{formatLabel(run.role)}</td>
                    <td className="py-3 pr-4">{formatLabel(run.task_type)}</td>
                    <td className="py-3 pr-4"><Badge>{run.status}</Badge></td>
                    <td className="py-3 pr-4">{run.overall_judge_score == null ? "n/a" : `${Math.round(run.overall_judge_score * 100)}%`}</td>
                    <td className="py-3 pr-4"><Badge tone={run.guardrail_status === "passed" ? "success" : "danger"}>{run.guardrail_status}</Badge></td>
                    <td className="py-3 pr-4">{new Date(run.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </Shell>
  );
}
