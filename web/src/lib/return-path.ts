/** Страница, на которую вернуть пользователя после входа (только этот сайт). */
const KEY = "crm-return-path";
const safe = (path: string | null) =>
  path && path.startsWith("/") && !path.startsWith("//") ? path : "/";

export function rememberReturnPath(path: string) {
  try {
    sessionStorage.setItem(KEY, safe(path));
  } catch {
    /* хранилище может быть недоступно */
  }
}

export function takeReturnPath() {
  try {
    const path = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return safe(path);
  } catch {
    return "/";
  }
}
