"use client";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { toDay } from "./format";
import type { Report } from "./types";

export const PRESETS = [
  { value: "7", label: "7 дней" },
  { value: "30", label: "30 дней" },
  { value: "90", label: "90 дней" },
  { value: "month", label: "Этот месяц" },
  { value: "prev-month", label: "Прошлый месяц" },
  { value: "year", label: "12 месяцев" },
  { value: "custom", label: "Свой период" },
] as const;

/** Даты периода в часовом поясе браузера. */
function presetRange(preset: string): [string, string] {
  const today = new Date();
  const y = today.getFullYear();
  const m = today.getMonth();
  if (preset === "month") return [toDay(new Date(y, m, 1)), toDay(today)];
  if (preset === "prev-month")
    return [toDay(new Date(y, m - 1, 1)), toDay(new Date(y, m, 0))];
  if (preset === "year") return [toDay(new Date(y, m - 11, 1)), toDay(today)];
  const days = Number(preset) || 30;
  const from = new Date(today);
  from.setDate(from.getDate() - days + 1);
  return [toDay(from), toDay(today)];
}

export function useAnalyticsFilters() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const preset = params.get("period") || "30";
  const [defaultFrom, defaultTo] = presetRange(preset);
  const custom = preset === "custom";
  const from = (custom && params.get("from")) || defaultFrom;
  const to = (custom && params.get("to")) || defaultTo;
  const branch = params.get("branch") || "";
  const assignee = params.get("assignee") || "";

  const set = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    const suffix = next.toString();
    router.replace(suffix ? `${pathname}?${suffix}` : pathname, {
      scroll: false,
    });
  };

  const query = new URLSearchParams({
    from,
    to,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });
  if (branch) query.set("branch", branch);
  if (assignee) query.set("assignee", assignee);

  return { preset, from, to, branch, assignee, custom, set, query };
}

export function AnalyticsFilters({
  filters,
  options,
}: {
  filters: ReturnType<typeof useAnalyticsFilters>;
  options: Report["filters"] | undefined;
}) {
  const { preset, from, to, branch, assignee, custom, set } = filters;
  return (
    <div className="analytics-filters" role="group" aria-label="Фильтры отчёта">
      <label>
        Период
        <select
          value={preset}
          onChange={(e) =>
            set(
              e.target.value === "custom"
                ? { period: "custom", from, to }
                : { period: e.target.value, from: "", to: "" },
            )
          }
        >
          {PRESETS.map((p) => (
            <option key={p.value} value={p.value}>
              {p.label}
            </option>
          ))}
        </select>
      </label>
      {custom && (
        <>
          <label>
            С
            <input
              type="date"
              value={from}
              max={to}
              onChange={(e) => e.target.value && set({ from: e.target.value })}
            />
          </label>
          <label>
            По
            <input
              type="date"
              value={to}
              min={from}
              onChange={(e) => e.target.value && set({ to: e.target.value })}
            />
          </label>
        </>
      )}
      {options && options.branches.length > 1 && (
        <label>
          Филиал
          <select
            value={branch}
            onChange={(e) => set({ branch: e.target.value })}
          >
            <option value="">Все филиалы</option>
            {options.branches.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
                {b.is_active ? "" : " (архив)"}
              </option>
            ))}
          </select>
        </label>
      )}
      {options && options.assignees.length > 0 && (
        <label>
          Сотрудник
          <select
            value={assignee}
            onChange={(e) => set({ assignee: e.target.value })}
          >
            <option value="">Все сотрудники</option>
            {options.assignees.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}
