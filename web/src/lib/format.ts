// Время показывается в часовом поясе браузера — так же, как в полях ввода
// datetime-local, чтобы срок в списке и в форме совпадали.
const shortFormat = new Intl.DateTimeFormat("ru", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});
const fullFormat = new Intl.DateTimeFormat("ru", {
  dateStyle: "medium",
  timeStyle: "short",
});

/** Короткая дата и время: «13 нояб., 10:00». */
export const formatShort = (value: string) =>
  shortFormat.format(new Date(value));

/** Полная дата и время. */
export const formatDateTime = (value: string) =>
  fullFormat.format(new Date(value));

/** ISO-время сервера → значение поля datetime-local в часовом поясе браузера. */
export function toLocalInput(value: string) {
  if (!value) return "";
  const date = new Date(value);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}

/** Значение datetime-local → ISO с часовым поясом; пустое поле → "". */
export const fromLocalInput = (value: FormDataEntryValue | null | undefined) =>
  value ? new Date(String(value)).toISOString() : "";

/** Сегодняшняя дата для атрибута max у полей type="date". */
export const todayInput = () => new Date().toLocaleDateString("en-CA");

export const isPast = (value: string) => Date.parse(value) < Date.now();
