export type Source = "whatsapp" | "instagram" | "telegram";

export type ImportMessage = {
  external_id?: string;
  direction: "in" | "out";
  author: string;
  /** ISO-время с часовым поясом или null, если страница его не показывает. */
  sent_at: string | null;
  text: string;
  has_attachment: boolean;
};

export type ReadResult = {
  source: Source;
  conversation: { external_id: string; title: string };
  messages: ImportMessage[];
  /** Что именно удалось прочитать: попадает в историю импорта в CRM. */
  note: string;
  warnings: string[];
};

/** Адаптер страницы мессенджера (Strategy). Читает только открытый диалог. */
export interface ConversationReader {
  readonly source: Source;
  matches(location: Location): boolean;
  read(document: Document): ReadResult;
}

export class ReadError extends Error {}
