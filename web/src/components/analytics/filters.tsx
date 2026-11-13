"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toDay } from "./format";

export const PERIODS = [
  { value: "7", label: "Неделя", days: 7 },
  { value: "30", label: "Месяц", days: 30 },
  { value: "90", label: "3 месяца", days: 90 },
  { value: "365", label: "Год", days: 365 },
] as const;

/** Период и сотрудник хранятся в адресе: ссылку на отчёт можно переслать. */
export function useAnalyticsFilters() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const period =
    PERIODS.find((p) => p.value === params.get("period")) || PERIODS[1];
  const assignee = params.get("assignee") || "";

  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`${pathname}?${next}`, { scroll: false });
  };

  const today = new Date();
  const from = new Date(today);
  from.setDate(from.getDate() - period.days + 1);
  const query = new URLSearchParams({
    from: toDay(from),
    to: toDay(today),
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });
  if (assignee) query.set("assignee", assignee);
  return { period: period.value, assignee, set, query };
}

export function AnalyticsFilters({
  filters,
  assignees,
}: {
  filters: ReturnType<typeof useAnalyticsFilters>;
  assignees: { id: string; name: string }[];
}) {
  return (
    <div className="analytics-filters">
      <div className="segmented" role="group" aria-label="Период">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            type="button"
            aria-pressed={filters.period === p.value}
            onClick={() => filters.set("period", p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>
      {assignees.length > 1 && (
        <select
          aria-label="Сотрудник"
          value={filters.assignee}
          onChange={(e) => filters.set("assignee", e.target.value)}
        >
          <option value="">Все сотрудники</option>
          {assignees.map((m) => (
            <option key={m.id} value={m.id}>
              {m.name}
            </option>
          ))}
        </select>
      )}
    </div>
  );
}
