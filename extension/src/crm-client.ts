import type { ReadResult } from "./types.js";
import type { Settings } from "./settings.js";

export type LeadOption = {
  id: string;
  title: string;
  client_name: string;
  stage: string;
};
export type ImportResult = {
  created: number;
  duplicates: number;
  lead_id: string;
};

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
      throw new Error("CRM недоступна. Проверьте подключение и повторите.");
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.error || "CRM отклонила запрос.");
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
