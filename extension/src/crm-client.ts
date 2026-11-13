import type { ReadResult, Source } from "./types.js";
import type { Settings } from "./settings.js";

export type LeadOption = {
  id: string;
  title: string;
  client_name: string;
  stage: string;
};
export type ChatStatus = {
  tracked: boolean;
  lead?: { id: string; title: string; client_name: string };
  message_count?: number;
};
export type ImportResult = {
  created: number;
  duplicates: number;
  lead_id: string;
};
export type ChatRef = { source: Source; external_id: string };

export class CrmError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Запросы к API расширения: только ключ, без cookie браузера. */
export class CrmClient {
  constructor(private settings: Settings) {}

  private async call<T>(path: string, body?: unknown): Promise<T> {
    let response: Response;
    try {
      response = await fetch(`${this.settings.crmUrl}/api/ext/${path}`, {
        method: body === undefined ? "GET" : "POST",
        credentials: "omit",
        headers: {
          Authorization: `Bearer ${this.settings.key}`,
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new CrmError("CRM недоступна. Проверьте подключение.", 0);
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok)
      throw new CrmError(
        data.error || "CRM отклонила запрос.",
        response.status,
      );
    return data as T;
  }

  session() {
    return this.call<{ company: string; user: string }>("session/");
  }

  leads(query: string) {
    return this.call<{ items: LeadOption[] }>(
      `leads/?q=${encodeURIComponent(query)}`,
    );
  }

  match(phone: string) {
    return this.call<{ items: LeadOption[] }>(
      `match/?phone=${encodeURIComponent(phone)}`,
    );
  }

  status(chat: ChatRef) {
    return this.call<ChatStatus>(
      `conversations/lookup/?${new URLSearchParams(chat)}`,
    );
  }

  track(chat: ChatRef, title: string, leadId: string) {
    return this.call<ChatStatus>("conversations/track/", {
      ...chat,
      title,
      lead_id: leadId,
    });
  }

  untrack(chat: ChatRef) {
    return this.call<ChatStatus>("conversations/untrack/", chat);
  }

  importFragment(read: ReadResult, leadId: string, key: string) {
    return this.call<ImportResult>("imports/", {
      idempotency_key: key,
      source: read.source,
      lead_id: leadId,
      conversation: read.conversation,
      messages: read.messages.slice(-500),
      history_note: read.note,
    });
  }
}

/** Детерминированный ключ повтора: тот же фрагмент даёт тот же ключ,
 *  поэтому повтор после потери ответа не создаёт дублей. */
export async function fragmentKey(read: ReadResult) {
  const material = JSON.stringify([
    read.source,
    read.conversation.external_id,
    read.messages.map(
      (m) => m.external_id || `${m.direction}|${m.sent_at}|${m.text}`,
    ),
  ]);
  const hash = new Uint8Array(
    await crypto.subtle.digest("SHA-256", new TextEncoder().encode(material)),
  );
  const hex = Array.from(hash.slice(0, 16), (b) =>
    b.toString(16).padStart(2, "0"),
  ).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** Номер собеседника WhatsApp из идентификатора чата 77001234567@c.us. */
export function chatPhone(read: ReadResult) {
  const match = read.conversation.external_id.match(/^(\d{6,15})@c\.us$/);
  return read.source === "whatsapp" && match ? match[1] : "";
}
