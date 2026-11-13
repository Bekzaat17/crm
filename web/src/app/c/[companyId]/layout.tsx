import { Workspace } from "@/components/workspace/workspace";

export default async function CompanyLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  return <Workspace companyId={companyId}>{children}</Workspace>;
}
