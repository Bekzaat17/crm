import { CRM_URL } from "./config.js";

export type Settings = { crmUrl: string; key: string; company: string };

export async function loadSettings(): Promise<Settings> {
  const stored = (await chrome.storage.local.get([
    "key",
    "company",
  ])) as Partial<Settings>;
  return {
    crmUrl: CRM_URL,
    key: stored.key || "",
    company: stored.company || "",
  };
}

/** Вход через CRM. Вызывается только из фонового worker: popup закрывается,
 *  когда открывается окно входа, и потерял бы результат. */
export async function login() {
  const state = crypto.randomUUID();
  const url = `${CRM_URL}/extension/connect?${new URLSearchParams({
    redirect_uri: chrome.identity.getRedirectURL("crm"),
    state,
  })}`;
  const result = await chrome.identity.launchWebAuthFlow({
    url,
    interactive: true,
  });
  if (!result) throw new Error("Вход не завершён. Повторите подключение.");
  const params = new URLSearchParams(new URL(result).hash.slice(1));
  if (params.get("state") !== state || !params.get("token"))
    throw new Error("Вход не завершён. Повторите подключение.");
  await chrome.storage.local.set({
    key: params.get("token"),
    company: params.get("company") || "",
  });
}

/** Выход отзывает ключ в CRM, чтобы он не оставался действующим 90 дней. */
export async function logout() {
  const settings = await loadSettings();
  if (settings.key) {
    await fetch(`${CRM_URL}/api/ext/session/revoke/`, {
      method: "POST",
      credentials: "omit",
      headers: {
        Authorization: `Bearer ${settings.key}`,
        "Content-Type": "application/json",
      },
      body: "{}",
    }).catch(() => undefined);
  }
  await chrome.storage.local.remove(["key", "company"]);
}
