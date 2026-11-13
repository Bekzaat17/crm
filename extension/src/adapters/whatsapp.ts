import {
  ReadError,
  type ConversationReader,
  type ImportMessage,
} from "../types.js";
import { parseStamp } from "./time.js";

/**
 * WhatsApp Web. Сообщения имеют data-id вида "true_<чат>_<id>":
 * префикс — направление, вторая часть — идентификатор чата.
 * Прототип: структура страницы может измениться.
 */
export const whatsappReader: ConversationReader = {
  source: "whatsapp",
  matches: (location) => location.hostname === "web.whatsapp.com",
  read(document) {
    const main = document.querySelector("#main");
    if (!main) throw new ReadError("Откройте диалог в WhatsApp Web.");
    const title =
      main.querySelector("header span[title]")?.getAttribute("title") ||
      main.querySelector("header")?.textContent?.trim() ||
      "Диалог WhatsApp";
    const rows = Array.from(
      main.querySelectorAll<HTMLElement>("[data-id]"),
    ).filter((row) => /^(true|false)_[^_]+_.+/.test(row.dataset.id || ""));
    if (!rows.length)
      throw new ReadError("В диалоге нет загруженных сообщений.");
    const chatId = rows[0].dataset.id!.split("_")[1];
    let withoutTime = 0;
    const messages: ImportMessage[] = rows.map((row) => {
      const id = row.dataset.id!;
      const meta =
        row
          .querySelector("[data-pre-plain-text]")
          ?.getAttribute("data-pre-plain-text") || "";
      const author = meta.replace(/^\[[^\]]*\]\s*/, "").replace(/:\s*$/, "");
      const sentAt = meta ? parseStamp(meta) : null;
      if (!sentAt) withoutTime += 1;
      const text = Array.from(
        row.querySelectorAll<HTMLElement>("span.selectable-text"),
      )
        .map((span) => span.innerText)
        .join("\n")
        .trim();
      return {
        external_id: id,
        direction: id.startsWith("true_") ? "out" : "in",
        author,
        sent_at: sentAt,
        text,
        has_attachment: Boolean(
          row.querySelector(
            "img[src^='blob:'], audio, video, [data-icon*='download']",
          ),
        ),
      };
    });
    const warnings = [];
    if (withoutTime)
      warnings.push(
        `Без времени отправки: ${withoutTime} (например, вложения).`,
      );
    warnings.push(
      "Передаются только сообщения, загруженные на странице. Прокрутите диалог вверх, чтобы загрузить более ранние.",
    );
    return {
      source: "whatsapp",
      conversation: { external_id: chatId, title },
      messages,
      note: `WhatsApp Web: загружено на странице ${messages.length} сообщ.`,
      warnings,
    };
  },
};
