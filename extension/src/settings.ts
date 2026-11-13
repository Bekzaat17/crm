export type Settings = { crmUrl: string; key: string; company: string };

export async function loadSettings(): Promise<Settings> {
  const stored = (await chrome.storage.local.get([
    "crmUrl",
    "key",
    "company",
  ])) as Partial<Settings>;
  return {
    crmUrl: stored.crmUrl || "",
    key: stored.key || "",
    company: stored.company || "",
  };
}

function crmOrigin(value: string) {
  const url = new URL(value);
  const local = ["127.0.0.1", "localhost"].includes(url.hostname);
  if (url.protocol !== "https:" && !(local && url.protocol === "http:"))
    throw new Error("Адрес CRM должен начинаться с https://");
  return url.origin;
}

/** Вход через CRM: пользователь подтверждает доступ на сайте, ключ приходит
 *  во фрагменте адреса расширения и сохраняется только в chrome.storage. */
export async function login(crmUrl: string) {
  const origin = crmOrigin(crmUrl);
  const granted = await chrome.permissions.request({
    origins: [`${origin}/*`],
  });
  if (!granted) throw new Error("Разрешите расширению доступ к адресу CRM.");
  const state = crypto.randomUUID();
  const redirect = chrome.identity.getRedirectURL("crm");
  const url = `${origin}/extension/connect?${new URLSearchParams({
    redirect_uri: redirect,
    state,
  })}`;
  const result = await chrome.identity.launchWebAuthFlow({
    url,
    interactive: true,
  });
  const params = new URLSearchParams(new URL(result || "").hash.slice(1));
  if (params.get("state") !== state || !params.get("token"))
    throw new Error("Вход не завершён. Повторите подключение.");
  await chrome.storage.local.set({
    crmUrl: origin,
    key: params.get("token"),
    company: params.get("company") || "",
  });
}

export async function logout() {
  await chrome.storage.local.remove(["key", "company"]);
}
