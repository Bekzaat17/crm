"use client";
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import type { ClientRecord } from "./types";
export const fields = (form: HTMLFormElement) =>
  Object.fromEntries(new FormData(form).entries());
export function Dialog({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog
      ref={ref}
      className="sales-dialog"
      aria-label={title}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      <div className="sales-dialog-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          onClick={onClose}
          aria-label="Закрыть карточку"
        >
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function ClientFields({ client }: { client?: ClientRecord }) {
  return (
    <>
      <label>
        ФИО клиента
        <input
          name="name"
          required
          maxLength={240}
          defaultValue={client?.name}
        />
      </label>
      <div className="form-grid">
        <label>
          Телефон
          <input
            name="phone"
            type="tel"
            maxLength={40}
            defaultValue={client?.phone}
          />
        </label>
        <label>
          Город
          <input name="city" maxLength={120} defaultValue={client?.city} />
        </label>
      </div>
      <label>
        Дата рождения
        <input
          name="date_of_birth"
          type="date"
          max={new Date().toLocaleDateString("en-CA")}
          defaultValue={client?.date_of_birth}
        />
      </label>
      <label>
        Заметки
        <textarea
          name="notes"
          maxLength={5000}
          rows={3}
          defaultValue={client?.notes}
        />
      </label>
    </>
  );
}
