import Link from "next/link";
import { Shell } from "@/components/shell";
import { Badge, Card } from "@/components/ui";
import { roles } from "@/lib/catalog";
import { formatLabel } from "@/lib/utils";

export default function HomePage() {
  return (
    <Shell>
      <section className="grid gap-8">
        <div className="grid gap-6 lg:grid-cols-[1fr_0.8fr]">
          <div>
            <div className="mb-4 inline-flex rounded-full border border-red-100 bg-white px-3 py-1 text-sm text-bankred">
              Governed internal AML analytics
            </div>
            <h1 className="max-w-4xl text-4xl font-semibold tracking-tight text-ink md:text-5xl">
              Select your AML workflow role
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-7 text-slate-600">
              Start from the role you are performing today. Each workspace exposes the actions, agent route,
              evidence views, and output style that fit that role.
            </p>
          </div>
          <Card className="self-start">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">System readiness</h2>
            <div className="mt-4 grid gap-3">
              <Readiness label="PostgreSQL pgvector" value="Required for typology retrieval" />
              <Readiness label="Model artifacts" value="Isolation Forest scoring service" />
              <Readiness label="Guardrails" value="Input, output, citation, and model-proof checks" />
            </div>
          </Card>
        </div>

        <div className="grid gap-4 md:grid-cols-2">
          {Object.entries(roles).map(([role, detail]) => (
            <Link key={role} href={`/roles/${role}`} className="group block">
              <Card className="h-full transition group-hover:-translate-y-0.5 group-hover:border-red-200 group-hover:shadow-lg">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <Badge>{formatLabel(role)}</Badge>
                    <h2 className="mt-4 text-2xl font-semibold text-ink">{detail.label}</h2>
                  </div>
                  <span className="rounded-md border border-slate-200 px-2 py-1 text-slate-500 group-hover:border-red-200 group-hover:text-bankred">
                    -&gt;
                  </span>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-600">{detail.focus}</p>
                <div className="mt-5 flex flex-wrap gap-2">
                  {detail.actions.map((task) => (
                    <Badge key={task} tone="neutral">{formatLabel(task)}</Badge>
                  ))}
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </section>
    </Shell>
  );
}

function Readiness({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start gap-3 rounded-md border border-slate-200 bg-slate-50 p-3">
      <div className="mt-1 h-2.5 w-2.5 rounded-full bg-green-500" />
      <div>
        <div className="text-sm font-semibold text-ink">{label}</div>
        <div className="mt-1 text-xs text-slate-600">{value}</div>
      </div>
    </div>
  );
}
