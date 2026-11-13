"use client";
import { useEffect, useState } from "react";
import { Puzzle, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { useMutation } from "@/lib/use-mutation";
import { useSession } from "@/lib/use-session";
import { Brand } from "@/components/brand";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";

/** Подтверждение входа расширения: CRM выдаёт ключ и возвращает его расширению. */
export function ExtensionConnect() {
  const session = useSession();
  const [request, setRequest] = useState({ redirect: "", state: "" });
  const [company, setCompany] = useState("");
  const allow = useMutation();
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setRequest({
      redirect: params.get("redirect_uri") || "",
      state: params.get("state") || "",
    });
  }, []);
  useEffect(() => {
    if (session.data?.organizations.length && !company)
      setCompany(session.data.organizations[0].id);
  }, [session.data, company]);

  if (session.error)
    return <ErrorAlert message={session.error} onRetry={session.reload} />;
  if (!session.data?.user) return <LoadingState />;
  const companies = session.data.organizations;
  return (
    <main className="connect-shell">
      <section className="card connect-card">
        <Brand />
        <span className="eyebrow">РАСШИРЕНИЕ БРАУЗЕРА</span>
        <h2>
          <Puzzle size={22} /> Подключить расширение
        </h2>
        <p className="muted">
          Расширение будет передавать в CRM только чаты, для которых вы включите
          «Отслеживать». Доступ можно отозвать в настройках компании.
        </p>
        <ErrorAlert
          message={
            allow.error ||
            (!request.redirect ? "Откройте эту страницу из расширения." : "")
          }
        />
        {companies.length ? (
          <div className="auth-form">
            <label>
              Компания
              <select
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              >
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} · {c.role_label}
                  </option>
                ))}
              </select>
            </label>
            <p className="form-note">
              <ShieldCheck size={15} /> Вход: {session.data.user.email}
            </p>
            <button
              className="button primary full"
              disabled={allow.busy || !request.redirect || !company}
              onClick={() =>
                void allow.run(async () => {
                  const result = await api<{ redirect: string }>(
                    "extension/authorize",
                    {
                      company_id: company,
                      redirect_uri: request.redirect,
                      state: request.state,
                    },
                  );
                  window.location.href = result.redirect;
                })
              }
            >
              Разрешить доступ
            </button>
          </div>
        ) : (
          <p className="muted">Вы пока не состоите ни в одной компании.</p>
        )}
      </section>
    </main>
  );
}
