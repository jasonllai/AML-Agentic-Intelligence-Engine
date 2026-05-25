import Link from "next/link";
import { ReactNode } from "react";

export function Shell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-surface">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link href="/" className="font-semibold tracking-tight text-ink">
            AML Agentic Intelligence Workbench
          </Link>
          <nav className="flex items-center gap-4 text-sm text-slate-600">
            <Link href="/roles" className="hover:text-ink">Roles</Link>
            <Link href="/analysis" className="hover:text-ink">Analysis</Link>
            <Link href="/history" className="hover:text-ink">Run History</Link>
            <span className="rounded-full border border-slate-200 px-3 py-1 text-xs">SSO placeholder</span>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">{children}</main>
    </div>
  );
}
