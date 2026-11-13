"use client";
import { useState } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";
import { BarList, funnelRows } from "./bar-list";
import { AnalyticsFilters, useAnalyticsFilters } from "./filters";
import { number, percent, rangeLabel } from "./format";
import { TrendChart, TrendTable } from "./trend-chart";
import { SERIES, type Report } from "./types";

function Delta({
  current,
  previous,
  points = false,
}: {
  current: number | null;
  previous: number | null;
  /** Сравнение долей: разница в процентных пунктах. */
  points?: boolean;
}) {
  if (current === null || previous === null)
    return <span className="kpi-delta muted">нет данных для сравнения</span>;
  const diff = points
    ? Math.round((current - previous) * 1000) / 10
    : current - previous;
  const Icon = diff > 0 ? ArrowUpRight : diff < 0 ? ArrowDownRight : Minus;
  const value = `${diff > 0 ? "+" : ""}${diff.toLocaleString("ru")}${points ? " п.п." : ""}`;
  return (
    <span className="kpi-delta">
      <Icon size={14} aria-hidden />
      {diff === 0 ? "без изменений" : value}
      <span className="muted"> к прошлому периоду</span>
    </span>
  );
}

function Kpis({ report }: { report: Report }) {
  const { totals, previous } = report;
  const refusedShare = totals.created ? totals.refused / totals.created : null;
  return (
    <div className="kpi-grid">
      <article className="card kpi">
        <span>Новые обращения</span>
        <strong>{number(totals.created)}</strong>
        <Delta current={totals.created} previous={previous.created} />
      </article>
      <article className="card kpi">
        <span>Поступили</span>
        <strong>{number(totals.admitted)}</strong>
        <span className="kpi-note">Конверсия {percent(totals.conversion)}</span>
        <Delta
          current={totals.conversion}
          previous={previous.conversion}
          points
        />
      </article>
      <article className="card kpi">
        <span>Отказы</span>
        <strong>{number(totals.refused)}</strong>
        <span className="kpi-note">
          {percent(refusedShare)} от новых · в работе {number(totals.open)}
        </span>
      </article>
      <article className="card kpi">
        <span>До поступления</span>
        <strong>
          {totals.median_days_to_admission === null
            ? "—"
            : `${totals.median_days_to_admission.toLocaleString("ru")} дн.`}
        </strong>
        <span className="kpi-note">Медиана от создания обращения</span>
      </article>
    </div>
  );
}

function Trend({ report }: { report: Report }) {
  const [table, setTable] = useState(false);
  return (
    <article className="card chart-card">
      <div className="section-title">
        <h2>Динамика</h2>
        <div className="segmented" role="group" aria-label="Вид">
          <button
            type="button"
            aria-pressed={!table}
            onClick={() => setTable(false)}
          >
            График
          </button>
          <button
            type="button"
            aria-pressed={table}
            onClick={() => setTable(true)}
          >
            Таблица
          </button>
        </div>
      </div>
      <p className="card-intro">
        События по дате: созданные обращения, переходы в «Поступил» и в «Отказ».
      </p>
      <ul className="chart-legend">
        {SERIES.map((s) => (
          <li key={s.key}>
            <i style={{ background: s.color }} aria-hidden />
            {s.label}
          </li>
        ))}
      </ul>
      {table ? (
        <TrendTable points={report.series} bucket={report.period.bucket} />
      ) : (
        <TrendChart points={report.series} bucket={report.period.bucket} />
      )}
    </article>
  );
}

function SourcesTable({ rows }: { rows: Report["sources"] }) {
  return (
    <article className="card table-card">
      <div className="section-title padded">
        <h2>Источники</h2>
      </div>
      {rows.length ? (
        <div className="table-scroll">
          <table className="analytics-table">
            <thead>
              <tr>
                <th>Источник</th>
                <th className="numeric">Обращения</th>
                <th className="numeric">Поступили</th>
                <th className="numeric">Конверсия</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.name}>
                  <td>{row.name}</td>
                  <td className="numeric">{number(row.created)}</td>
                  <td className="numeric">{number(row.admitted)}</td>
                  <td className="numeric">{percent(row.conversion)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="chart-empty muted">Нет обращений за период.</p>
      )}
    </article>
  );
}

function TeamTable({ rows }: { rows: NonNullable<Report["team"]> }) {
  return (
    <article className="card table-card">
      <div className="section-title padded">
        <h2>Сотрудники</h2>
      </div>
      <div className="table-scroll">
        <table className="analytics-table">
          <thead>
            <tr>
              <th>Сотрудник</th>
              <th className="numeric">Новые</th>
              <th className="numeric">В работе</th>
              <th className="numeric">Поступили</th>
              <th className="numeric">Отказы</th>
              <th className="numeric">Конверсия</th>
              <th className="numeric">Дней до поступления</th>
              <th className="numeric">Просрочено задач</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>
                  {row.name}
                  {!row.is_active && (
                    <span className="subtle-pill">отключён</span>
                  )}
                </td>
                <td className="numeric">{number(row.created)}</td>
                <td className="numeric">{number(row.open)}</td>
                <td className="numeric">{number(row.admitted)}</td>
                <td className="numeric">{number(row.refused)}</td>
                <td className="numeric">{percent(row.conversion)}</td>
                <td className="numeric">
                  {row.median_days_to_admission?.toLocaleString("ru") ?? "—"}
                </td>
                <td className="numeric">{number(row.overdue_tasks)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </article>
  );
}

export function AnalyticsPage() {
  const { root } = useCompany();
  const { item, eyebrow } = useSection();
  const filters = useAnalyticsFilters();
  const { data, error, loading, reload } = useResource<Report>(
    `${root}/analytics?${filters.query}`,
  );
  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "Аналитика"}
        description={item?.description}
      />
      <AnalyticsFilters filters={filters} options={data?.filters} />
      <ErrorAlert message={error} onRetry={reload} />
      {!data ? (
        loading && <LoadingState />
      ) : (
        <div className={`analytics ${loading ? "is-refreshing" : ""}`}>
          <p className="analytics-scope muted small">
            {rangeLabel(data.period.from, data.period.to)}
            {data.scope === "own"
              ? " · показаны только ваши обращения"
              : " · итоги по обращениям, созданным за период, по их текущему этапу"}
          </p>
          <Kpis report={data} />
          <Trend report={data} />
          <div className="analytics-grid">
            <article className="card chart-card">
              <div className="section-title">
                <h2>Воронка</h2>
              </div>
              <p className="card-intro">
                Сколько обращений дошло хотя бы до этапа. Процент — от первого
                этапа.
              </p>
              <BarList
                label="Воронка по этапам"
                rows={funnelRows(data.funnel)}
                empty="Нет обращений за период."
              />
            </article>
            <article className="card chart-card">
              <div className="section-title">
                <h2>Причины отказов</h2>
              </div>
              <p className="card-intro">
                Обращения периода, которые сейчас в отказе.
              </p>
              <BarList
                label="Причины отказов"
                rows={data.refusal_reasons.map((r) => ({
                  key: r.reason,
                  label: r.reason,
                  value: r.count,
                  color: "var(--series-refused)",
                }))}
                empty="Отказов за период нет."
              />
            </article>
          </div>
          <SourcesTable rows={data.sources} />
          {data.team && <TeamTable rows={data.team} />}
        </div>
      )}
    </>
  );
}
