export type Outcome = {
  created: number;
  open: number;
  admitted: number;
  refused: number;
  conversion: number | null;
  median_days_to_admission: number | null;
};

export type Bucket = "day" | "week" | "month";

export type SeriesPoint = {
  start: string;
  created: number;
  admitted: number;
  refused: number;
};

export type FunnelStep = {
  id: string;
  name: string;
  kind: "open" | "admitted";
  count: number;
};

export type TeamRow = Outcome & {
  id: string;
  name: string;
  is_active: boolean;
  overdue_tasks: number;
};

export type Report = {
  period: { from: string; to: string; bucket: Bucket };
  scope: "company" | "own";
  filters: {
    branches: { id: string; name: string; is_active: boolean }[];
    assignees: { id: string; name: string }[];
  };
  totals: Outcome;
  previous: Pick<Outcome, "created" | "admitted" | "refused" | "conversion">;
  funnel: FunnelStep[];
  series: SeriesPoint[];
  sources: {
    name: string;
    created: number;
    admitted: number;
    conversion: number | null;
  }[];
  refusal_reasons: { reason: string; count: number }[];
  team: TeamRow[] | null;
};

/** Серии динамики: цвет закреплён за сущностью и не зависит от фильтров. */
export const SERIES = [
  { key: "created", label: "Новые обращения", color: "var(--series-created)" },
  { key: "admitted", label: "Поступили", color: "var(--series-admitted)" },
  { key: "refused", label: "Отказы", color: "var(--series-refused)" },
] as const;

export type SeriesKey = (typeof SERIES)[number]["key"];
