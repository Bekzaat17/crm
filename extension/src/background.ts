import {
  CrmClient,
  CrmError,
  fragmentKey,
  type ChatStatus,
} from "./crm-client.js";
import { loadSettings, login, logout } from "./settings.js";
import type { ReadResult } from "./types.js";

type SyncRequest = { type: "rehub:sync"; read: ReadResult };
export type SyncResponse = {
  connected: boolean;
  tracked: boolean;
  created?: number;
  error?: string;
  /** Через сколько миллисекунд можно повторить после ошибки. */
  retryIn?: number;
};

const STATUS_TTL = 60_000;
const statusCache = new Map<string, { at: number; status: ChatStatus }>();
/** Ошибки по чату: экспоненциальная пауза, чтобы не исчерпать лимит запросов. */
const failures = new Map<string, number>();

const chatKey = (read: ReadResult) =>
  `${read.source}:${read.conversation.external_id}`;

const message = (error: unknown, fallback: string) =>
  error instanceof Error ? error.message : fallback;

function retryDelay(key: string, error: unknown) {
  const count = (failures.get(key) || 0) + 1;
  failures.set(key, count);
  // Ошибки данных (400/403/404/409/413) повторять бессмысленно: пауза 15 минут.
  if (
    error instanceof CrmError &&
    error.status >= 400 &&
    error.status < 500 &&
    error.status !== 429
  )
    return 15 * 60_000;
  return Math.min(15 * 60_000, 10_000 * 2 ** (count - 1));
}

async function status(client: CrmClient, read: ReadResult) {
  const key = chatKey(read);
  const cached = statusCache.get(key);
  if (cached && Date.now() - cached.at < STATUS_TTL) return cached.status;
  const fresh = await client.status({
    source: read.source,
    external_id: read.conversation.external_id,
  });
  statusCache.set(key, { at: Date.now(), status: fresh });
  return fresh;
}

async function signedOut(usedKey: string) {
  // Удаляем ключ, только если за время запроса не выполнен новый вход.
  const current = await loadSettings();
  if (current.key === usedKey)
    await chrome.storage.local.remove(["key", "company"]);
  await chrome.action.setBadgeText({ text: "!" });
  await chrome.action.setBadgeBackgroundColor({ color: "#b91c1c" });
}

/** Автосинхронизация: передаём только чаты с включённой галочкой. */
async function sync(read: ReadResult): Promise<SyncResponse> {
  const settings = await loadSettings();
  if (!settings.key) return { connected: false, tracked: false };
  const client = new CrmClient(settings);
  const key = chatKey(read);
  try {
    const current = await status(client, read);
    if (!current.tracked || !current.lead)
      return { connected: true, tracked: false };
    const result = await client.importFragment(
      read,
      current.lead.id,
      await fragmentKey(read),
    );
    failures.delete(key);
    return { connected: true, tracked: true, created: result.created };
  } catch (error) {
    if (error instanceof CrmError && error.status === 401) {
      await signedOut(settings.key);
      return {
        connected: false,
        tracked: false,
        error: "войдите в расширение снова",
      };
    }
    return {
      connected: true,
      tracked: true,
      error: message(error, "ошибка синхронизации"),
      retryIn: retryDelay(key, error),
    };
  }
}

/** Ошибки окна входа Chrome приходят по-английски. */
function loginError(error: unknown) {
  const text = message(error, "");
  if (/did not approve|closed|canceled|cancelled/i.test(text))
    return "Окно входа закрыто. Нажмите «Войти» ещё раз.";
  if (/could not be loaded|ERR_/i.test(text))
    return "CRM недоступна. Проверьте подключение.";
  return text || "Вход не выполнен.";
}

type Request = SyncRequest | { type: string };

chrome.runtime.onMessage.addListener((request: Request, sender, respond) => {
  // Сообщения принимаются только от частей самого расширения.
  if (sender.id !== chrome.runtime.id) return;
  switch (request.type) {
    case "rehub:sync":
      void sync((request as SyncRequest).read).then(respond);
      return true;
    case "rehub:login":
      login()
        .then(async () => {
          statusCache.clear();
          failures.clear();
          await chrome.action.setBadgeText({ text: "" });
          respond({ ok: true });
        })
        .catch((error) => respond({ ok: false, error: loginError(error) }));
      return true;
    case "rehub:logout":
      void logout().then(() => {
        statusCache.clear();
        respond({ ok: true });
      });
      return true;
    case "rehub:status-changed":
      statusCache.clear();
      failures.clear();
      respond({ ok: true });
      return;
  }
});

// Ключ не нужен content scripts: закрываем к нему доступ из страниц мессенджеров.
chrome.storage.local
  .setAccessLevel?.({ accessLevel: "TRUSTED_CONTEXTS" })
  .catch(() => undefined);
