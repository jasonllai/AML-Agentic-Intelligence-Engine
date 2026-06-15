"use client";

import { FormEvent, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Shell } from "@/components/shell";
import { Badge, Button, Card, FieldLabel } from "@/components/ui";
import { formatLabel } from "@/lib/utils";
import type { CustomerDataRecord, CustomerDataSection } from "@/types/api";

const defaultCustomerId = "SYNID0200567030";

export default function CustomerDataPage() {
  const [customerInput, setCustomerInput] = useState(defaultCustomerId);
  const [customerId, setCustomerId] = useState(defaultCustomerId);
  const [source, setSource] = useState("all");
  const [limit, setLimit] = useState(100);

  const sourcesQuery = useQuery({
    queryKey: ["customer-data-sources"],
    queryFn: api.customerDataSources
  });
  const dataQuery = useQuery({
    queryKey: ["customer-data", customerId, source, limit],
    queryFn: () => api.customerData(customerId, source, limit),
    enabled: Boolean(customerId)
  });

  const sourceOptions = useMemo(
    () => [
      { source: "all", label: "All sources" },
      ...(sourcesQuery.data?.sources ?? []).map((item) => ({ source: item.source, label: item.label }))
    ],
    [sourcesQuery.data?.sources]
  );

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCustomerId(customerInput.trim());
  }

  const sections = dataQuery.data?.sections ?? [];
  const summary = dataQuery.data?.summary;

  return (
    <Shell>
    <div className="grid gap-6">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Badge tone="danger">Customer evidence</Badge>
            <h1 className="mt-3 text-3xl font-semibold text-ink">View Customer Data</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
              Search a customer ID and inspect available KYC, engineered features, and transaction-channel records from
              the local real-data sources.
            </p>
          </div>
          <Badge>{sourcesQuery.data?.sources.length ?? 0} sources indexed</Badge>
        </div>

        <form onSubmit={submit} className="mt-5 grid gap-3 lg:grid-cols-[1fr_220px_160px_auto]">
          <div>
            <FieldLabel>Customer ID</FieldLabel>
            <input
              value={customerInput}
              onChange={(event) => setCustomerInput(event.target.value)}
              placeholder="SYNID0200567030"
              className="w-full rounded-md border border-slate-300 bg-white p-2.5 text-sm"
            />
          </div>
          <div>
            <FieldLabel>Source</FieldLabel>
            <select
              value={source}
              onChange={(event) => setSource(event.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white p-2.5 text-sm"
            >
              {sourceOptions.map((item) => (
                <option key={item.source} value={item.source}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <FieldLabel>Rows per source</FieldLabel>
            <select
              value={limit}
              onChange={(event) => setLimit(Number(event.target.value))}
              className="w-full rounded-md border border-slate-300 bg-white p-2.5 text-sm"
            >
              {[25, 50, 100, 250, 500].map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <Button type="submit" className="w-full" disabled={!customerInput.trim() || dataQuery.isFetching}>
              {dataQuery.isFetching ? "Loading..." : "Search"}
            </Button>
          </div>
        </form>
      </section>

      {dataQuery.isError && (
        <Card className="border-red-200 bg-red-50">
          <div className="text-sm font-semibold text-danger">Unable to load customer data</div>
          <p className="mt-2 text-sm text-red-700">{dataQuery.error.message}</p>
        </Card>
      )}

      {summary && (
        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <SummaryMetric label="Customer type" value={summary.customer_type ? formatLabel(summary.customer_type) : "Unknown"} />
          <SummaryMetric label="Available sources" value={summary.available_sources.length} />
          <SummaryMetric label="Transaction sources" value={summary.transaction_source_count} />
          <SummaryMetric label="Total records" value={summary.total_records} />
        </section>
      )}

      {!dataQuery.isFetching && dataQuery.data && sections.length === 0 && (
        <Card className="border-dashed bg-white/70">
          <h2 className="text-xl font-semibold text-ink">No customer records found</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            No rows were found for <span className="font-mono">{customerId}</span> in the selected source set.
          </p>
        </Card>
      )}

      <div className="grid gap-4">
        {sections.map((section) => (
          <SourceSection key={section.source} section={section} />
        ))}
      </div>
    </div>
    </Shell>
  );
}

function SummaryMetric({ label, value }: { label: string; value: string | number }) {
  return (
    <Card className="shadow-none">
      <div className="text-xs font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
    </Card>
  );
}

function SourceSection({ section }: { section: CustomerDataSection }) {
  const visibleColumns = preferredColumns(section);
  return (
    <section className="rounded-lg border border-slate-200 bg-white shadow-soft">
      <div className="grid gap-4 border-b border-slate-200 px-4 py-4 xl:grid-cols-[minmax(0,1fr)_minmax(560px,auto)]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-xl font-semibold text-ink">{section.label}</h2>
            <Badge>{formatLabel(section.source_type)}</Badge>
            {section.truncated && <Badge tone="warning">Showing first {section.returned_count} of {section.row_count}</Badge>}
          </div>
          <p className="mt-1 text-sm text-slate-600">
            {section.row_count} matching record{section.row_count === 1 ? "" : "s"} in this source.
          </p>
        </div>
        {section.source_type === "transaction" && <TransactionSummary summary={section.summary} />}
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              {visibleColumns.map((column) => (
                <th key={column} className="whitespace-nowrap border-b border-slate-200 px-3 py-2 font-semibold">
                  {formatLabel(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {section.records.map((record, index) => (
              <tr key={`${section.source}-${index}`} className="border-b border-slate-100 last:border-0">
                {visibleColumns.map((column) => (
                  <td key={column} className="max-w-[280px] whitespace-nowrap px-3 py-2 text-slate-700">
                    {formatCell(record[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function TransactionSummary({ summary }: { summary: Record<string, unknown> }) {
  return (
    <div className="grid w-full gap-2 text-xs sm:grid-cols-3 xl:grid-cols-[repeat(3,minmax(100px,1fr))_minmax(240px,1.6fr)]">
      <MiniMetric label="Total" value={formatMoney(summary.total_amount)} />
      <MiniMetric label="Credit" value={formatMoney(summary.credit_amount)} />
      <MiniMetric label="Debit" value={formatMoney(summary.debit_amount)} />
      <DateRangeMetric
        earliest={summary.earliest_transaction_date}
        latest={summary.latest_transaction_date}
      />
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2">
      <div className="font-semibold uppercase text-slate-500">{label}</div>
      <div className="mt-1 max-w-[160px] truncate text-slate-800">{value}</div>
    </div>
  );
}

function DateRangeMetric({ earliest, latest }: { earliest: unknown; latest: unknown }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-2 sm:col-span-3 xl:col-span-1">
      <div className="font-semibold uppercase text-slate-500">Date range</div>
      <div className="mt-1 grid gap-1 font-mono text-[11px] leading-4 text-slate-800">
        <span>From {formatMetricValue(earliest)}</span>
        <span>To {formatMetricValue(latest)}</span>
      </div>
    </div>
  );
}

function preferredColumns(section: CustomerDataSection): string[] {
  const preferred = [
    "transaction_id",
    "customer_id",
    "amount_cad",
    "debit_credit",
    "transaction_datetime",
    "country",
    "province",
    "city",
    "occupation_title",
    "industry",
    "income",
    "sales"
  ];
  const ordered = preferred.filter((column) => section.columns.includes(column));
  const remaining = section.columns.filter((column) => !ordered.includes(column));
  return [...ordered, ...remaining].slice(0, 14);
}

function formatCell(value: CustomerDataRecord[string]): string {
  if (value == null || value === "") return "n/a";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

function formatMoney(value: unknown): string {
  if (typeof value !== "number") return "n/a";
  return new Intl.NumberFormat("en-CA", { style: "currency", currency: "CAD", maximumFractionDigits: 0 }).format(value);
}

function formatMetricValue(value: unknown): string {
  if (value == null || value === "") return "n/a";
  return String(value);
}
