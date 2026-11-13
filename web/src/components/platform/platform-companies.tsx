"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight, Building2, LogOut, Plus } from "lucide-react";
import { api, type Session } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { Brand } from "@/components/brand";
import { ErrorAlert, LoadingState, Notice } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { PageHeading } from "@/components/ui/page-heading";

type Company = {
  id: string;
  name: string;
  created_at: string;
  members: number;
  owner:
    | { state: "active"; email: string; name: string }
    | { state: "invited"; email: string; expires_at: string }
    | { state: "missing" };
};

function OwnerCell({
  company,
  onInvite,
}: {
  company: Company;
  onInvite: () => void;
}) {
  const { owner } = company;
  if (owner.state === "active")
    return (
      <span>
        {owner.name} · {owner.email}
      </span>
    );
  return (
    <span>
      {owner.state === "invited"
        ? `Приглашение: ${owner.email}`
        : "Владелец не назначен"}{" "}
      <button className="text-button" onClick={onInvite}>
        {owner.state === "invited" ? "Отправить снова" : "Пригласить"}
      </button>
    </span>
  );
}

/** Раздел администратора платформы: создание компаний и приглашение владельцев. */
export function PlatformCompanies() {
  const router = useRouter();
  const session = useResource<Session>("auth/session");
  const companies = useResource<{ items: Company[] }>(
    session.data?.user?.is_platform_admin ? "platform/companies" : null,
  );
  const create = useMutation(() => {
    companies.reload();
    session.reload();
  });
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (session.data && !session.data.user) router.replace("/login");
  }, [session.data, router]);

  const invite = (company: Company) => {
    const email = window.prompt(
      `Почта владельца компании «${company.name}»`,
      company.owner.state === "invited" ? company.owner.email : "",
    );
    if (email)
      void create.run(async () => {
        const result = await api<{ message: string }>(
          `platform/companies/${company.id}/owner-invitation`,
          { owner_email: email },
        );
        setNotice(result.message);
      });
  };

  if (!session.data) return <LoadingState />;
  if (!session.data.user?.is_platform_admin)
    return (
      <main className="auth-shell">
        <div className="empty-state">
          <h2>Раздел платформы недоступен</h2>
          <p>Компании создаёт только администратор платформы.</p>
          <Link className="button secondary" href="/">
            Вернуться
          </Link>
        </div>
      </main>
    );
  const own = new Set(session.data.organizations.map((o) => o.id));
  return (
    <main className="platform-page">
      <header className="platform-header">
        <Brand />
        <button
          className="icon-button"
          aria-label="Выйти из аккаунта"
          onClick={() =>
            api("auth/logout", {}).finally(() => router.replace("/login"))
          }
        >
          <LogOut size={17} />
        </button>
      </header>
      <div className="workspace-content">
        <PageHeading
          eyebrow="АДМИНИСТРАТОР ПЛАТФОРМЫ"
          title="Компании"
          description="Создавайте компании и приглашайте их владельцев. Данные компаний видны только их сотрудникам."
        />
        <Notice message={notice} onClose={() => setNotice("")} />
        <article className="card">
          <h3>Новая компания</h3>
          <ErrorAlert message={create.error} />
          <form
            className="inline-form"
            onSubmit={(e) => {
              e.preventDefault();
              const form = e.currentTarget;
              const data = fields(form);
              void create.run(async () => {
                await api("platform/companies", data);
                form.reset();
                setNotice(
                  data.owner_email
                    ? "Компания создана, владельцу отправлено приглашение."
                    : "Компания создана, вы её владелец.",
                );
              });
            }}
          >
            <input
              name="name"
              required
              maxLength={160}
              placeholder="Название компании"
              aria-label="Название компании"
            />
            <input
              name="owner_email"
              type="email"
              maxLength={254}
              placeholder="Почта владельца (пусто — вы)"
              aria-label="Почта владельца"
            />
            <button className="button primary" disabled={create.busy}>
              <Plus size={16} /> Создать
            </button>
          </form>
        </article>
        <ErrorAlert message={companies.error} onRetry={companies.reload} />
        {!companies.data ? (
          <LoadingState />
        ) : (
          <div className="card table-card sales-section">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Компания</th>
                    <th>Владелец</th>
                    <th>Сотрудники</th>
                    <th>Создана</th>
                    <th>
                      <span className="sr-only">Открыть</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {companies.data.items.map((company) => (
                    <tr key={company.id}>
                      <td>
                        <div className="member-cell">
                          <Building2 size={18} />
                          <strong>{company.name}</strong>
                        </div>
                      </td>
                      <td>
                        <OwnerCell
                          company={company}
                          onInvite={() => invite(company)}
                        />
                      </td>
                      <td>{company.members}</td>
                      <td>{formatDateTime(company.created_at)}</td>
                      <td>
                        {own.has(company.id) && (
                          <Link
                            className="text-button"
                            href={`/c/${company.id}`}
                          >
                            Открыть <ArrowRight size={14} />
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
