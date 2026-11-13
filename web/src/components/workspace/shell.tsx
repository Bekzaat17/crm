"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Building2,
  ChevronDown,
  Globe2,
  LogOut,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { Brand } from "@/components/brand";
import { useCompany } from "./company-context";
import { activeNav, NAVIGATION } from "./navigation";

function Sidebar() {
  const { base, session, organization, can, companyId } = useCompany();
  const pathname = usePathname();
  const router = useRouter();
  const current = activeNav(pathname, base);
  const name = session.user?.name || "";
  async function signOut() {
    await api("auth/logout", {}).catch(() => undefined);
    router.replace("/login");
  }
  return (
    <aside className="sidebar">
      <Brand light />
      <div className="company-switch">
        <span className="company-icon">
          <Building2 size={20} />
        </span>
        <div>
          <span className="small">Компания</span>
          <label className="sr-only" htmlFor="company-select">
            Выбрать компанию
          </label>
          <select
            id="company-select"
            value={companyId}
            onChange={(e) => router.push(`/c/${e.target.value}`)}
          >
            {session.organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </div>
        <ChevronDown size={15} />
      </div>
      <span className="nav-label">РАБОЧЕЕ ПРОСТРАНСТВО</span>
      <nav aria-label="Основная навигация">
        {NAVIGATION.filter((item) => !item.perm || can(item.perm)).map(
          (item) => (
            <Link
              key={item.path}
              href={`${base}${item.path}`}
              className={`nav-item ${current === item ? "active" : ""}`}
              aria-current={current === item ? "page" : undefined}
            >
              <item.icon size={19} /> {item.label}
              {item.path === "/team" && (
                <span className="nav-count">{organization.member_count}</span>
              )}
            </Link>
          ),
        )}
        {session.user?.is_platform_admin && (
          <Link href="/platform" className="nav-item">
            <Globe2 size={19} /> Компании платформы
          </Link>
        )}
      </nav>
      <div className="sidebar-bottom">
        <div className="workspace-safety">
          <ShieldCheck size={19} />
          <span>
            Данные доступны только
            <br />
            вашей компании
          </span>
        </div>
        <div className="user-block">
          <span className="avatar">{name.slice(0, 1).toUpperCase()}</span>
          <div>
            <strong>{name}</strong>
            <span>{organization.role_label}</span>
          </div>
          <button
            title="Выйти из аккаунта"
            aria-label="Выйти из аккаунта"
            className="icon-button"
            onClick={signOut}
          >
            <LogOut size={17} />
          </button>
        </div>
      </div>
    </aside>
  );
}

export function WorkspaceShell({ children }: { children: React.ReactNode }) {
  const { base } = useCompany();
  const current = activeNav(usePathname(), base);
  return (
    <>
      <Sidebar />
      <section className="workspace-main">
        <header className="topbar">
          <div>
            <span className="muted">Рабочее пространство</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{current?.label || "Раздел"}</strong>
          </div>
        </header>
        <div className="workspace-content">
          {children}
          <footer className="workspace-footer">
            <span>RehubPro CRM</span>
            <span>С заботой о людях и вашей команде</span>
          </footer>
        </div>
      </section>
    </>
  );
}

/** Заголовок раздела по конфигурации навигации. */
export function useSection() {
  const { base, organization } = useCompany();
  const item = activeNav(usePathname(), base);
  return { item, eyebrow: organization.name };
}
