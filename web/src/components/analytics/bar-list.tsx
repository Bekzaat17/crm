import { number } from "./format";

export type BarRow = { key: string; label: string; value: number };

/** Горизонтальные столбцы с подписями значений. */
export function BarList({
  rows,
  label,
  color,
  empty,
}: {
  rows: BarRow[];
  label: string;
  color: string;
  empty: string;
}) {
  const max = Math.max(0, ...rows.map((row) => row.value));
  if (!max) return <p className="chart-empty muted">{empty}</p>;
  return (
    <ul className="bar-list" aria-label={label}>
      {rows.map((row) => (
        <li key={row.key}>
          <span className="bar-label" title={row.label}>
            {row.label}
          </span>
          <span className="bar-track">
            <span
              className="bar-fill"
              style={{
                width: `${(row.value / max) * 100}%`,
                background: color,
              }}
            />
          </span>
          <strong className="bar-value">{number(row.value)}</strong>
        </li>
      ))}
    </ul>
  );
}
