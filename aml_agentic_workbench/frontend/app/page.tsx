import Link from "next/link";
import { Shell } from "@/components/shell";
import { Button, Card } from "@/components/ui";

export default function HomePage() {
  return (
    <Shell>
      <section className="grid min-h-[70vh] items-center gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <div>
          <div className="mb-4 inline-flex rounded-full border border-red-100 bg-white px-3 py-1 text-sm text-bankred">
            Governed internal AML analytics
          </div>
          <h1 className="max-w-4xl text-5xl font-semibold tracking-tight text-ink">
            AML Agentic Intelligence Workbench
          </h1>
          <p className="mt-5 max-w-3xl text-lg leading-8 text-slate-600">
            Role-aware multi-agent intelligence platform for AML behaviour explanation, model interpretation,
            typology mapping, and feature critique.
          </p>
          <div className="mt-8 flex gap-3">
            <Link href="/analysis"><Button>Start Analysis</Button></Link>
            <Link href="/roles" className="rounded-md border border-slate-300 px-4 py-2 text-sm font-semibold text-ink">
              Review Roles
            </Link>
          </div>
        </div>
        <Card>
          <h2 className="text-lg font-semibold text-ink">Workbench Controls</h2>
          <div className="mt-5 grid gap-4">
            {[
              "Dynamic route preview before execution",
              "LLM-as-judge scores with compliance override",
              "Guardrail status and audit trace",
              "Evidence tables instead of chatbot transcripts"
            ].map((item) => (
              <div key={item} className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                {item}
              </div>
            ))}
          </div>
        </Card>
      </section>
    </Shell>
  );
}
