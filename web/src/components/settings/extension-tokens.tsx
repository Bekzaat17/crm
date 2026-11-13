"use client";
import { useState } from "react";
import { KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

type Token = {
  id: string;
  name: string;
  user: string;
  created_at: string;
  expires_at: string;
  last_used_at: string | null;
  revoked: boolean;
  secret?: string;
};

export function ExtensionTokens() {
  const { root } = useCompany();
  const tokens = useResource<{ items: Token[] }>(`${root}/extension-tokens`);
  const action = useMutation(tokens.reload);
  const [issued, setIssued] = useState<Token | null>(null);
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
      {issued?.secret && (
        <div className="alert success" role="status">
          <KeyRound size={17} />
          <div>
            <strong>
              Скопируйте ключ сейчас — он больше не будет показан.
            </strong>
            <code className="secret-value">{issued.secret}</code>
          </div>
        </div>
      )}
      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void action.run(async () =>
            setIssued(await api<Token>(`${root}/extension-tokens`, data)),
          );
        }}
      >
        <input
          name="name"
          required
          maxLength={80}
          defaultValue="Рабочий браузер"
          aria-label="Название ключа"
        />
        <button className="button primary" disabled={action.busy}>
          Выдать ключ
        </button>
      </form>
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
