export type Settings = { crmUrl: string; key: string };

export async function loadSettings(): Promise<Settings> {
  const stored = (await chrome.storage.local.get([
    "crmUrl",
    "key",
  ])) as Partial<Settings>;
  return { crmUrl: stored.crmUrl || "", key: stored.key || "" };
}

/** Сохраняет адрес CRM и запрашивает доступ расширения только к этому адресу. */
export async function saveSettings(crmUrl: string, key: string) {
  const url = new URL(crmUrl);
  const local = ["127.0.0.1", "localhost"].includes(url.hostname);
  if (url.protocol !== "https:" && !(local && url.protocol === "http:"))
    throw new Error("Адрес CRM должен начинаться с https://");
  const origin = url.origin;
  const granted = await chrome.permissions.request({
    origins: [`${origin}/*`],
  });
  if (!granted) throw new Error("Разрешите расширению доступ к адресу CRM.");
  await chrome.storage.local.set({ crmUrl: origin, key: key.trim() });
}
