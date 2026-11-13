"use client";
import { formatDateTime } from "@/lib/format";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert } from "@/components/ui/feedback";

type Conversation = {
  id: string;
  source_label: string;
  title: string;
  message_count: number;
  messages: {
    id: string;
    direction: "in" | "out";
    author: string;
    sent_at: string | null;
    text: string;
    has_attachment: boolean;
  }[];
  imports: { created_at: string; created: number; note: string; by: string }[];
};

/** Импортированная переписка: только выбранные и переданные сотрудником фрагменты. */
export function LeadConversations({ path }: { path: string }) {
  const { data, error } = useResource<{ items: Conversation[] }>(path);
  if (error) return <ErrorAlert message={error} />;
  if (!data?.items.length) return null;
  return (
    <article className="card sales-section">
      <h3>Переписка</h3>
      {data.items.map((conversation) => (
        <details key={conversation.id} className="conversation" open>
          <summary>
            {conversation.source_label} · {conversation.title} ·{" "}
            {conversation.message_count} сообщ.
          </summary>
          <p className="card-intro">
            Передано из браузера: CRM хранит только выбранные фрагменты.
            {conversation.imports[0]?.note &&
              ` Последний импорт: ${conversation.imports[0].note}.`}
          </p>
          <div className="chat">
            {conversation.messages.map((m) => (
              <div key={m.id} className={`chat-message chat-${m.direction}`}>
                <span className="small muted">
                  {m.author ||
                    (m.direction === "out" ? "Компания" : "Собеседник")}
                  {m.sent_at && ` · ${formatDateTime(m.sent_at)}`}
                </span>
                <p>{m.text || (m.has_attachment ? "Вложение" : "")}</p>
                {m.has_attachment && m.text && (
                  <span className="small muted">
                    Есть вложение (не передано)
                  </span>
                )}
              </div>
            ))}
          </div>
        </details>
      ))}
    </article>
  );
}
