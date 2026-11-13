import { rememberReturnPath } from "./return-path";

export type Company = {
  id: string;
  name: string;
  role: string;
  role_label: string;
};
export type User = {
  id: string;
  name: string;
  email: string;
  is_platform_admin: boolean;
};
export type Session = {
  user: User | null;
  organizations: Company[];
  csrf_token: string;
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

let csrfToken = "";

/** Запросы, для которых 401 — ожидаемый ответ, а не истёкшая сессия. */
const PUBLIC = ["auth/", "invitations/"];

/** Сессия истекла посреди работы: вернуть пользователя сюда после входа. */
function redirectToLogin() {
  if (typeof window === "undefined" || window.location.pathname === "/login")
    return;
  rememberReturnPath(window.location.pathname + window.location.search);
  window.location.assign("/login");
}

export async function api<T>(
  path: string,
  data?: Record<string, unknown>,
): Promise<T> {
  const method = data === undefined ? "GET" : "POST";
  if (method === "POST" && !csrfToken) await api<Session>("auth/session");
  let response: Response;
  try {
    const [pathname, query] = path.split("?");
    response = await fetch(`/api/${pathname}/${query ? `?${query}` : ""}`, {
      method,
      credentials: "same-origin",
      cache: "no-store",
      headers:
        data === undefined
          ? {}
          : { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
      body: data === undefined ? undefined : JSON.stringify(data),
    });
  } catch {
    throw new ApiError(
      "Сервер недоступен. Проверьте подключение и попробуйте ещё раз.",
      0,
    );
  }
  const result = await response
    .json()
    .catch(() => ({ error: "Сервис временно недоступен. Попробуйте позже." }));
  if (result.csrf_token) csrfToken = result.csrf_token;
  if (response.status === 401 && !PUBLIC.some((p) => path.startsWith(p)))
    redirectToLogin();
  if (!response.ok)
    throw new ApiError(
      result.error || "Не удалось выполнить действие.",
      response.status,
    );
  return result as T;
}

export function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Не удалось выполнить действие.";
}
