"use client";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
} from "react";
import { useRouter } from "next/navigation";
import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import type { Session } from "@/lib/api";
import type { Organization, Perm } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { rememberCompany } from "@/lib/storage";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";

type CompanyContextValue = {
  companyId: string;
  /** Префикс API компании: organizations/{id}. */
  root: string;
  /** Префикс страниц компании: /c/{id}. */
  base: string;
  session: Session;
  organization: Organization;
  can: (perm: Perm) => boolean;
  reload: () => void;
};

const CompanyContext = createContext<CompanyContextValue | null>(null);

export function useCompany() {
  const value = useContext(CompanyContext);
  if (!value) throw new Error("useCompany вне CompanyProvider");
  return value;
}

/** Загружает сессию и компанию; права используются только для отображения. */
export function CompanyProvider({
  companyId,
  children,
}: {
  companyId: string;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const session = useResource<Session>("auth/session");
  const organization = useResource<Organization>(
    session.data?.user ? `organizations/${companyId}` : null,
  );
  useEffect(() => {
    if (session.data && !session.data.user) router.replace("/login");
    if (organization.status === 401) router.replace("/login");
  }, [session.data, organization.status, router]);
  useEffect(() => {
    if (organization.data) rememberCompany(companyId);
  }, [organization.data, companyId]);
  const { reload: reloadSession } = session;
  const { reload: reloadOrganization } = organization;
  const reload = useCallback(() => {
    reloadSession();
    reloadOrganization();
  }, [reloadSession, reloadOrganization]);
  const value = useMemo(() => {
    if (!session.data?.user || !organization.data) return null;
    const permissions = new Set(organization.data.permissions);
    return {
      companyId,
      root: `organizations/${companyId}`,
      base: `/c/${companyId}`,
      session: session.data,
      organization: organization.data,
      can: (perm: Perm) => permissions.has(perm),
      reload,
    };
  }, [companyId, session.data, organization.data, reload]);

  if (session.error)
    return <ErrorAlert message={session.error} onRetry={session.reload} />;
  if (organization.status === 404)
    return (
      <div className="empty-state">
        <LockKeyhole size={32} />
        <h2>Компания недоступна</h2>
        <p>Компания не найдена или ваш доступ к ней закрыт.</p>
        <Link className="button secondary" href="/">
          Открыть доступную компанию
        </Link>
      </div>
    );
  if (organization.error && !organization.data)
    return (
      <ErrorAlert message={organization.error} onRetry={organization.reload} />
    );
  if (!value) return <LoadingState text="Загружаем пространство компании…" />;
  return (
    <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>
  );
}
