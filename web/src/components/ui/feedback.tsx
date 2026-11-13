"use client";
import { Check, X } from "lucide-react";

export function ErrorAlert({
  message,
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  if (!message) return null;
  return (
    <div className="alert error" role="alert">
      {message}
      {onRetry && (
        <button className="text-button" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

export function Notice({
  message,
  onClose,
}: {
  message: string;
  onClose: () => void;
}) {
  if (!message) return null;
  return (
    <div className="alert success" role="status">
      <Check size={17} />
      {message}
      <button
        className="icon-button"
        aria-label="Закрыть уведомление"
        onClick={onClose}
      >
        <X size={16} />
      </button>
    </div>
  );
}

export function LoadingState({
  text = "Загружаем данные…",
}: {
  text?: string;
}) {
  return (
    <div className="loading-state" role="status">
      {text}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  text,
  children,
}: {
  icon?: React.ReactNode;
  title: string;
  text?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="empty-state compact">
      {icon}
      <h3>{title}</h3>
      {text && <p>{text}</p>}
      {children}
    </div>
  );
}

export function LoadMore({
  visible,
  loading,
  onClick,
  label = "Загрузить ещё",
}: {
  visible: boolean;
  loading: boolean;
  onClick: () => void;
  label?: string;
}) {
  if (!visible) return null;
  return (
    <button
      className="button secondary load-more"
      disabled={loading}
      onClick={onClick}
    >
      {loading ? "Загружаем…" : label}
    </button>
  );
}
