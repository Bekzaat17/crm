/** Значения полей формы как объект для JSON-запроса. */
export const fields = (form: HTMLFormElement) =>
  Object.fromEntries(new FormData(form).entries());
