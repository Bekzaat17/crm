import type { Bucket } from "./types";

const day = new Intl.DateTimeFormat("ru", { day: "numeric", month: "short" });
const month = new Intl.DateTimeFormat("ru", { month: "short" });
const monthLong = new Intl.DateTimeFormat("ru", {
  month: "long",
  year: "numeric",
});

/** Дата ГГГГ-ММ-ДД без сдвига часового пояса. */
export const parseDay = (value: string) => {
  const [y, m, d] = value.split("-").map(Number);
  return new Date(y, m - 1, d);
};

export const toDay = (date: Date) => date.toLocaleDateString("en-CA");

export function bucketLabel(start: string, bucket: Bucket, long = false) {
  const date = parseDay(start);
  if (bucket === "month") return (long ? monthLong : month).format(date);
  if (bucket === "week") return `${long ? "Неделя с " : ""}${day.format(date)}`;
  return day.format(date);
}

export const percent = (value: number | null) =>
  value === null
    ? "—"
    : `${(Math.round(value * 1000) / 10).toLocaleString("ru")}%`;

export const number = (value: number) => value.toLocaleString("ru");
