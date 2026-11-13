"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  Building2,
  Check,
  ChevronDown,
  Circle,
  LayoutDashboard,
  Link2,
  LogOut,
  Mail,
  Plus,
  ShieldCheck,
  Users,
  X,
  Activity,
  Layers3,
  LockKeyhole,
} from "lucide-react";
import { api, ApiError, Company, errorMessage, Session } from "@/lib/api";
import { Centers } from "@/components/integrations/centers";
import { SalesSummary } from "@/components/sales/summary";
import { WorkTasks } from "@/components/sales/work-tasks";
import { Sales } from "@/components/sales";
import { Brand } from "@/components/brand";

type Organization = Company & {
  can_manage_team: boolean;
  member_count: number;
  branches: { id: string; name: string }[];
  created_at: string;
};
type Member = {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: string;
  role_label: string;
  is_active: boolean;
};
type Invitation = {
  id: string;
  email: string;
  role_label: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
};
type Team = { members: Member[]; invitations: Invitation[] };
type Event = { id: string; action: string; actor: string; created_at: string };
type Panel =
  "overview" | "team" | "activity" | "tasks" | "settings" | "clients" | "leads";
const statusLabels = {
  pending: "Ожидает ответа",
  accepted: "Принято",
  revoked: "Отозвано",
  expired: "Истекло",
};
const formatDate = (value: string) =>
  new Intl.DateTimeFormat("ru", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Almaty",
  }).format(new Date(value));

