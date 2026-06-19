"use client";

import { useEffect, useMemo, useState } from "react";
import { agents } from "@/lib/catalog";
import { formatLabel } from "@/lib/utils";
import type { AgentName, AnalysisStreamEvent } from "@/types/api";

type RunPhase = "idle" | "running" | "completed" | "failed";

export function AgentProgressTimeline({
  route,
  executedAgents = [],
  phase,
  streamEvents = [],
  streamMode = false
}: {
  route: AgentName[];
  executedAgents?: AgentName[];
  phase: RunPhase;
  streamEvents?: AnalysisStreamEvent[];
  streamMode?: boolean;
}) {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    if (phase !== "running") {
      setActiveIndex(0);
      return;
    }
    const timer = window.setInterval(() => {
      setActiveIndex((current) => Math.min(current + 1, Math.max(route.length - 1, 0)));
    }, 1300);
    return () => window.clearInterval(timer);
  }, [phase, route.length]);

  const steps = useMemo(
    () =>
      route.map((agent, index) => {
        const actuallyCompleted = executedAgents.includes(agent);
        const estimatedCompleted = phase === "running" && index < activeIndex;
        const isActive = phase === "running" && index === activeIndex;
        const isCompleted = phase === "completed" ? actuallyCompleted : estimatedCompleted;
        return { agent, index, isActive, isCompleted };
      }),
    [activeIndex, executedAgents, phase, route]
  );

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-soft">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-ink">Execution Flow</h2>
          <p className="mt-1 text-sm text-slate-600">
            {streamEvents.length > 0
              ? "Live planner decisions, agent outputs, critic feedback, and final governance checkpoints."
              : phase === "running"
              ? "Estimated live progress while the backend completes the non-streaming analysis request."
              : "Actual completed agents appear after the backend returns."}
          </p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
          {formatLabel(phase)}
        </span>
      </div>
      {streamEvents.length > 0 || (streamMode && phase !== "idle") ? (
        <StreamEventDisplay events={streamEvents} phase={phase} />
      ) : (
        <EstimatedRouteRows steps={steps} />
      )}
    </section>
  );
}

