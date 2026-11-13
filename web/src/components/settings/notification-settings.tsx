"use client";
import { useEffect, useState } from "react";
import { Bell, Send } from "lucide-react";
import { api } from "@/lib/api";
import { currentSubscription, pushSupported, subscribePush } from "@/lib/push";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";

type Flags = { email: boolean; telegram: boolean; webpush: boolean };
type State = {
  preferences: Flags;
  telegram: { available: boolean; linked: boolean; blocked: boolean };
  webpush: { available: boolean; public_key: string; subscriptions: number };
};

const PATH = "me/notifications";

export function NotificationSettings() {
  const settings = useResource<State>(PATH);
  const action = useMutation();
  const [linkUrl, setLinkUrl] = useState("");
  const [browserSubscribed, setBrowserSubscribed] = useState(false);
  useEffect(() => {
    void currentSubscription().then((s) => setBrowserSubscribed(Boolean(s)));
  }, []);
  const update = (values: Partial<Flags>) =>
    action.run(async () => settings.setData(await api<State>(PATH, values)));

  if (settings.error)
    return <ErrorAlert message={settings.error} onRetry={settings.reload} />;
  if (!settings.data) return <LoadingState />;
  const { preferences, telegram, webpush } = settings.data;

  async function enablePush(publicKey: string) {
    await action.run(async () => {
      const subscription = (await subscribePush(publicKey)).toJSON();
      settings.setData(
        await api<State>("me/push/subscribe", {
          endpoint: subscription.endpoint,
          keys: subscription.keys,
        }),
      );
      setBrowserSubscribed(true);
    });
  }
  async function disablePush() {
    await action.run(async () => {
      const subscription = await currentSubscription();
      if (subscription) {
        await api("me/push/unsubscribe", { endpoint: subscription.endpoint });
        await subscription.unsubscribe();
      }
      setBrowserSubscribed(false);
      settings.reload();
    });
  }

  return (
    <article className="card">
      <div className="section-title">
        <h2>Напоминания</h2>
      </div>
      <p className="small muted">
        Когда наступает срок задачи или время следующего контакта, CRM пришлёт
        короткое напоминание без имени клиента. Подробности открываются по
        ссылке после входа. Настройки действуют для всех ваших компаний.
      </p>
      <ErrorAlert message={action.error} />

      <div className="settings-row">
        <Send size={18} />
        <strong>Telegram</strong>
        {!telegram.available ? (
          <span className="small muted">Бот не настроен на сервере CRM</span>
        ) : telegram.linked ? (
          <span className="subtle-pill">Подключён</span>
        ) : (
          <span className="small muted">
            {telegram.blocked ? "Отключён командой /stop" : "Не подключён"}
          </span>
        )}
        <div className="row-actions">
          {telegram.available && (
            <label className="toggle">
              <input
                type="checkbox"
                checked={preferences.telegram}
                disabled={action.busy}
                onChange={(e) => void update({ telegram: e.target.checked })}
              />
              Получать
            </label>
          )}
          {telegram.available && (
            <button
              className="text-button"
              disabled={action.busy}
              onClick={() =>
                void action.run(async () => {
                  const result = await api<{ url: string }>(
                    "me/telegram/link",
                    {},
                  );
                  setLinkUrl(result.url);
                })
              }
            >
              {telegram.linked ? "Подключить другой чат" : "Подключить"}
            </button>
          )}
          {(telegram.linked || telegram.blocked) && (
            <button
              className="text-button danger-text"
              disabled={action.busy}
              onClick={() =>
                void action.run(async () =>
                  settings.setData(await api<State>("me/telegram/unlink", {})),
                )
              }
            >
              Отвязать
            </button>
          )}
        </div>
      </div>
      {linkUrl && (
        <p className="small form-note">
          Откройте{" "}
          <a href={linkUrl} target="_blank" rel="noopener noreferrer">
            ссылку на бота
          </a>{" "}
          и нажмите «Start». Ссылка действует 15 минут, затем обновите эту
          страницу.
        </p>
      )}

      <div className="settings-row">
        <Bell size={18} />
        <strong>Уведомления браузера</strong>
        {!webpush.available ? (
          <span className="small muted">Не настроены на сервере CRM</span>
        ) : !pushSupported() ? (
          <span className="small muted">Этот браузер не поддерживает</span>
        ) : (
          <span className="small muted">
            {browserSubscribed ? "Включены в этом браузере" : "Выключены"}
            {webpush.subscriptions > 0 &&
              ` · устройств: ${webpush.subscriptions}`}
          </span>
        )}
        <div className="row-actions">
          {webpush.available && (
            <label className="toggle">
              <input
                type="checkbox"
                checked={preferences.webpush}
                disabled={action.busy}
                onChange={(e) => void update({ webpush: e.target.checked })}
              />
              Получать
            </label>
          )}
          {webpush.available && pushSupported() && (
            <button
              className="text-button"
              disabled={action.busy}
              onClick={() =>
                void (browserSubscribed
                  ? disablePush()
                  : enablePush(webpush.public_key))
              }
            >
              {browserSubscribed
                ? "Выключить здесь"
                : "Включить в этом браузере"}
            </button>
          )}
        </div>
      </div>

      <div className="settings-row">
        <strong>Почта</strong>
        <span className="small muted">Напоминания на адрес аккаунта</span>
        <div className="row-actions">
          <label className="toggle">
            <input
              type="checkbox"
              checked={preferences.email}
              disabled={action.busy}
              onChange={(e) => void update({ email: e.target.checked })}
            />
            Получать
          </label>
        </div>
      </div>
    </article>
  );
}
