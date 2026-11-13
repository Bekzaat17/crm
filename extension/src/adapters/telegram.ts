import {
  ReadError,
  type ConversationReader,
  type ImportMessage,
} from "../types.js";
import { toOffsetIso } from "./time.js";

/** Текст сообщения без служебных элементов: время, реакции, статус прочтения. */
function messageText(element: Element | null) {
  if (!element) return "";
  const copy = element.cloneNode(true) as HTMLElement;
  copy
    .querySelectorAll(
      ".time, .Message-time, .MessageMeta, .reactions, .message-reactions, .tgico",
    )
    .forEach((node) => node.remove());
  return (copy.innerText ?? copy.textContent ?? "").trim();
}

function peerId(location: Location) {
  // web.telegram.org/k/#@username или #-100123…, /a/#123…
  const id = decodeURIComponent(location.hash.replace(/^#/, "")).split("?")[0];
  if (!id) throw new ReadError("Откройте диалог в Telegram Web.");
  return id;
}

/** Telegram Web K: пузыри .bubble[data-mid], data-timestamp в секундах. */
function readWebK(document: Document): ImportMessage[] {
  return Array.from(document.querySelectorAll<HTMLElement>(".bubble[data-mid]"))
    .filter((bubble) => !bubble.classList.contains("service"))
    .map((bubble) => {
      const timestamp = Number(bubble.dataset.timestamp);
      return {
        external_id: bubble.dataset.mid,
        direction: bubble.classList.contains("is-out") ? "out" : "in",
        author:
          bubble.querySelector(".peer-title, .name")?.textContent?.trim() || "",
        sent_at: timestamp ? toOffsetIso(new Date(timestamp * 1000)) : null,
        text: messageText(bubble.querySelector(".message")),
        has_attachment: Boolean(
          bubble.querySelector(
            ".media-photo, .media-video, audio, .document-container, .attachment",
          ),
        ),
      } satisfies ImportMessage;
    });
}

/** Telegram Web A: .Message[data-message-id], исходящие с классом own. */
function readWebA(document: Document): ImportMessage[] {
  return Array.from(
    document.querySelectorAll<HTMLElement>(".Message[data-message-id]"),
  ).map(
    (message) =>
      ({
        external_id: message.dataset.messageId,
        direction: message.classList.contains("own") ? "out" : "in",
        author:
          message
            .querySelector(".message-title-name, .sender-title")
            ?.textContent?.trim() || "",
        sent_at: null,
        text: messageText(message.querySelector(".text-content")),
        has_attachment: Boolean(
          message.querySelector(
            ".media-inner, .Audio, .File, video, img.full-media",
          ),
        ),
      }) satisfies ImportMessage,
  );
}

/**
 * Telegram Web (версии K и A). Идентификатор диалога — из адреса после «#»,
 * идентификаторы сообщений — из атрибутов страницы. Прототип.
 */
export const telegramReader: ConversationReader = {
  source: "telegram",
  matches: (location) => location.hostname === "web.telegram.org",
  read(document) {
    const location = document.location;
    const versionA = location.pathname.startsWith("/a");
    const messages = (
      versionA ? readWebA(document) : readWebK(document)
    ).filter((m) => m.text || m.has_attachment);
    if (!messages.length)
      throw new ReadError("В диалоге нет загруженных сообщений.");
    const title =
      document
        .querySelector(
          versionA
            ? ".ChatInfo .fullName, .ChatInfo h3"
            : ".chat-info .peer-title",
        )
        ?.textContent?.trim() || "Диалог Telegram";
    const warnings = [
      "Передаются только сообщения, загруженные на странице. Прокрутите диалог вверх, чтобы загрузить более ранние.",
    ];
    if (versionA)
      warnings.push(
        "В версии A время сообщений на странице не указано полностью: оно не передаётся.",
      );
    return {
      source: "telegram",
      conversation: { external_id: peerId(location), title },
      messages,
      note: `Telegram Web ${versionA ? "A" : "K"}: загружено на странице ${messages.length} сообщ.`,
      warnings,
    };
  },
};
