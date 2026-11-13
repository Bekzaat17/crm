import { CrmClient } from "./crm-client.js";
import { loadSettings, saveSettings } from "./settings.js";
import type { ReadResult } from "./types.js";

const $ = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const show = (id: string, visible: boolean) => ($(id).hidden = !visible);
const status = (text: string, error = false) => {
  $("status").textContent = text;
  $("status").className = error ? "status error" : "status";
};

let read: ReadResult | null = null;
let client: CrmClient | null = null;

/** Один ключ повтора на фрагмент: после потери ответа повтор не создаст дублей. */
async function idempotencyKey(fragment: ReadResult, leadId: string) {
  const signature = JSON.stringify([
    fragment.conversation.external_id,
    leadId,
    fragment.messages.length,
    fragment.messages.at(-1)?.external_id || fragment.messages.at(-1)?.text,
  ]);
  const { pending } = (await chrome.storage.local.get("pending")) as {
    pending?: { signature: string; key: string };
  };
  if (pending?.signature === signature) return pending.key;
  const key = crypto.randomUUID();
  await chrome.storage.local.set({ pending: { signature, key } });
  return key;
}

async function readActiveTab(): Promise<ReadResult> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) throw new Error("Нет активной вкладки.");
  try {
    const response = await chrome.tabs.sendMessage(tab.id, {
      type: "rehub:read",
    });
    if (!response?.ok)
      throw new Error(response?.error || "Не удалось прочитать диалог.");
    return response.result as ReadResult;
  } catch (error) {
    if (error instanceof Error && !error.message.includes("Receiving end"))
      throw error;
    throw new Error(
      "Откройте диалог WhatsApp Web или Instagram Direct и обновите страницу.",
    );
  }
}

function renderPreview(fragment: ReadResult) {
  $("conversation").textContent =
    `${fragment.conversation.title} · ${fragment.messages.length} сообщ.`;
  const list = $("messages");
  list.replaceChildren();
  const sample = [
    ...fragment.messages.slice(0, 3),
    ...fragment.messages.slice(-3),
  ];
  for (const message of new Set(sample)) {
    const item = document.createElement("li");
    item.className = message.direction;
    item.textContent = message.text || "Вложение";
    list.append(item);
  }
  const warnings = $("warnings");
  warnings.replaceChildren(
    ...fragment.warnings.map((w) =>
      Object.assign(document.createElement("li"), { textContent: w }),
    ),
  );
  show("preview", true);
}

async function searchLeads() {
  if (!client) return;
  const select = $<HTMLSelectElement>("lead");
  const { items } = await client.leads(
    $<HTMLInputElement>("lead-search").value,
  );
  select.replaceChildren(
    ...items.map((lead) =>
      Object.assign(document.createElement("option"), {
        value: lead.id,
        textContent: `${lead.client_name} · ${lead.title} (${lead.stage})`,
      }),
    ),
  );
  $<HTMLButtonElement>("send").disabled = !items.length || !read;
}

async function start() {
  const settings = await loadSettings();
  $<HTMLInputElement>("crm-url").value = settings.crmUrl;
  if (!settings.crmUrl || !settings.key) {
    show("settings-form", true);
    status("Укажите адрес CRM и ключ из настроек «Расширение браузера».");
    return;
  }
  client = new CrmClient(settings);
  try {
    const session = await client.session();
    $("account").textContent = `${session.company} · ${session.user}`;
    read = await readActiveTab();
    renderPreview(read);
    await searchLeads();
    status("Проверьте сообщения и выберите обращение.");
  } catch (error) {
    status(error instanceof Error ? error.message : "Ошибка", true);
  }
}

$("toggle-settings").addEventListener("click", () =>
  show("settings-form", $("settings-form").hidden),
);
$("settings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await saveSettings(
      $<HTMLInputElement>("crm-url").value,
      $<HTMLInputElement>("key").value,
    );
    $<HTMLInputElement>("key").value = "";
    show("settings-form", false);
    await start();
  } catch (error) {
    status(error instanceof Error ? error.message : "Ошибка", true);
  }
});
let timer = 0;
$("lead-search").addEventListener("input", () => {
  clearTimeout(timer);
  timer = window.setTimeout(
    () => void searchLeads().catch((e) => status(e.message, true)),
    250,
  );
});
$("send").addEventListener("click", async () => {
  if (!client || !read) return;
  const leadId = $<HTMLSelectElement>("lead").value;
  const button = $<HTMLButtonElement>("send");
  button.disabled = true;
  status("Передаём…");
  try {
    const result = await client.importFragment(
      read,
      leadId,
      await idempotencyKey(read, leadId),
    );
    await chrome.storage.local.remove("pending");
    status(
      `Готово: новых сообщений ${result.created}, уже были в CRM ${result.duplicates}.`,
    );
  } catch (error) {
    // Ключ повтора сохранён: нажмите ещё раз, дублей не будет.
    status(
      `${error instanceof Error ? error.message : "Ошибка"} Можно безопасно повторить.`,
      true,
    );
    button.disabled = false;
  }
});

void start();