export default function Dashboard() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [companyId, setCompanyId] = useState("");
  const [clientToOpen, setClientToOpen] = useState<string | undefined>();
  const [organization, setOrganization] = useState<Organization | null>(null);
  const [team, setTeam] = useState<Team | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [panel, setPanel] = useState<Panel>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [inviteOpen, setInviteOpen] = useState(false);
  const [confirmMember, setConfirmMember] = useState<Member | null>(null);
  const [confirmInvite, setConfirmInvite] = useState<Invitation | null>(null);
  const [busy, setBusy] = useState(false);
  const [modalError, setModalError] = useState("");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api<Session>("auth/session")
      .then((current) => {
        if (cancelled) return;
        if (!current.user) {
          router.replace("/login");
          return;
        }
        setSession(current);
        const previous = sessionStorage.getItem("crm-company");
        setCompanyId(
          current.organizations.find((o) => o.id === previous)?.id ||
            current.organizations[0]?.id ||
            "",
        );
        if (!current.organizations.length) setLoading(false);
      })
      .catch((e) => {
        if (!cancelled) {
          setError(errorMessage(e));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setOrganization(null);
    setTeam(null);
    setEvents([]);
    sessionStorage.setItem("crm-company", companyId);
    async function load() {
      try {
        const org = await api<Organization>(`organizations/${companyId}`);
        const [members, audit] = org.can_manage_team
          ? await Promise.all([
              api<Team>(`organizations/${companyId}/team`),
              api<{ events: Event[] }>(`organizations/${companyId}/audit`),
            ])
          : [null, { events: [] }];
        if (!cancelled) {
          setOrganization(org);
          setTeam(members);
          setEvents(audit.events);
        }
      } catch (e) {
        if (!cancelled) {
          setError(errorMessage(e));
          if (e instanceof ApiError && e.status === 401)
            router.replace("/login");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [companyId, revision, router]);

  useEffect(() => {
    if (!inviteOpen && !confirmMember && !confirmInvite) return;
    const previous = document.activeElement as HTMLElement | null;
    const closeOnEscape = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !busy) {
        setInviteOpen(false);
        setConfirmMember(null);
        setConfirmInvite(null);
      }
      if (e.key === "Tab") {
        const controls = Array.from(
          document.querySelectorAll<HTMLElement>(
            '[role="dialog"] button:not(:disabled), [role="dialog"] input, [role="dialog"] select',
          ),
        );
        const first = controls[0],
          last = controls[controls.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
        if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", closeOnEscape);
    document
      .querySelector<HTMLElement>(
        '[role="dialog"] input, [role="dialog"] button',
      )
      ?.focus();
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      previous?.focus();
    };
  }, [inviteOpen, confirmMember, confirmInvite, busy]);

  async function invite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setModalError("");
    const data = Object.fromEntries(
      new FormData(event.currentTarget).entries(),
    );
    try {
      const response = await api<{ message: string }>(
        `organizations/${companyId}/invitations`,
        data,
      );
      setNotice(response.message);
      setInviteOpen(false);
      setRevision((v) => v + 1);
    } catch (e) {
      setModalError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirmAction() {
    setBusy(true);
    setModalError("");
    try {
      const path = confirmMember
        ? `members/${confirmMember.id}/deactivate`
        : `invitations/${confirmInvite!.id}/revoke`;
      const response = await api<{ message: string }>(
        `organizations/${companyId}/${path}`,
        {},
      );
      setConfirmMember(null);
      setConfirmInvite(null);
      setNotice(response.message);
      setRevision((v) => v + 1);
    } catch (e) {
      setModalError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function switchCompany(value: string) {
    setOrganization(null);
    setTeam(null);
    setEvents([]);
    setLoading(true);
    setPanel("overview");
    setNotice("");
    setCompanyId(value);
  }

  async function signOut() {
    try {
      await api("auth/logout", {});
      router.replace("/login");
    } catch (e) {
      setError(errorMessage(e));
    }
  }

  const name = session?.user?.name || "";
  const titles = {
    overview: "Обзор пространства",
    team: "Команда",
    activity: "История действий",
    clients: "Клиенты",
    leads: "Воронка обращений",
    tasks: "Задачи и напоминания",
    settings: "Настройки компании",
  };
  const descriptions: Record<Panel, string> = {
    overview: "Здесь начинается совместная работа вашей команды.",
    team: "Сотрудники, приглашения и доступ к компании.",
    activity: "Изменения в компании и управление доступом.",
    clients: "Карточки клиентов и связанные контактные лица.",
    leads: "Обращения, этапы и следующие действия.",
    tasks: "Задачи менеджеров, сроки и следующие контакты.",
    settings: "Центры RehubPro и подключения вашей компании.",
  };
  const pending =
    team?.invitations.filter((i) => i.status === "pending").length || 0;
  const openInvite = () => {
    setModalError("");
    setInviteOpen(true);
  };

  return (
    <main className="workspace">
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
              onChange={(e) => switchCompany(e.target.value)}
            >
              {session?.organizations.map((o) => (
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
          {organization?.can_manage_team && (
            <button
              className={`nav-item ${panel === "settings" ? "active" : ""}`}
              onClick={() => setPanel("settings")}
            >
              <Building2 size={19} /> Настройки
            </button>
          )}
          <button
            className={`nav-item ${panel === "tasks" ? "active" : ""}`}
            onClick={() => setPanel("tasks")}
          >
            <Check size={19} /> Задачи
          </button>
          <button
            className={`nav-item ${panel === "clients" ? "active" : ""}`}
            onClick={() => {
              setClientToOpen(undefined);
              setPanel("clients");
            }}
          >
            <Users size={19} /> Клиенты
          </button>
          <button
            className={`nav-item ${panel === "leads" ? "active" : ""}`}
            onClick={() => setPanel("leads")}
          >
            <Layers3 size={19} /> Воронка
          </button>
          <button
            className={`nav-item ${panel === "overview" ? "active" : ""}`}
            onClick={() => setPanel("overview")}
          >
            <LayoutDashboard size={19} /> Обзор
          </button>
          {organization?.can_manage_team && (
            <button
              className={`nav-item ${panel === "team" ? "active" : ""}`}
              onClick={() => setPanel("team")}
            >
              <Users size={19} /> Команда{" "}
              <span className="nav-count">{organization.member_count}</span>
            </button>
          )}
          {organization?.can_manage_team && (
            <button
              className={`nav-item ${panel === "activity" ? "active" : ""}`}
              onClick={() => setPanel("activity")}
            >
              <Activity size={19} /> История действий
            </button>
          )}
        </nav>
        <div className="nav-upcoming">
          <span className="nav-label">СЛЕДУЮЩИЙ ЭТАП</span>
          <div>
            <Link2 size={18} /> Связь с RehubPro <span>Скоро</span>
          </div>
        </div>
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
              <span>{organization?.role_label || "Личный аккаунт"}</span>
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
      <section className="workspace-main">
        <header className="topbar">
          <div>
            <span className="muted">Рабочее пространство</span>
            <span className="breadcrumb-separator">/</span>
            <strong>{titles[panel]}</strong>
          </div>
          <div className="topbar-actions">
            <span className="environment-badge">
              <span /> Начальная версия
            </span>
            <button
              className="icon-button mobile-logout"
              aria-label="Выйти из аккаунта"
              onClick={signOut}
            >
              <LogOut size={17} />
            </button>
          </div>
        </header>
        <div className="workspace-content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {organization?.name || "REHUBPRO CRM"}
              </span>
              <h1>
                {panel === "overview"
                  ? `Здравствуйте${name ? `, ${name.split(" ")[0]}` : ""}`
                  : titles[panel]}
                <span className="heading-dot">.</span>
              </h1>
              <p className="muted">{descriptions[panel]}</p>
            </div>
            {organization?.can_manage_team &&
              (panel === "overview" || panel === "team") && (
                <button className="button primary" onClick={openInvite}>
                  <Plus size={17} /> Пригласить сотрудника
                </button>
              )}
          </div>
          {error && (
            <div className="alert error" role="alert">
              {error}
              <button
                className="text-button"
                onClick={() => window.location.reload()}
              >
                Повторить
              </button>
            </div>
          )}
          {notice && (
            <div className="alert success" role="status">
              <Check size={17} />
              {notice}
              <button
                className="icon-button"
                aria-label="Закрыть уведомление"
                onClick={() => setNotice("")}
              >
                <X size={16} />
              </button>
            </div>
          )}
          {loading ? (
            <div className="loading-state" role="status">
              Загружаем пространство компании…
            </div>
          ) : !organization ? (
            <div className="empty-state">
              <LockKeyhole size={32} />
              <h2>Пока нет доступа к компании</h2>
              <p>Попросите владельца отправить приглашение на вашу почту.</p>
            </div>
          ) : (
            <>
              {(panel === "clients" || panel === "leads") && (
                <Sales
                  key={`${companyId}-${panel}`}
                  companyId={companyId}
                  view={panel}
                  initialClientId={
                    panel === "clients" ? clientToOpen : undefined
                  }
                />
              )}
              {panel === "settings" && organization?.can_manage_team && (
                <Centers key={companyId} companyId={companyId} />
              )}
              {panel === "tasks" && (
                <WorkTasks
                  key={companyId}
                  companyId={companyId}
                  onOpenClient={(id) => {
                    setClientToOpen(id);
                    setPanel("clients");
                  }}
                />
              )}
              {panel === "overview" && (
                <>
                  <SalesSummary
                    key={companyId}
                    companyId={companyId}
                    onTasks={() => setPanel("tasks")}
                  />
                  <div className="welcome-card">
                    <div className="welcome-copy">
                      <span className="welcome-label">
                        <span /> ПРОСТРАНСТВО СОЗДАНО
                      </span>
                      <h2>
                        Сильная команда —<br />
                        начало больших перемен.
                      </h2>
                      <p>
                        Пригласите коллег и распределите роли.
                        <br />
                        Всё необходимое для начала — в одном месте.
                      </p>
                      {organization.can_manage_team && (
                        <button
                          className="button welcome-button"
                          onClick={() => setPanel("team")}
                        >
                          Открыть команду <ArrowUpRight size={18} />
                        </button>
                      )}
                    </div>
                    <div className="welcome-art" aria-hidden="true">
                      <div className="art-ring ring-one" />
                      <div className="art-ring ring-two" />
                      <div className="art-ring ring-three" />
                      <div className="art-card">
                        <span className="art-avatar">
                          <Users size={30} />
                        </span>
                        <strong>Вместе — больше</strong>
                        <span>Ваша команда. Ваше пространство.</span>
                        <div className="art-people">
                          <i>К</i>
                          <i>М</i>
                          <i>Р</i>
                          <i>
                            <Plus size={13} />
                          </i>
                        </div>
                      </div>
                      <span className="floating-check">
                        <Check size={20} />
                      </span>
                    </div>
                  </div>
                  <div className="stats-grid">
                    <article className="stat-card">
                      <span className="stat-icon">
                        <Users size={20} />
                      </span>
                      <span className="stat-label">Сотрудники</span>
                      <strong>
                        {organization.member_count}
                        <small>в команде</small>
                      </strong>
                      <span className="stat-caption">
                        С активным доступом к компании
                      </span>
                    </article>
                    <article className="stat-card">
                      <span className="stat-icon sand">
                        <Building2 size={20} />
                      </span>
                      <span className="stat-label">Филиалы</span>
                      <strong>
                        {organization.branches.length}
                        <small>
                          {organization.branches.length === 1
                            ? "центр"
                            : "центров"}
                        </small>
                      </strong>
                      <span className="stat-caption">
                        {organization.branches.map((b) => b.name).join(", ")}
                      </span>
                    </article>
                    <article className="stat-card">
                      <span className="stat-icon lavender">
                        <Link2 size={20} />
                      </span>
                      <span className="stat-label">RehubPro</span>
                      <strong className="text-stat">Настроить центры</strong>
                      <span className="stat-caption">
                        Центры настраиваются в настройках компании
                      </span>
                    </article>
                  </div>
                  <div className="overview-grid">
                    <article className="card setup-card">
                      <div className="section-title">
                        <h2>Первые шаги</h2>
                        <span className="subtle-pill">
                          {organization.member_count > 1 ? "2" : "1"} из 3
                        </span>
                      </div>
                      <p className="muted small">
                        Подготовьте пространство к работе.
                      </p>
                      <div className="setup-step">
                        <span className="step-check">
                          <Check size={15} />
                        </span>
                        <div>
                          <strong>Создать компанию</strong>
                          <p>{organization.name} готова к работе</p>
                        </div>
                        <span className="done-label">Готово</span>
                      </div>
                      <div className="setup-step">
                        <span
                          className={
                            organization.member_count > 1
                              ? "step-check"
                              : "step-number"
                          }
                        >
                          {organization.member_count > 1 ? (
                            <Check size={15} />
                          ) : (
                            "2"
                          )}
                        </span>
                        <div>
                          <strong>Собрать команду</strong>
                          <p>
                            {organization.member_count > 1
                              ? "Сотрудники присоединились к компании"
                              : pending
                                ? "Ожидаем принятия приглашений"
                                : "Пригласите коллег и назначьте роли"}
                          </p>
                        </div>
                        {organization.can_manage_team && (
                          <button
                            className="icon-button step-arrow"
                            aria-label="Открыть команду"
                            onClick={() => setPanel("team")}
                          >
                            <ArrowRight size={18} />
                          </button>
                        )}
                      </div>
                      <div className="setup-step muted-step">
                        <span className="step-number">3</span>
                        <div>
                          <strong>Добавить первое обращение</strong>
                          <p>Карточки клиентов и воронка готовы к работе</p>
                        </div>
                        <button
                          className="text-button"
                          onClick={() => {
                            setClientToOpen(undefined);
                            setPanel("clients");
                          }}
                        >
                          Открыть
                        </button>
                      </div>
                    </article>
                    <article className="card">
                      <div className="section-title">
                        <h2>Последние действия</h2>
                        <Activity size={18} className="muted" />
                      </div>
                      {organization.can_manage_team ? (
                        <>
                          <div className="activity-list">
                            {events.slice(0, 3).map((e) => (
                              <div className="activity-item" key={e.id}>
                                <span className="activity-dot" />
                                <div>
                                  <strong>{e.action}</strong>
                                  <p>
                                    {e.actor} · {formatDate(e.created_at)}
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                          <button
                            className="text-button"
                            onClick={() => setPanel("activity")}
                          >
                            Вся история <ArrowRight size={15} />
                          </button>
                        </>
                      ) : (
                        <div className="quiet-note">
                          <ShieldCheck size={26} />
                          <p>
                            Управление доступом и история компании доступны
                            владельцу и администратору.
                          </p>
                        </div>
                      )}
                    </article>
                  </div>
                </>
              )}
              {panel === "team" && team && (
                <>
                  <div className="section-title table-section-title">
                    <h2>
                      Сотрудники{" "}
                      <span className="subtle-pill">
                        {team.members.filter((m) => m.is_active).length}
                      </span>
                    </h2>
                    <span className="small muted">
                      Роли действуют только в этой компании
                    </span>
                  </div>
                  <div className="card table-card">
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Сотрудник</th>
                            <th>Роль</th>
                            <th>Доступ</th>
                            <th>
                              <span className="sr-only">Действия</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {team.members.map((m) => (
                            <tr key={m.id}>
                              <td>
                                <div className="member-cell">
                                  <span className="avatar light-avatar">
                                    {m.name.slice(0, 1)}
                                  </span>
                                  <div>
                                    <strong>
                                      {m.name}
                                      {m.user_id === session?.user?.id && (
                                        <span className="you-label">Вы</span>
                                      )}
                                    </strong>
                                    <span>{m.email}</span>
                                  </div>
                                </div>
                              </td>
                              <td>{m.role_label}</td>
                              <td>
                                <span
                                  className={`status ${m.is_active ? "status-active" : "status-muted"}`}
                                >
                                  <Circle size={7} fill="currentColor" />
                                  {m.is_active ? "Активен" : "Отключён"}
                                </span>
                              </td>
                              <td>
                                {m.is_active &&
                                  m.role !== "owner" &&
                                  m.user_id !== session?.user?.id && (
                                    <button
                                      className="text-button danger-text"
                                      onClick={() => {
                                        setModalError("");
                                        setConfirmMember(m);
                                      }}
                                    >
                                      Отключить
                                    </button>
                                  )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="section-title table-section-title">
                    <h2>
                      Приглашения <span className="subtle-pill">{pending}</span>
                    </h2>
                  </div>
                  <div className="card table-card">
                    {team.invitations.length ? (
                      <div className="table-scroll">
                        <table>
                          <thead>
                            <tr>
                              <th>Электронная почта</th>
                              <th>Роль</th>
                              <th>Статус</th>
                              <th>
                                <span className="sr-only">Действия</span>
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {team.invitations.map((i) => (
                              <tr key={i.id}>
                                <td>
                                  <span className="invite-email">
                                    <Mail size={16} />
                                    {i.email}
                                  </span>
                                </td>
                                <td>{i.role_label}</td>
                                <td>
                                  <span
                                    className={`status ${i.status === "pending" ? "status-pending" : "status-muted"}`}
                                  >
                                    {statusLabels[i.status]}
                                  </span>
                                </td>
                                <td>
                                  {i.status === "pending" && (
                                    <button
                                      className="text-button"
                                      onClick={() => {
                                        setModalError("");
                                        setConfirmInvite(i);
                                      }}
                                    >
                                      Отозвать
                                    </button>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="empty-state compact">
                        <span className="empty-icon">
                          <Mail size={25} />
                        </span>
                        <h3>Начните с приглашения</h3>
                        <p>
                          Сотрудник получит письмо и присоединится к вашей
                          компании.
                        </p>
                        <button
                          className="button secondary"
                          onClick={openInvite}
                        >
                          <Plus size={16} /> Пригласить сотрудника
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
              {panel === "activity" && (
                <article className="card">
                  <div className="section-title">
                    <h2>Управление компанией</h2>
                    <span className="small muted">Время Алматы</span>
                  </div>
                  <div className="activity-list full-activity">
                    {events.map((e) => (
                      <div className="activity-item" key={e.id}>
                        <span className="activity-dot" />
                        <div>
                          <strong>{e.action}</strong>
                          <p>{e.actor}</p>
                        </div>
                        <time>{formatDate(e.created_at)}</time>
                      </div>
                    ))}
                  </div>
                </article>
              )}
              <footer className="workspace-footer">
                <span>RehubPro CRM</span>
                <span>С заботой о людях и вашей команде</span>
              </footer>
            </>
          )}
        </div>
      </section>
      {(inviteOpen || confirmMember || confirmInvite) && (
        <div className="modal-backdrop">
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="modal-title"
          >
            <button
              className="icon-button modal-close"
              disabled={busy}
              aria-label="Закрыть"
              onClick={() => {
                setInviteOpen(false);
                setConfirmMember(null);
                setConfirmInvite(null);
              }}
            >
              <X size={20} />
            </button>
            <span className="modal-icon">
              {inviteOpen ? <Users size={25} /> : <ShieldCheck size={25} />}
            </span>
            <h2 id="modal-title">
              {inviteOpen
                ? "Пригласить сотрудника"
                : confirmMember
                  ? "Отключить доступ?"
                  : "Отозвать приглашение?"}
            </h2>
            <p className="muted">
              {inviteOpen
                ? `Добавьте коллегу в компанию «${organization?.name}».`
                : confirmMember
                  ? `${confirmMember.name} потеряет доступ к этой компании. Аккаунт и работа в других компаниях сохранятся.`
                  : `Ссылка из письма для ${confirmInvite?.email} перестанет действовать.`}
            </p>
            {modalError && (
              <div className="alert error" role="alert">
                {modalError}
              </div>
            )}
            {inviteOpen ? (
              <form className="auth-form" onSubmit={invite}>
                <label>
                  Электронная почта
                  <input
                    autoFocus
                    name="email"
                    type="email"
                    autoComplete="off"
                    required
                    maxLength={254}
                    placeholder="colleague@company.kz"
                  />
                </label>
                <label>
                  Роль в компании
                  <select name="role" defaultValue="manager">
                    <option value="manager">Менеджер</option>
                    <option value="lead">Руководитель</option>
                    <option value="admin">Администратор</option>
                  </select>
                </label>
                <p className="form-note">
                  <Mail size={15} /> Приглашение действует 7 дней.
                </p>
                <button className="button primary full" disabled={busy}>
                  {busy ? "Отправляем…" : "Отправить приглашение"}
                  <ArrowRight size={16} />
                </button>
              </form>
            ) : (
              <div className="modal-actions">
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() => {
                    setConfirmMember(null);
                    setConfirmInvite(null);
                  }}
                >
                  Отмена
                </button>
                <button
                  className="button danger"
                  disabled={busy}
                  onClick={confirmAction}
                >
                  {busy
                    ? "Подождите…"
                    : confirmMember
                      ? "Отключить доступ"
                      : "Отозвать"}
                </button>
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