function EstimatedRouteRows({
  steps
}: {
  steps: Array<{ agent: AgentName; index: number; isActive: boolean; isCompleted: boolean }>;
}) {
  return (
    <div className="mt-5 grid gap-3">
      {steps.map((step) => (
        <div
          key={`${step.agent}-${step.index}`}
          className={[
            "grid gap-3 rounded-md border p-3 md:grid-cols-[auto_1fr]",
            step.isActive ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50",
            step.isCompleted ? "border-green-200 bg-green-50" : ""
          ].join(" ")}
        >
          <div
            className={[
              "flex h-8 w-8 items-center justify-center rounded-full text-sm font-semibold",
              step.isCompleted ? "bg-green-600 text-white" : step.isActive ? "bg-bankred text-white" : "bg-white text-slate-500"
            ].join(" ")}
          >
            {step.isCompleted ? "✓" : step.index + 1}
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="font-semibold text-ink">{agents[step.agent]?.label ?? formatLabel(step.agent)}</h3>
              {step.isActive && <span className="text-xs font-medium text-bankred">Working now</span>}
            </div>
            <p className="mt-1 text-sm leading-6 text-slate-600">{agents[step.agent]?.why}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

function StreamEventDisplay({ events, phase }: { events: AnalysisStreamEvent[]; phase: RunPhase }) {
  const latestEvent = events[events.length - 1] ?? { event: "run_started" };
  if (phase === "running") {
    return (
      <div className="mt-5">
        <StreamEventRow event={latestEvent} index={Math.max(events.length - 1, 0)} />
      </div>
    );
  }

  return (
    <details className="mt-5 rounded-md border border-slate-200 bg-slate-50">
      <summary className="cursor-pointer px-4 py-3">
        <span className="inline-flex w-full flex-wrap items-center justify-between gap-3 align-middle">
          <span>
            <span className="block font-semibold text-ink">Execution record</span>
            <span className="mt-1 block text-sm text-slate-600">{eventTitle(latestEvent)}</span>
          </span>
          <span className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
              {events.length} stages recorded
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
              {formatLabel(phase)}
            </span>
          </span>
        </span>
      </summary>
      <div className="border-t border-slate-200 bg-white px-4 py-4">
        <LiveEventRows events={events} className="grid gap-3" />
      </div>
    </details>
  );
}

function LiveEventRows({
  events,
  className = "mt-5 grid gap-3"
}: {
  events: AnalysisStreamEvent[];
  className?: string;
}) {
  return (
    <div className={className}>
      {events.map((event, index) => (
        <StreamEventRow key={`${event.event}-${index}`} event={event} index={index} />
      ))}
    </div>
  );
}

function StreamEventRow({ event, index }: { event: AnalysisStreamEvent; index: number }) {
  return (
    <div
      className={[
        "grid gap-3 rounded-md border p-3 md:grid-cols-[auto_1fr]",
        eventTone(event)
      ].join(" ")}
    >
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-sm font-semibold text-slate-600">
        {index + 1}
      </div>
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-ink">{eventTitle(event)}</h3>
          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
            {formatLabel(event.event)}
          </span>
        </div>
        <p className="mt-1 text-sm leading-6 text-slate-600">{eventBody(event)}</p>
        {event.decision?.evidence_checked && event.decision.evidence_checked.length > 0 && (
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Evidence checked: {event.decision.evidence_checked.join(", ")}
          </p>
        )}
      </div>
    </div>
  );
}

function eventTone(event: AnalysisStreamEvent): string {
  if (event.event === "run_failed") return "border-red-200 bg-red-50";
  if (event.event === "run_completed") {
    if (event.response?.result.governance_status === "guardrail_failed") return "border-red-200 bg-red-50";
    if (event.response?.result.governance_status === "judge_warning") return "border-amber-200 bg-amber-50";
    return "border-green-200 bg-green-50";
  }
  if (event.event === "agent_completed" && event.agent === "guardrail_agent") {
    return guardrailEventFailed(event) ? "border-red-200 bg-red-50" : "border-green-200 bg-green-50";
  }
  if (event.event.endsWith("_completed")) return "border-green-200 bg-green-50";
  if (event.event.includes("started")) return "border-red-200 bg-red-50";
  return "border-slate-200 bg-slate-50";
}

function eventTitle(event: AnalysisStreamEvent): string {
  if (event.event === "planner_decision") {
    return `Planner chose ${formatLabel(String(event.decision?.next_action ?? "next action"))}`;
  }
  if (event.event.endsWith("_started") && event.agent) {
    return `${agents[event.agent]?.label ?? formatLabel(event.agent)} running`;
  }
  if (event.event === "agent_completed" && event.agent === "guardrail_agent") {
    return `Guardrail Review completed: ${guardrailEventFailed(event) ? "Failed" : "Passed"}`;
  }
  if (event.event === "agent_completed" && event.agent) {
    return `${agents[event.agent]?.label ?? formatLabel(event.agent)} completed`;
  }
  if (event.event === "critic_completed") {
    return `Critic ${formatLabel(event.review?.status ?? "review completed")}`;
  }
  if (event.event === "guardrail_remediation_started") {
    return "Guardrail remediation started";
  }
  if (event.event === "guardrail_remediation_completed") {
    return "Guardrail remediation completed";
  }
  if (event.agent) return agents[event.agent]?.label ?? formatLabel(event.agent);
  if (event.event === "run_completed") {
    if (event.response?.result.governance_status === "judge_warning") return "Run completed: Judge warning";
    if (event.response?.result.governance_status === "guardrail_failed") return "Run completed: Guardrail failed";
    return "Run completed";
  }
  if (event.event === "run_started") return "Run started";
  return formatLabel(event.event);
}

function eventBody(event: AnalysisStreamEvent): string {
  if (event.event === "planner_decision") {
    const missing = event.decision?.missing_evidence?.length
      ? ` Missing evidence: ${event.decision.missing_evidence.join(", ")}.`
      : "";
    return `${event.decision?.reason ?? "Planner decision received."}${missing}`;
  }
  if (event.event === "agent_completed" && event.agent === "guardrail_agent") {
    const flags = guardrailFlags(event);
    return flags.length > 0 ? `Guardrail flags: ${flags.join(", ")}.` : "No blocking guardrail flags found.";
  }
  if (event.event === "agent_completed" && event.output) {
    const findings = event.output.findings?.slice(0, 2).join(" ");
    return truncate([event.output.summary, findings].filter(Boolean).join(" "), 260);
  }
  if (event.event === "critic_completed") {
    const issues = event.review?.issues?.slice(0, 2).join(" ");
    const instruction = event.review?.refinement_instruction ? ` ${event.review.refinement_instruction}` : "";
    return truncate([issues || "No material issue found.", instruction].join(" "), 260);
  }
  if (event.event === "refinement_started") {
    return event.instruction || "Evidence assembly is refining the draft from critic feedback.";
  }
  if (event.event === "refinement_completed") {
    return "Refined report draft is ready for final Judge Panel and Guardrail review.";
  }
  if (event.event === "guardrail_remediation_started") {
    const flags = event.flags?.length ? ` Flags: ${event.flags.join(", ")}.` : "";
    return truncate(`${event.instruction || "Governance remediation started from final guardrail feedback."}${flags}`, 260);
  }
  if (event.event === "guardrail_remediation_completed") {
    return `Remediation pass ${event.guardrail_remediation_rounds ?? 1} completed; Judge Panel and Guardrail will rerun.`;
  }
  if (event.event === "run_completed") {
    if (event.response?.result.governance_status === "judge_warning") {
      return "Final report returned with a Judge warning; Guardrail passed.";
    }
    if (event.response?.result.governance_status === "guardrail_failed") {
      return "Final report was blocked or rewritten by output guardrails.";
    }
    return "Final governed report returned.";
  }
  if (event.event === "run_failed") {
    return event.message || "Run failed while streaming.";
  }
  if (event.agent) {
    return agents[event.agent]?.why ?? "Agent checkpoint received.";
  }
  return "Workflow checkpoint received.";
}

function guardrailEventFailed(event: AnalysisStreamEvent): boolean {
  return guardrailFlags(event).length > 0;
}

function guardrailFlags(event: AnalysisStreamEvent): string[] {
  const structuredFlags = event.output?.structured_output?.flags;
  if (Array.isArray(structuredFlags) && structuredFlags.every((flag) => typeof flag === "string")) {
    return structuredFlags;
  }
  const evidenceFlags = event.output?.evidence?.flatMap((item) => {
    const flags = item.flags;
    return Array.isArray(flags) && flags.every((flag) => typeof flag === "string") ? flags : [];
  });
  if (evidenceFlags && evidenceFlags.length > 0) return evidenceFlags;
  return (event.output?.findings ?? []).filter((finding) => finding !== "No blocking guardrail flags found.");
}

function truncate(value: string, maxLength: number): string {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1).trim()}...` : value;
}
