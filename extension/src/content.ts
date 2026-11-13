import { readerFor } from "./adapters/index.js";
import type { ReadResult } from "./types.js";
import type { SyncResponse } from "./background.js";

const SYNC_DELAY = 3000;
let lastSignature = "";
/** После ошибки не повторяем раньше этого времени (лимит запросов CRM). */
let pausedUntil = 0;
let timer: number | undefined;

function readCurrent(): ReadResult | null {
  try {
    return readerFor(location).read(document);
  } catch {
    return null;
  }
}

function badge(text: string, error = false) {
  let element = document.getElementById("rehub-crm-badge");
  if (!element) {
    element = document.createElement("div");
    element.id = "rehub-crm-badge";
    element.style.cssText =
      "position:fixed;right:16px;bottom:16px;z-index:2147483647;padding:6px 10px;" +
      "border-radius:8px;font:12px system-ui,sans-serif;color:#fff;pointer-events:none;";
    document.documentElement.append(element);
  }
  element.textContent = text;
  element.style.background = error ? "#b91c1c" : "#2563eb";
  element.hidden = !text;
}

/** Новые сообщения отмеченного чата передаются через фоновый worker. */
async function syncIfChanged() {
  const read = readCurrent();
  if (!read) return badge("");
  const last = read.messages.at(-1);
  const signature = [
    read.conversation.external_id,
    read.messages.length,
    last?.external_id || last?.text,
  ].join("|");
  if (signature === lastSignature || Date.now() < pausedUntil) return;
  lastSignature = signature;
  let result: SyncResponse;
  try {
    result = (await chrome.runtime.sendMessage({
      type: "rehub:sync",
      read,
    })) as SyncResponse;
  } catch {
    // Расширение обновили или перезапустили: страницу нужно обновить.
    lastSignature = "";
    return badge("CRM: обновите страницу", true);
  }
  if (!result?.connected)
    return badge(
      result?.error ? `CRM: ${result.error}` : "",
      Boolean(result?.error),
    );
  if (!result.tracked) return badge("");
  if (result.error) {
    // Повторим после паузы, которую назначил фоновый worker.
    lastSignature = "";
    pausedUntil = Date.now() + (result.retryIn || 60_000);
    return badge(`CRM: ${result.error}`, true);
  }
  pausedUntil = 0;
  badge(
    result.created
      ? `CRM: отслеживается · новых сообщений ${result.created}`
      : "CRM: отслеживается",
  );
}

// Мессенджеры меняют страницу постоянно (статус «в сети», «печатает…»),
// поэтому проверяем не чаще раза в SYNC_DELAY, а не откладываем бесконечно.
new MutationObserver(() => {
  if (timer !== undefined) return;
  timer = window.setTimeout(() => {
    timer = undefined;
    void syncIfChanged();
  }, SYNC_DELAY);
}).observe(document.body, {
  childList: true,
  subtree: true,
  characterData: true,
});

chrome.runtime.onMessage.addListener(
  (request: { type: string }, _sender, respond) => {
    if (request?.type === "rehub:read") {
      try {
        respond({ ok: true, result: readerFor(location).read(document) });
      } catch (error) {
        respond({
          ok: false,
          error:
            error instanceof Error
              ? error.message
              : "Не удалось прочитать диалог.",
        });
      }
    }
    if (request?.type === "rehub:resync") {
      lastSignature = "";
      pausedUntil = 0;
      void syncIfChanged();
      respond({ ok: true });
    }
  },
);
