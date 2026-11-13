"use client";
import { api } from "@/lib/api";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { useCompany } from "@/components/workspace/company-context";

type Center = {
  id: string;
  company_id: string;
  name: string;
  domain: string;
  endpoint: string;
  has_key: boolean;
  verified: boolean;
  is_active: boolean;
  version: number;
};
function CenterCard({
  center,
  root,
  onSaved,
}: {
  center: Center;
  root: string;
  onSaved: () => void;
}) {
  const { busy, error, run } = useMutation(onSaved);
  const command = `python manage.py issue_crm_key --company ${center.company_id} --connection ${center.id}`;
  return (
    <article className="card">
      <div className="section-title">
        <h2>{center.name}</h2>
        <span className="subtle-pill">
          {!center.is_active
            ? "Отключён"
            : center.verified
              ? "Проверен"
              : "Не проверен"}
        </span>
      </div>
      <p className="integration-address">{center.endpoint}</p>
      <ErrorAlert message={error} />
      <form
        className="auth-form"
        onSubmit={(event) => {
          event.preventDefault();
          const data = fields(event.currentTarget);
          if (!data.key) delete data.key;
          void run(() =>
            api(`${root}/centers/${center.id}`, {
              ...data,
              version: center.version,
            }),
          );
        }}
      >
        <label>
          Название центра
          <input
            name="name"
            defaultValue={center.name}
            required
            maxLength={160}
          />
        </label>
        <label>
          Домен или ссылка
          <input
            name="address"
            defaultValue={center.domain}
            required
            maxLength={2000}
          />
        </label>
        <label>
          {center.has_key ? "Заменить ключ подключения" : "Ключ подключения"}
          <input
            name="key"
            type="password"
            autoComplete="new-password"
            maxLength={256}
            placeholder={
              center.has_key
                ? "Ключ сохранён; оставьте поле пустым"
                : "Вставьте ключ из RehubPro"
            }
          />
        </label>
        <button className="button secondary" disabled={busy}>
          Сохранить
        </button>
      </form>
      <details className="integration-help">
        <summary>Как подключить этот центр</summary>
        <p>
          На сервере этого центра установите обновление с CRM API, выполните
          миграции и включите CRM_BRIDGE_ENABLED=1. Затем администратор центра
          выдаёт ключ командой:
        </p>
        <code>{command}</code>
        <p>
          Ключ привязан к вашей компании и этому подключению. Сохраните его в
          поле выше и проверьте подключение. В сетевых настройках центра должен
          быть разрешён адрес сервера CRM.
        </p>
      </details>
      <div className="task-actions">
        <button
          className="button primary"
          disabled={busy || !center.has_key || !center.is_active}
          onClick={() =>
            run(() => api(`${root}/centers/${center.id}/verify`, {}))
          }
        >
          Проверить подключение
        </button>
        <button
          className="button secondary"
          disabled={busy}
          onClick={() =>
            run(() =>
              api(`${root}/centers/${center.id}`, {
                version: center.version,
                is_active: !center.is_active,
              }),
            )
          }
        >
          {center.is_active ? "Отключить" : "Включить"}
        </button>
      </div>
    </article>
  );
}
export function Centers() {
  const { root } = useCompany();
  const centers = useResource<{ items: Center[] }>(`${root}/centers`);
  const refresh = centers.reload;
  const mutation = useMutation(refresh);
  return (
    <section>
      <article className="card">
        <h2>Добавить центр RehubPro</h2>
        <p className="sales-hint muted integration-intro">
          Вставьте домен или полную ссылку. Например,
          test.rehubpro.kz/qqweqw/qweqwe станет
          https://test.rehubpro.kz/crm/create. Путь страницы будет отброшен.
        </p>
        <ErrorAlert message={mutation.error} />
        <form
          className="auth-form"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const data = fields(form);
            void mutation.run(async () => {
              await api(`${root}/centers`, data);
              form.reset();
            });
          }}
        >
          <div className="form-grid">
            <label>
              Название центра
              <input
                name="name"
                required
                maxLength={160}
                placeholder="Название центра"
              />
            </label>
            <label>
              Домен или ссылка
              <input
                name="address"
                required
                maxLength={2000}
                placeholder="test.rehubpro.kz/страница"
              />
            </label>
          </div>
          <button className="button primary" disabled={mutation.busy}>
            Добавить центр
          </button>
        </form>
      </article>
      <ErrorAlert message={centers.error} onRetry={refresh} />
      {!centers.data ? (
        <LoadingState text="Загружаем центры…" />
      ) : (
        <div className="task-list sales-section">
          {centers.data.items.map((center) => (
            <CenterCard
              key={`${center.id}-${center.version}`}
              center={center}
              root={root}
              onSaved={refresh}
            />
          ))}
        </div>
      )}
    </section>
  );
}
