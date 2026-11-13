"use client";
import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import type { Contact } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { ConfirmDialog } from "@/components/ui/dialog";
import { ErrorAlert } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";

export function ContactFields({ contact }: { contact?: Contact }) {
  return (
    <>
      <label>
        Имя контакта
        <input
          name="name"
          required
          maxLength={240}
          defaultValue={contact?.name}
        />
      </label>
      <div className="form-grid">
        <label>
          Кем приходится
          <input
            name="relationship"
            required
            maxLength={80}
            placeholder="Мать, брат…"
            defaultValue={contact?.relationship}
          />
        </label>
        <label>
          Телефон
          <input
            name="phone"
            type="tel"
            maxLength={40}
            defaultValue={contact?.phone}
          />
        </label>
      </div>
    </>
  );
}

/** Контактное лицо: просмотр, правка с проверкой версии и удаление. */
export function ContactRow({
  path,
  contact,
  onChanged,
}: {
  path: string;
  contact: Contact;
  onChanged: () => void;
}) {
  const [mode, setMode] = useState<"view" | "edit" | "delete">("view");
  const { busy, error, run } = useMutation(() => {
    setMode("view");
    onChanged();
  });
  if (mode === "edit")
    return (
      <form
        className="auth-form related-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void run(() => api(path, { ...data, version: contact.version }));
        }}
      >
        <ErrorAlert message={error} />
        <ContactFields contact={contact} />
        <div className="task-actions">
          <button className="button primary" disabled={busy}>
            Сохранить
          </button>
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => setMode("view")}
          >
            Отмена
          </button>
        </div>
      </form>
    );
  return (
    <div className="related-contact">
      <div>
        <strong>{contact.name}</strong>
        <span>
          {contact.relationship} · {contact.phone || "Телефон не указан"}
        </span>
      </div>
      <div className="row-actions">
        <button
          className="icon-button"
          aria-label={`Изменить контакт ${contact.name}`}
          onClick={() => setMode("edit")}
        >
          <Pencil size={15} />
        </button>
        <button
          className="icon-button"
          aria-label={`Удалить контакт ${contact.name}`}
          onClick={() => setMode("delete")}
        >
          <Trash2 size={15} />
        </button>
      </div>
      {mode === "delete" && (
        <ConfirmDialog
          title="Удалить контактное лицо?"
          text={`${contact.name} будет удалён из карточки. Уже подтверждённые передачи в RehubPro не изменятся.`}
          confirmLabel="Удалить"
          danger
          busy={busy}
          error={error}
          onClose={() => setMode("view")}
          onConfirm={() => void run(() => api(`${path}/delete`, {}))}
        />
      )}
    </div>
  );
}
