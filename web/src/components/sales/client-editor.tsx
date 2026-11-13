"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { ClientRecord } from "./types";
import { Dialog, ClientFields, fields } from "./forms";
import { useSalesMutation } from "./use-sales-mutation";
export function ClientEditor({
  initial,
  root,
  onClose,
  onSaved,
  onNewLead,
  onOpenLead,
}: {
  initial: ClientRecord;
  root: string;
  onClose: () => void;
  onSaved: () => void;
  onNewLead: (c: ClientRecord) => void;
  onOpenLead: (id: string) => void;
}) {
  const [selectedClient, setSelectedClient] = useState(initial);
  const { busy, error: formError, run: mutation } = useSalesMutation(onSaved);
  const close = () => {
    if (!busy) onClose();
  };
  const openClient = async (id: string) =>
    setSelectedClient(await api<ClientRecord>(`${root}/clients/${id}`));
  const newLead = onNewLead;
  const openLead = onOpenLead;
  return (
    <Dialog title="Карточка клиента" onClose={close}>
      {formError && (
        <div className="alert error" role="alert">
          {formError}
        </div>
      )}
      <form
        key={selectedClient.version}
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          const data = fields(e.currentTarget);
          void mutation(async () =>
            setSelectedClient(
              await api<ClientRecord>(`${root}/clients/${selectedClient.id}`, {
                ...data,
                version: selectedClient.version,
              }),
            ),
          );
        }}
      >
        <ClientFields client={selectedClient} />
        <button className="button primary" disabled={busy}>
          Сохранить карточку
        </button>
      </form>
      <h3 className="sales-section">Родственники и контактные лица</h3>
      {selectedClient.contacts?.map((c) => (
        <div className="related-contact" key={c.id}>
          <strong>{c.name}</strong>
          <span>
            {c.relationship} · {c.phone || "Телефон не указан"}
          </span>
        </div>
      ))}
      <form
        className="auth-form related-form"
        onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget,
            data = fields(form);
          void mutation(async () => {
            await api(`${root}/clients/${selectedClient.id}/contacts`, data);
            form.reset();
            await openClient(selectedClient.id);
          });
        }}
      >
        <label>
          Имя контакта
          <input name="name" required maxLength={240} />
        </label>
        <div className="form-grid">
          <label>
            Кем приходится
            <input
              name="relationship"
              required
              maxLength={80}
              placeholder="Мать, брат…"
            />
          </label>
          <label>
            Телефон
            <input name="phone" type="tel" maxLength={40} />
          </label>
        </div>
        <button className="button secondary" disabled={busy}>
          Добавить контакт
        </button>
      </form>
      <div className="section-title sales-section">
        <h3>Обращения клиента</h3>
        <button className="text-button" onClick={() => newLead(selectedClient)}>
          Новое <Plus size={14} />
        </button>
      </div>
      {selectedClient.leads?.map((l) => (
        <button
          className="client-lead"
          key={l.id}
          onClick={() => {
            void openLead(l.id);
          }}
        >
          <strong>{l.title}</strong>
          <span>{l.stage_label}</span>
        </button>
      ))}
    </Dialog>
  );
}
