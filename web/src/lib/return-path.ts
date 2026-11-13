/** Страница, на которую вернуть пользователя после входа (только этот сайт). */
const KEY = "crm-return-path";

/** Путь того же сайта; «//host» и «/\\host» браузер считает другим адресом. */
function safe(path: string | null) {
  if (!path || typeof window === "undefined") return "/";
  try {
    const url = new URL(path, window.location.origin);
    return url.origin === window.location.origin
      ? url.pathname + url.search
      : "/";
  } catch {
    return "/";
  }
}

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
