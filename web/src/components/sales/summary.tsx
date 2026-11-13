"use client";
import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";

type Summary = {
  clients: number;
  leads: number;
  active_leads: number;
  admitted: number;
  refused: number;
  open_tasks: number;
  overdue_tasks: number;
  contacts_due: number;
};
export function SalesSummary({
  companyId,
  onTasks,
}: {
  companyId: string;
  onTasks: () => void;
}) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const result = await api<Summary>(`organizations/${companyId}/summary`);
        if (active) {
          setSummary(result);
          setError("");
        }
      } catch (cause) {
        if (active) setError(errorMessage(cause));
      }
    }
    void load();
    const timer = setInterval(() => void load(), 60000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [companyId]);
  if (error)
    return (
      <div className="alert error" role="alert">
        Не удалось обновить сводку: {error}
      </div>
    );
  if (!summary) return <div className="loading-state">Обновляем сводку…</div>;
  const metrics = [
    ["Клиенты", summary.clients],
    ["Обращения в работе", summary.active_leads],
    ["Поступили", summary.admitted],
    ["Открытые задачи", summary.open_tasks],
  ];
  return (
    <>
      <div className="sales-metrics">
        {metrics.map(([label, value]) => (
          <article className="card" key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
      {(summary.overdue_tasks > 0 || summary.contacts_due > 0) && (
        <div className="reminder-banner" role="status">
          <div>
            <strong>Требуют внимания</strong>
            <p>
              Просроченные задачи: {summary.overdue_tasks}. Пора связаться по
              обращениям: {summary.contacts_due}.
            </p>
          </div>
          <button className="button secondary" onClick={onTasks}>
            Открыть задачи
          </button>
        </div>
      )}
    </>
  );
}
