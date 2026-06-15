import Link from "next/link";
import { Shell } from "@/components/shell";
import { Badge, Card } from "@/components/ui";
import { agents, primaryRoles, roles } from "@/lib/catalog";
import { formatLabel } from "@/lib/utils";

const metrics = [
  ["Primary roles", "2", "data science and investigation"],
  ["Golden cases", "role-grounded", "candidate and feedback coverage"],
  ["RAG store", "pgvector", "official AML sources"],
  ["Model backend", "Isolation Forest", "local scoring service"]
];

export default function HomePage() {
  return (
    <Shell>
      <div className="grid gap-6">
        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-soft">
          <div className="grid gap-0 xl:grid-cols-[1fr_420px]">
            <div className="p-6 lg:p-8">
              <Badge tone="danger">AML Agentic Intelligence Workbench</Badge>
              <h1 className="mt-5 max-w-4xl text-4xl font-semibold tracking-tight text-ink lg:text-5xl">
                Governed AML analysis command center
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-7 text-slate-600">
                Run model-driven candidate generation, hand off ranked packages to investigation, and review
                governed outputs with evidence, guardrails, model context, and evaluation scores.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link
                  href="/roles/data_scientist"
                  className="rounded-md bg-bankred px-4 py-2 text-sm font-semibold text-white hover:bg-red-800"
                >
                  Start data science workflow
                </Link>
                <Link
                  href="/evaluations"
                  className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:border-slate-400"
                >
                  Open evaluation dashboard
                </Link>
              </div>
            </div>

            <div className="border-t border-slate-200 bg-[#111827] p-6 text-white xl:border-l xl:border-t-0">
              <div className="text-sm font-semibold uppercase tracking-wide text-slate-300">System flow</div>
              <div className="mt-5 grid gap-3">
                {["Population Scoring", "Candidate Handoff", "Case Review", "Feedback Capture", "Guardrail Review"].map(
                  (step, index) => (
                    <div key={step} className="flex items-center gap-3 rounded-md bg-white/10 p-3">
                      <span className="flex h-8 w-8 items-center justify-center rounded-md bg-bankred text-sm font-semibold">
                        {index + 1}
                      </span>
                      <span className="text-sm font-medium">{step}</span>
                    </div>
                  )
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map(([label, value, detail]) => (
            <Card key={label} className="p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
              <div className="mt-2 text-2xl font-semibold text-ink">{value}</div>
              <div className="mt-1 text-sm text-slate-600">{detail}</div>
            </Card>
          ))}
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
          <Card>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold text-ink">Choose your role</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">
                  Each primary role has one realistic function matching AML bank operating responsibilities.
                </p>
              </div>
              <Link href="/roles" className="text-sm font-semibold text-bankred hover:underline">View role catalog</Link>
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-2">
              {primaryRoles.map((role) => {
                const detail = roles[role];
                return (
                <Link
                  key={role}
                  href={`/roles/${role}`}
                  className="group rounded-md border border-slate-200 bg-slate-50 p-4 transition hover:border-red-200 hover:bg-red-50"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-lg font-semibold text-ink">{detail.label}</div>
                      <div className="mt-2 text-sm leading-6 text-slate-600">{detail.focus}</div>
                    </div>
                    <span className="text-bankred">→</span>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {detail.actions.map((task) => (
                      <Badge key={task}>{formatLabel(task)}</Badge>
                    ))}
                  </div>
                </Link>
                );
              })}
            </div>
          </Card>

          <Card>
            <h2 className="text-2xl font-semibold text-ink">Agent operating model</h2>
            <div className="mt-5 grid gap-3">
              {Object.entries(agents).map(([agent, detail]) => (
                <div key={agent} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-semibold text-ink">{detail.label}</h3>
                    <span className="text-xs text-slate-500">{detail.sections.length} sections</span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-slate-600">{detail.why}</p>
                </div>
              ))}
            </div>
          </Card>
        </section>
      </div>
    </Shell>
  );
}
