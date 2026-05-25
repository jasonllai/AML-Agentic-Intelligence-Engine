"use client";

import { useQuery } from "@tanstack/react-query";
import { Shell } from "@/components/shell";
import { EmptyState } from "@/components/ui";
import { ReportView } from "@/components/report-view";
import { api } from "@/lib/api";

export default function ReportPage({ params }: { params: { runId: string } }) {
  const query = useQuery({
    queryKey: ["report", params.runId],
    queryFn: () => api.report(params.runId)
  });

  return (
    <Shell>
      {query.isLoading && <EmptyState title="Loading report" body="Retrieving the latest run details." />}
      {query.isError && <EmptyState title="Report unavailable" body={query.error.message} />}
      {query.data && <ReportView report={query.data} />}
    </Shell>
  );
}
