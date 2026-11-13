"use client";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { useCompany } from "@/components/workspace/company-context";

type Token = {
  id: string;
  name: string;
  user: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked: boolean;
};

export function ExtensionTokens() {
  const { root } = useCompany();
  const tokens = useResource<{ items: Token[] }>(`${root}/extension-tokens`);
  const action = useMutation(tokens.reload);
  return (
    <article className="card">
      <div className="section-title">
        <h2>Расширение браузера</h2>
      </div>
      <p className="small muted">
        Расширение передаёт выбранный диалог WhatsApp Web или Instagram в
        обращение этой компании. Ключ действует 90 дней, работает только для
        вашего доступа и сразу перестаёт действовать после отзыва или отключения
        сотрудника. Пароли и сессии мессенджеров в CRM не передаются.
      </p>
      <ErrorAlert
        message={tokens.error || action.error}
        onRetry={tokens.reload}
      />
      <p className="small form-note">
        Подключение: установите расширение и нажмите в нём «Войти в RehubPro
        CRM». Ниже — подключённые браузеры, доступ любого можно отозвать.
      </p>
      {!tokens.data ? (
        <LoadingState />
      ) : (
        tokens.data.items.map((token) => (
          <div
            className={`settings-row ${token.revoked ? "archived" : ""}`}
            key={token.id}
          >
            <strong>{token.name}</strong>
            <span className="small muted">
              {token.user} · до {formatDateTime(token.expires_at)}
              {token.last_used_at &&
                ` · использован ${formatDateTime(token.last_used_at)}`}
            </span>
            {token.revoked ? (
              <span className="subtle-pill">Отозван</span>
            ) : (
              <div className="row-actions">
                <button
                  className="text-button danger-text"
                  disabled={action.busy}
                  onClick={() =>
                    void action.run(() =>
                      api(`${root}/extension-tokens/${token.id}/revoke`, {}),
                    )
                  }
                >
                  Отозвать
                </button>
              </div>
            )}
          </div>
        ))
      )}
    </article>
  );
}
