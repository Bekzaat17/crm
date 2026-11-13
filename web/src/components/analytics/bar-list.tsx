import { number, percent } from "./format";

export type BarRow = {
  key: string;
  label: string;
  value: number;
  color: string;
  /** Подпись справа от значения, например доля от первого шага. */
  note?: string;
};

/** Горизонтальные столбцы с подписями: длина — величина, цвет — сущность. */
export function BarList({
  rows,
  label,
  empty,
}: {
  rows: BarRow[];
  label: string;
  empty: string;
}) {
  const max = Math.max(0, ...rows.map((row) => row.value));
  if (!rows.length || max === 0)
    return <p className="chart-empty muted">{empty}</p>;
  return (
    <ul className="bar-list" aria-label={label}>
      {rows.map((row) => (
        <li key={row.key} title={`${row.label}: ${number(row.value)}`}>
          <span className="bar-label">{row.label}</span>
          <span className="bar-track">
            <span
              className="bar-fill"
              style={{
                width: `${(row.value / max) * 100}%`,
                background: row.color,
              }}
            />
          </span>
          <span className="bar-value">
            <strong>{number(row.value)}</strong>
            {row.note && <span className="muted"> {row.note}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function funnelRows(
  steps: { id: string; name: string; kind: string; count: number }[],
): BarRow[] {
  const first = steps[0]?.count || 0;
  return steps.map((step, index) => ({
    key: step.id,
    label: step.name,
    value: step.count,
    color:
      step.kind === "admitted"
        ? "var(--series-admitted)"
        : "var(--series-created)",
    note: index && first ? percent(step.count / first) : undefined,
  }));
}
