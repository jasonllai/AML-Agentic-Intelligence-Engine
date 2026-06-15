"use client";

import { useEffect, useMemo, useState } from "react";
import { agents } from "@/lib/catalog";
import { formatLabel } from "@/lib/utils";
import type { AgentName } from "@/types/api";

type RunPhase = "idle" | "running" | "completed" | "failed";

export function AgentProgressTimeline({
  route,
  executedAgents = [],
  phase
}: {
  route: AgentName[];
  executedAgents?: AgentName[];
  phase: RunPhase;
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
            {phase === "running"
              ? "Estimated live progress while the backend completes the non-streaming analysis request."
              : "Actual completed agents appear after the backend returns."}
          </p>
        </div>
        <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-medium text-slate-600">
          {formatLabel(phase)}
        </span>
      </div>
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
    </section>
  );
}
