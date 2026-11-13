import {
  chatPhone,
  CrmClient,
  type ChatRef,
  type ChatStatus,
} from "./crm-client.js";
import { loadSettings, login, logout } from "./settings.js";
import type { ReadResult } from "./types.js";

const $ = <T extends HTMLElement>(id: string) =>
  document.getElementById(id) as T;
const show = (id: string, visible: boolean) => ($(id).hidden = !visible);
const status = (text: string, error = false) => {
  $("status").textContent = text;
  $("status").className = error ? "status error" : "status";
};
const message = (error: unknown) =>
  error instanceof Error ? error.message : "Ошибка";

let client: CrmClient | null = null;
let read: ReadResult | null = null;
let tabId: number | undefined;

const chatRef = (fragment: ReadResult): ChatRef => ({
  source: fragment.source,
  external_id: fragment.conversation.external_id,
});

async function readActiveTab(): Promise<ReadResult> {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  tabId = tab?.id;
  if (!tabId) throw new Error("Нет активной вкладки.");
  try {
    const response = await chrome.tabs.sendMessage(tabId, {
      type: "rehub:read",
    });
    if (!response?.ok)
      throw new Error(response?.error || "Не удалось прочитать диалог.");
    return response.result as ReadResult;
  } catch (error) {
    if (error instanceof Error && !error.message.includes("Receiving end"))
      throw error;
    throw new Error(
      "Откройте чат WhatsApp Web, Telegram Web или Instagram и обновите страницу.",
    );
  }
}

function fillLeads(
  items: { id: string; title: string; client_name: string; stage: string }[],
) {
  $<HTMLSelectElement>("lead").replaceChildren(
    ...items.map((lead) =>
      Object.assign(document.createElement("option"), {
        value: lead.id,
        textContent: `${lead.client_name} · ${lead.title} (${lead.stage})`,
      }),
    ),
  );
  $<HTMLInputElement>("track").disabled = !items.length;
}

function renderStatus(current: ChatStatus) {
  show("tracked", current.tracked);
  show("untracked", !current.tracked);
  if (current.tracked && current.lead)
    $("tracked-lead").textContent =
      `✓ Отслеживается → ${current.lead.client_name} · ${current.lead.title}`;
}

async function suggestLeads(fragment: ReadResult) {
  if (!client) return;
  const phone = chatPhone(fragment);
  if (phone) {
    const { items } = await client.match(phone);
    if (items.length) {
      fillLeads(items);
      $("match-note").textContent =
        items.length === 1
          ? "Найдено по номеру собеседника."
          : "По номеру найдено несколько обращений — выберите нужное.";
      return;
    }
    $("match-note").textContent =
      "Номер не найден в CRM. Выберите обращение поиском.";
  }
  fillLeads((await client.leads("")).items);
}

async function start() {
  const settings = await loadSettings();
  $<HTMLInputElement>("crm-url").value = settings.crmUrl;
  if (!settings.key) {
    show("login-form", true);
    show("logout", false);
    status("Войдите один раз — дальше расширение работает само.");
    return;
  }
  show("login-form", false);
  show("logout", true);
  client = new CrmClient(settings);
  try {
    const session = await client.session();
    $("account").textContent = `${session.company} · ${session.user}`;
    read = await readActiveTab();
    $("chat-title").textContent = read.conversation.title;
    $("chat-meta").textContent = `${read.messages.length} сообщ. на странице`;
    $("warnings").replaceChildren(
      ...read.warnings.map((w) =>
        Object.assign(document.createElement("li"), { textContent: w }),
      ),
    );
    show("chat", true);
    const current = await client.status(chatRef(read));
    renderStatus(current);
    if (!current.tracked) await suggestLeads(read);
    status("");
  } catch (error) {
    status(message(error), true);
  }
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    status("Подтвердите доступ на странице CRM…");
    await login($<HTMLInputElement>("crm-url").value);
    await start();
  } catch (error) {
    status(message(error), true);
  }
});

$("logout").addEventListener("click", async () => {
  await logout();
  show("chat", false);
  $("account").textContent = "";
  await start();
});

let timer = 0;
$("lead-search").addEventListener("input", () => {
  clearTimeout(timer);
  timer = window.setTimeout(async () => {
    try {
      fillLeads(
        (await client!.leads($<HTMLInputElement>("lead-search").value)).items,
      );
      $("match-note").textContent = "";
    } catch (error) {
      status(message(error), true);
    }
  }, 250);
});

$("track").addEventListener("change", async () => {
  if (!client || !read || !$<HTMLInputElement>("track").checked) return;
  try {
    const current = await client.track(
      chatRef(read),
      read.conversation.title,
      $<HTMLSelectElement>("lead").value,
    );
    renderStatus(current);
    await chrome.runtime.sendMessage({ type: "rehub:status-changed" });
    if (tabId) await chrome.tabs.sendMessage(tabId, { type: "rehub:resync" });
    status("Чат отслеживается. Сообщения передаются в CRM.");
  } catch (error) {
    $<HTMLInputElement>("track").checked = false;
    status(message(error), true);
  }
});

$("untrack").addEventListener("click", async () => {
  if (!client || !read) return;
  try {
    renderStatus(await client.untrack(chatRef(read)));
    await chrome.runtime.sendMessage({ type: "rehub:status-changed" });
    $<HTMLInputElement>("track").checked = false;
    await suggestLeads(read);
    status("Отслеживание выключено. Уже переданные сообщения остаются в CRM.");
  } catch (error) {
    status(message(error), true);
  }
});

$("sync").addEventListener("click", async () => {
  if (!tabId) return;
  await chrome.runtime.sendMessage({ type: "rehub:status-changed" });
  await chrome.tabs.sendMessage(tabId, { type: "rehub:resync" });
  status("Синхронизация запущена.");
});

void start();
