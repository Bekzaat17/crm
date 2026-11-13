import {
  ReadError,
  type ConversationReader,
  type ImportMessage,
} from "../types.js";

/**
 * Instagram Direct. Идентификатор диалога — из адреса /direct/t/<id>/.
 * Сообщения не имеют стабильных идентификаторов на странице, направление
 * определяется по выравниванию. Прототип: проверить на тестовом аккаунте.
 */
export const instagramReader: ConversationReader = {
  source: "instagram",
  matches: (location) =>
    location.hostname === "www.instagram.com" &&
    location.pathname.startsWith("/direct/t/"),
  read(document) {
    const threadId = document.location.pathname.split("/")[3];
    if (!threadId) throw new ReadError("Откройте диалог в Instagram Direct.");
    const grid =
      document.querySelector<HTMLElement>("[role='grid']") || document.body;
    const middle = grid.getBoundingClientRect().left + grid.clientWidth / 2;
    const rows = Array.from(grid.querySelectorAll<HTMLElement>("[role='row']"));
    const messages: ImportMessage[] = rows
      .map((row) => {
        const text = row.innerText.trim();
        const bubble = row.querySelector<HTMLElement>("div[dir='auto']") || row;
        const rect = bubble.getBoundingClientRect();
        return {
          direction: rect.left + rect.width / 2 > middle ? "out" : "in",
          author: "",
          sent_at: null,
          text,
          has_attachment: Boolean(row.querySelector("img, video, audio")),
        } satisfies ImportMessage;
      })
      .filter((m) => m.text || m.has_attachment);
    if (!messages.length)
      throw new ReadError("В диалоге нет загруженных сообщений.");
    const title =
      document.querySelector("header h1, header h2")?.textContent?.trim() ||
      document.title.replace(/\s*•.*$/, "") ||
      "Диалог Instagram";
    return {
      source: "instagram",
      conversation: { external_id: threadId, title },
      messages,
      note: `Instagram: загружено на странице ${messages.length} сообщ., без времени отправки`,
      warnings: [
        "Instagram не показывает время и идентификаторы каждого сообщения: повторная передача того же фрагмента не создаст дублей, но изменённый фрагмент может.",
        "Направление сообщения определено по расположению на экране. Проверьте предпросмотр.",
      ],
    };
  },
};
