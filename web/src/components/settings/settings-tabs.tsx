"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Perm } from "@/lib/types";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";

const TABS: { path: string; label: string; perm?: Perm }[] = [
  { path: "", label: "Компания и филиалы" },
  { path: "/pipeline", label: "Этапы воронки", perm: "manage_pipeline" },
  { path: "/centers", label: "Центры RehubPro", perm: "manage_centers" },
  { path: "/notifications", label: "Уведомления" },
  { path: "/extension", label: "Расширение браузера" },
];

export function SettingsTabs({ children }: { children: React.ReactNode }) {
  const { base, can, organization } = useCompany();
  const pathname = usePathname();
  const settings = `${base}/settings`;
  return (
    <>
      <PageHeading
        eyebrow={organization.name}
        title="Настройки"
        description="Компания, филиалы, воронка, центры и уведомления."
      />
      <nav className="tabs" aria-label="Разделы настроек">
        {TABS.filter((t) => !t.perm || can(t.perm)).map((tab) => {
          const href = `${settings}${tab.path}`;
          const active = pathname === href;
          return (
            <Link
              key={tab.path}
              href={href}
              className={`tab ${active ? "active" : ""}`}
              aria-current={active ? "page" : undefined}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>
      {children}
    </>
  );
}

/** Раздел без права доступа: сервер всё равно отклонит запросы. */
export function RequirePerm({
  perm,
  children,
}: {
  perm: Perm;
  children: React.ReactNode;
}) {
  const { can } = useCompany();
  if (!can(perm))
    return (
      <div className="empty-state compact">
        <h3>Недостаточно прав</h3>
        <p>Этот раздел доступен владельцу и администратору компании.</p>
      </div>
    );
  return children;
}
