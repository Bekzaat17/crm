"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime, todayInput } from "@/lib/format";
import type { ClientRecord, LeadRecord } from "@/lib/types";
import { useInterval } from "@/lib/use-interval";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";

type Center = { id: string; name: string; domain: string };
type Transfer = {
  id: string;
  center_name: string;
  domain: string;
  status: string;
  status_label: string;
  attempt_count: number;
  resident_id: string;
  last_error: string;
  next_attempt_at: string | null;
  attempts: {
    number: number;
    outcome: string;
    http_status: number | null;
    started_at: string;
  }[];
};
const errorLabels: Record<string, string> = {
  network_error: "Сеть недоступна; CRM повторит передачу.",
  connection_inactive: "Центр отключён или не проверен.",
  remote_access_denied:
    "Центр не разрешил доступ. Проверьте ключ, лицензию и сетевые настройки.",
  remote_conflict: "Центр сообщил о конфликте данных. Нужна ручная проверка.",
  invalid_response: "Центр вернул неподтверждённый ответ.",
  connection_configuration: "Проверьте настройки ключа подключения.",
  unsafe_destination: "Адрес центра не прошёл проверку безопасности.",
  redirect_forbidden: "Центр перенаправляет запрос. Проверьте адрес API.",
};
export function Admission({
  root,
  lead,
  canSend,
  onSaved,
}: {
  root: string;
  lead: LeadRecord;
  canSend: boolean;
  onSaved: () => void;
}) {
  const [showForm, setShowForm] = useState(false);
  // Центры и карточка клиента не меняются во время опроса — грузим один раз.
  const destinations = useResource<{ items: Center[] }>(`${root}/destinations`);
  const card = useResource<ClientRecord>(`${root}/clients/${lead.client_id}`);
  const history = useResource<{ items: Transfer[] }>(
    `${root}/leads/${lead.id}/transfers`,
  );
  const centers = destinations.data?.items || [];
  const client = card.data;
  const transfers = history.data?.items || [];
  const error = destinations.error || card.error || history.error;
  const {
    busy,
    error: mutationError,
    run,
  } = useMutation(() => {
    history.reload();
    card.reload();
    onSaved();
  });
  const inFlight = transfers.some((t) =>
    ["pending", "retry", "sending"].includes(t.status),
  );
  // Пока передача в очереди, каждые 5 секунд обновляется только её статус.
  useInterval(history.reload, inFlight ? 5000 : null);
  return (
    <section className="admission-section">
      <h3>Передача в RehubPro</h3>
      <p className="card-intro">
        Создание резидента выполняется только после вашего подтверждения
        фактического поступления. Повторные попытки используют одну и ту же
        операцию.
      </p>
      <ErrorAlert message={error || mutationError} />
      {transfers.map((transfer) => (
        <article className="transfer-card" key={transfer.id}>
          <div className="section-title">
            <strong>{transfer.center_name}</strong>
            <span className="subtle-pill">{transfer.status_label}</span>
          </div>
          <p>
            {transfer.domain} · Попыток: {transfer.attempt_count}
            {transfer.resident_id ? ` · Резидент №${transfer.resident_id}` : ""}
          </p>
          {transfer.last_error && (
            <p className="transfer-error">
              {errorLabels[transfer.last_error] ||
                "Передача требует внимания. Проверьте подключение центра."}
            </p>
          )}
          {transfer.next_attempt_at && (
            <p>Следующая попытка: {formatDateTime(transfer.next_attempt_at)}</p>
          )}
          <details>
            <summary>История доставки</summary>
            {transfer.attempts.map((attempt) => (
              <p key={attempt.number}>
                Попытка {attempt.number} · {formatDateTime(attempt.started_at)}{" "}
                ·{" "}
                {attempt.http_status
                  ? `HTTP ${attempt.http_status}`
                  : "Без HTTP-ответа"}{" "}
                ·{" "}
                {attempt.outcome === "delivered"
                  ? "Подтверждена"
                  : attempt.outcome === "unknown"
                    ? "Результат пока неизвестен"
                    : "Не подтверждена"}
              </p>
            ))}
          </details>
          {canSend &&
            ["failed", "blocked", "conflict"].includes(transfer.status) && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() =>
                  run(() => api(`${root}/transfers/${transfer.id}/retry`, {}))
                }
              >
                Повторить исходную передачу
              </button>
            )}
        </article>
      ))}
      {canSend && (
        <>
          <button
            type="button"
            className="button secondary"
            disabled={!client || !centers.length}
            onClick={() => setShowForm((value) => !value)}
          >
            {showForm ? "Скрыть форму" : "Подготовить передачу"}
          </button>
          {!centers.length && (
            <p className="small muted integration-intro">
              В настройках компании добавьте центр, сохраните ключ и проверьте
              подключение.
            </p>
          )}
        </>
      )}
      {canSend && showForm && client && (
        <form
          className="auth-form sales-section"
          onSubmit={(event) => {
            event.preventDefault();
            const data = fields(event.currentTarget);
            void run(async () => {
              await api(`${root}/leads/${lead.id}/transfers`, {
                ...data,
                confirmed: data.confirmed === "on",
                version: lead.version,
                client_version: client.version,
              });
              setShowForm(false);
            });
          }}
        >
          <label>
            Центр
            <select name="center_id" required>
              <option value="">Выберите центр</option>
              {centers.map((center) => (
                <option key={center.id} value={center.id}>
                  {center.name} · {center.domain}
                </option>
              ))}
            </select>
          </label>
          <p className="small muted">
            Имя в CRM: {client.name}. Укажите фамилию и имя отдельно для личного
            дела.
          </p>
          <label>
            Фамилия
            <input name="last_name" required maxLength={100} />
          </label>
          <label>
            Имя
            <input name="first_name" required maxLength={100} />
          </label>
          <label>
            Отчество
            <input name="middle_name" maxLength={100} />
          </label>
          <label>
            Фактическая дата поступления
            <input
              name="date_of_admission"
              type="date"
              required
              max={todayInput()}
            />
          </label>
          <div className="admission-preview">
            <strong>Будет передано</strong>
            <p>
              Дата рождения: {client.date_of_birth || "не указана"} · Телефон:{" "}
              {client.phone || "не указан"} · Город:{" "}
              {client.city || "не указан"}
            </p>
            {client.contacts?.slice(0, 20).map((contact) => (
              <p key={contact.id}>
                {contact.name} · {contact.relationship} ·{" "}
                {contact.phone || "без телефона"}
              </p>
            ))}
            <p>Комментарии, заметки и история общения не передаются.</p>
          </div>
          <label className="confirmation-check">
            <input type="checkbox" name="confirmed" required />
            Подтверждаю центр, данные клиента и фактическую дату поступления.
            Разрешаю передать указанные данные этому центру.
          </label>
          <button className="button primary" disabled={busy}>
            Подтвердить и поставить в очередь
          </button>
        </form>
      )}
    </section>
  );
}
