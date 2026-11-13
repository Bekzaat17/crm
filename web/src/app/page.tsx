"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LockKeyhole, LogOut } from "lucide-react";
import { api, type Session } from "@/lib/api";
import { lastCompany } from "@/lib/storage";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";

/** Точка входа: открывает последнюю доступную компанию. */
export default function Home() {
  const router = useRouter();
  const { data, error, reload } = useResource<Session>("auth/session");
  useEffect(() => {
    if (!data) return;
    if (!data.user) return router.replace("/login");
    const previous = lastCompany();
    const company =
      data.organizations.find((o) => o.id === previous) ||
      data.organizations[0];
    if (company) router.replace(`/c/${company.id}`);
    else if (data.user.is_platform_admin) router.replace("/platform");
  }, [data, router]);
  if (error)
    return (
      <main className="auth-shell">
        <ErrorAlert message={error} onRetry={reload} />
      </main>
    );
  if (data?.user && !data.organizations.length && !data.user.is_platform_admin)
    return (
      <main className="auth-shell">
        <div className="empty-state">
          <LockKeyhole size={32} />
          <h2>Пока нет доступа к компании</h2>
          <p>Попросите владельца отправить приглашение на вашу почту.</p>
          <button
            className="button secondary"
            onClick={() =>
              api("auth/logout", {}).finally(() => router.replace("/login"))
            }
          >
            <LogOut size={16} /> Выйти
          </button>
        </div>
      </main>
    );
  return <LoadingState text="Открываем рабочее пространство…" />;
}
