import { notFound } from "next/navigation";
import { RoleWorkspace } from "@/components/role-workspace";
import { Shell } from "@/components/shell";
import { roles } from "@/lib/catalog";
import type { SupportedRole } from "@/types/api";

const supportedRoles = Object.keys(roles) as SupportedRole[];

export default function RoleWorkspacePage({ params }: { params: { role: string } }) {
  if (!supportedRoles.includes(params.role as SupportedRole)) {
    notFound();
  }

  return (
    <Shell>
      <RoleWorkspace role={params.role as SupportedRole} />
    </Shell>
  );
}
