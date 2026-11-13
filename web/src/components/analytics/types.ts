export type Bucket = "day" | "week" | "month";

export type Totals = {
  created: number;
  admitted: number;
  refused: number;
  conversion: number | null;
};

export type SeriesPoint = { start: string; created: number; admitted: number };

export type Report = {
  period: { from: string; to: string; bucket: Bucket };
  scope: "company" | "own";
  assignees: { id: string; name: string }[];
  totals: Totals;
  series: SeriesPoint[];
  sources: { name: string; created: number; admitted: number }[];
  refusal_reasons: { reason: string; count: number }[];
  team: (Totals & { id: string; name: string; overdue_tasks: number })[] | null;
};

/** Цвет закреплён за смыслом: обращения — синий, поступления — зелёный. */
export const SERIES = [
  { key: "created", label: "Обращения", color: "var(--series-created)" },
  { key: "admitted", label: "Поступили", color: "var(--series-admitted)" },
] as const;
