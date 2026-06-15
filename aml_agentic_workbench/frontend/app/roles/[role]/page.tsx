import { notFound } from "next/navigation";
import { RoleWorkspace } from "@/components/role-workspace";
import { Shell } from "@/components/shell";
import { roles } from "@/lib/catalog";
import type { SupportedRole } from "@/types/api";

const supportedRoles = Object.keys(roles) as SupportedRole[];

export default function RoleWorkspacePage({
  params,
  searchParams
}: {
  params: { role: string };
  searchParams: { customerId?: string; modelFamily?: string };
}) {
  if (!supportedRoles.includes(params.role as SupportedRole)) {
    notFound();
  }

  return (
    <Shell>
      <RoleWorkspace
        role={params.role as SupportedRole}
        initialCustomerId={searchParams.customerId}
        initialModelFamily={searchParams.modelFamily}
      />
    </Shell>
  );
}
