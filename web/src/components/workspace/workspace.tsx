"use client";
import { CompanyProvider } from "./company-context";
import { WorkspaceShell } from "./shell";

export function Workspace({
  companyId,
  children,
}: {
  companyId: string;
  children: React.ReactNode;
}) {
  return (
    <main className="workspace">
      <CompanyProvider key={companyId} companyId={companyId}>
        <WorkspaceShell>{children}</WorkspaceShell>
      </CompanyProvider>
    </main>
  );
}
