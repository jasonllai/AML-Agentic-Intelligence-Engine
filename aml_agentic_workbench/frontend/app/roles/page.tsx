import Link from "next/link";
import { Shell } from "@/components/shell";
import { Badge, Button, Card } from "@/components/ui";
import { roles } from "@/lib/catalog";

export default function RolesPage() {
  return (
    <Shell>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-ink">Role Selection</h1>
          <p className="mt-2 text-slate-600">Choose a workflow lens before routing agents and report sections.</p>
        </div>
        <Link href="/analysis"><Button>Start Analysis</Button></Link>
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        {Object.entries(roles).map(([role, detail]) => (
          <Card key={role}>
            <div className="flex items-start justify-between">
              <h2 className="text-xl font-semibold text-ink">{detail.label}</h2>
              <Badge>{role}</Badge>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">{detail.focus}</p>
            <h3 className="mt-5 text-sm font-semibold text-slate-700">Typical tasks</h3>
            <div className="mt-2 flex flex-wrap gap-2">
              {detail.tasks.map((task) => <Badge key={task}>{task}</Badge>)}
            </div>
            <h3 className="mt-5 text-sm font-semibold text-slate-700">Report style</h3>
            <p className="mt-2 text-sm text-slate-600">{detail.reportStyle}</p>
          </Card>
        ))}
      </div>
    </Shell>
  );
}
