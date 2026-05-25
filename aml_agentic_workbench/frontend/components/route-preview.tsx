import type { AgentName } from "@/types/api";
import { agents } from "@/lib/catalog";
import { Card, Badge } from "@/components/ui";

export function RoutePreview({ route }: { route: AgentName[] }) {
  const sections = Array.from(new Set(route.flatMap((agent) => agents[agent].sections)));
  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ink">Dynamic Route Preview</h2>
          <p className="mt-1 text-sm text-slate-600">
            Only selected agents run. This reduces latency, cost, and unnecessary exposure of data to agents that are not needed.
          </p>
        </div>
        <Badge>{route.length} agents</Badge>
      </div>
      <div className="mt-5 grid gap-3">
        {route.map((agent, index) => (
          <div key={agent} className="grid gap-3 rounded-md border border-slate-200 p-3 md:grid-cols-[36px_1fr]">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-ink">
              {index + 1}
            </div>
            <div>
              <div className="font-medium text-ink">{agents[agent].label}</div>
              <p className="mt-1 text-sm text-slate-600">{agents[agent].why}</p>
            </div>
          </div>
        ))}
      </div>
      <div className="mt-5">
        <h3 className="text-sm font-semibold text-slate-700">Estimated report sections</h3>
        <div className="mt-2 flex flex-wrap gap-2">
          {sections.map((section) => <Badge key={section}>{section}</Badge>)}
        </div>
      </div>
    </Card>
  );
}
