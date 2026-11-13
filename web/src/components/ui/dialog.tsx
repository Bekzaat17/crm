"use client";
import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { ErrorAlert } from "./feedback";

/** Модальное окно на нативном <dialog>: фокус и Escape обрабатывает браузер. */
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
    const dialog = ref.current;
    dialog?.showModal();
    // Фокус в первое поле формы, а не на кнопку закрытия.
    dialog
      ?.querySelector<HTMLElement>(
        "input:not([type=hidden]):not([type=checkbox]), select, textarea",
      )
      ?.focus();
    return () => dialog?.close();
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
        <button className="icon-button" onClick={onClose} aria-label="Закрыть">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

/** Подтверждение необратимого или заметного действия. */
export function ConfirmDialog({
  title,
  text,
  confirmLabel,
  busy,
  error,
  danger,
  onConfirm,
  onClose,
  children,
}: {
  title: string;
  text: string;
  confirmLabel: string;
  busy: boolean;
  error?: string;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children?: React.ReactNode;
}) {
  return (
    <Dialog title={title} onClose={() => !busy && onClose()}>
      <p className="muted">{text}</p>
      <ErrorAlert message={error} />
      {children}
      <div className="modal-actions">
        <button className="button secondary" disabled={busy} onClick={onClose}>
          Отмена
        </button>
        <button
          className={`button ${danger ? "danger" : "primary"}`}
          disabled={busy}
          onClick={onConfirm}
        >
          {busy ? "Подождите…" : confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
