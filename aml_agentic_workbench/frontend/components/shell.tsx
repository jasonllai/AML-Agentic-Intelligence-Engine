import Link from "next/link";
import { ReactNode } from "react";
import { primaryRoles, roles } from "@/lib/catalog";

const primaryNav = [
  { href: "/", label: "Home", icon: "⌂" },
  { href: "/roles", label: "Role catalog", icon: "▦" },
  { href: "/customer-data", label: "View Customer Data", icon: "◎" },
  { href: "/evaluations", label: "Evaluations", icon: "✓" },
  { href: "/history", label: "Run history", icon: "◷" }
];

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-[#eef3f8] text-ink">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 border-r border-slate-200 bg-[#101827] text-white lg:block">
        <div className="flex h-full flex-col">
          <div className="border-b border-white/10 px-6 py-6">
            <Link href="/" className="block">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-red-200">AML Workbench</div>
              <div className="mt-2 text-xl font-semibold leading-tight">Agentic Intelligence</div>
            </Link>
          </div>

          <nav className="flex-1 overflow-y-auto px-4 py-5">
            <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">Workspace</div>
            <div className="mt-3 grid gap-1">
              {primaryNav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-slate-200 hover:bg-white/10 hover:text-white"
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded-md bg-white/10 text-xs">{item.icon}</span>
                  {item.label}
                </Link>
              ))}
            </div>

            <div className="mt-8 text-xs font-semibold uppercase tracking-wide text-slate-400">Role workspaces</div>
            <div className="mt-3 grid gap-1">
              {primaryRoles.map((role) => {
                const detail = roles[role];
                return (
                <Link
                  key={role}
                  href={`/roles/${role}`}
                  className="rounded-md px-3 py-2 text-sm text-slate-300 hover:bg-white/10 hover:text-white"
                >
                  <span className="block font-semibold">{detail.label}</span>
                  <span className="mt-0.5 block text-xs leading-5 text-slate-400">{detail.tasks[0]}</span>
                </Link>
                );
              })}
            </div>
          </nav>

          <div className="border-t border-white/10 p-4">
            <div className="rounded-md bg-white/10 p-3">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-300">Runtime</div>
              <div className="mt-2 grid gap-2 text-xs text-slate-300">
                <StatusDot label="pgvector ready" />
                <StatusDot label="model scoring local" />
                <StatusDot label="guardrails active" />
              </div>
            </div>
          </div>
        </div>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
          <div className="flex items-center justify-between gap-4 px-5 py-3 lg:px-8">
            <Link href="/" className="font-semibold text-ink lg:hidden">AML Workbench</Link>
            <div className="hidden text-sm text-slate-600 lg:block">Governed AML multi-agent operations</div>
            <div className="flex items-center gap-3">
              <span className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
                Local environment
              </span>
              <span className="rounded-full bg-bankred px-3 py-1 text-xs font-semibold text-white">Internal use</span>
            </div>
          </div>
          <nav className="flex gap-2 overflow-x-auto border-t border-slate-100 px-5 py-2 text-sm lg:hidden">
            {primaryNav.map((item) => (
              <Link key={item.href} href={item.href} className="whitespace-nowrap rounded-md bg-slate-100 px-3 py-1.5">
                {item.label}
              </Link>
            ))}
          </nav>
        </header>

        <main className="px-5 py-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  );
}

function StatusDot({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 rounded-full bg-emerald-400" />
      <span>{label}</span>
    </div>
  );
}
