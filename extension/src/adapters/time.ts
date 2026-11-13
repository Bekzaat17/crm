/** "[10:15, 13.11.2026]" или "[10:15 AM, 11/13/2026]" → ISO с часовым поясом браузера. */
export function parseStamp(stamp: string): string | null {
  const match = stamp.match(
    /\[(\d{1,2}):(\d{2})(?:\s*([AP]M))?,\s*(\d{1,2})[./](\d{1,2})[./](\d{2,4})\]/i,
  );
  if (!match) return null;
  let hours = Number(match[1]);
  const minutes = Number(match[2]);
  const meridiem = match[3]?.toUpperCase();
  if (meridiem === "PM" && hours < 12) hours += 12;
  if (meridiem === "AM" && hours === 12) hours = 0;
  const first = Number(match[4]);
  const second = Number(match[5]);
  let year = Number(match[6]);
  if (year < 100) year += 2000;
  // Точка — день.месяц (ru); косая черта с AM/PM — месяц/день (en-US).
  const [day, month] =
    stamp.includes("/") && meridiem ? [second, first] : [first, second];
  const date = new Date(year, month - 1, day, hours, minutes);
  return Number.isNaN(date.getTime()) ? null : toOffsetIso(date);
}

export function toOffsetIso(date: Date): string {
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.trunc(Math.abs(n))).padStart(2, "0");
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:00` +
    `${sign}${pad(offset / 60)}:${pad(offset % 60)}`
  );
}
