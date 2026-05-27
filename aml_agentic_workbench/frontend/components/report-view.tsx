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
  return "result" in report ? report.result.final_report : undefined;
}

function getAuditTrace(report: ReportLike) {
  if ("audit_trace" in report) return report.audit_trace;
  return report.result.audit_trace ?? [];
}

export function ReportView({ report }: { report: ReportLike }) {
  const agentOutputs = getAgentOutputs(report);
  const finalReport = getFinalReport(report);
  const judgeScores = report.judge_scores ?? {};
  const exportAllowed = report.guardrail_status === "passed" && report.status === "completed";
  const citations = Object.values(agentOutputs).flatMap((output) => output.citations ?? []);

  return (
    <div className="grid gap-6">
      <Card>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold text-ink">AML Intelligence Package</h1>
            <p className="mt-2 text-sm text-slate-600">
              Human-review output. Model scores and typology indicators are not proof of suspicious activity.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone={report.guardrail_status === "passed" ? "success" : "danger"}>Guardrail {report.guardrail_status}</Badge>
            <Badge>{formatLabel(report.status)}</Badge>
            <Button disabled={!exportAllowed}>Export governed report</Button>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-4">
        <ScoreCard label="Overall judge" value={judgeScores.overall_score} />
        <ScoreCard label="Faithfulness" value={judgeScores.faithfulness} />
        <ScoreCard label="Citations" value={judgeScores.citation} />
        <ScoreCard label="Compliance" value={judgeScores.compliance} />
      </div>

      {finalReport ? (
        <Card>
          <ReadableMarkdown text={finalReport} />
        </Card>
      ) : (
        <EmptyState title="No report content" body="Run an analysis to generate a governed report." />
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_0.9fr]">
        <AgentSummary outputs={agentOutputs} />
        <CitationPanel citations={citations} />
      </div>

      <EvidencePanel outputs={agentOutputs} />
      <AuditPanel events={getAuditTrace(report)} />
    </div>
  );
}

function ScoreCard({ label, value }: { label: string; value?: number }) {
  return (
    <Card className="p-4">
      <div className="text-xs font-medium uppercase text-slate-500">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-ink">{value == null ? "n/a" : `${Math.round(value * 100)}%`}</div>
    </Card>
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
