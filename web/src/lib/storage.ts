/** Последняя открытая компания — удобство одного браузера, без гарантий. */
const KEY = "crm-company";

export function rememberCompany(id: string) {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* хранилище может быть недоступно */
  }
}

export function lastCompany() {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}
