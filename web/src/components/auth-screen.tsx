"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import {
  ArrowRight,
  Check,
  Mail,
  ShieldCheck,
  Users,
  Building2,
  ArrowUpRight,
} from "lucide-react";
import { api, errorMessage, Session } from "@/lib/api";
import { Brand } from "./brand";

type Mode = "login" | "register" | "verify" | "invite" | "forgot" | "reset";
type Invitation = { company_name: string; email: string; role_label: string };
const headings = {
  login: ["С возвращением", "Войдите в рабочее пространство вашей команды."],
  register: [
    "Начнём с вашей компании",
    "Создайте пространство центра, затем пригласите сотрудников.",
  ],
  verify: [
    "Подтвердите почту",
    "Один шаг — и пространство вашей компании будет готово.",
  ],
  invite: [
    "Вас пригласили в команду",
    "Примите приглашение, чтобы начать совместную работу.",
  ],
  forgot: [
    "Восстановим доступ",
    "Отправим ссылку для смены пароля на вашу почту.",
  ],
  reset: ["Новый пароль", "Придумайте надёжный пароль для своего аккаунта."],
};

export function AuthScreen({ mode }: { mode: Mode }) {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState("");
  const [uid, setUid] = useState("");
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const fragment = new URLSearchParams(window.location.hash.slice(1));
        const secret =
          fragment.get("token") ||
          (mode === "invite"
            ? sessionStorage.getItem("crm-pending-invite") || ""
            : "");
        setToken(secret);
        setUid(fragment.get("uid") || "");
        const current = await api<Session>("auth/session");
        if (cancelled) return;
        setSession(current);
        if ((mode === "login" || mode === "register") && current.user) {
          router.replace("/");
          return;
        }
        if (mode === "invite" && secret) {
          const preview = await api<Invitation>("invitations/preview", {
            token: secret,
          });
          if (!cancelled) setInvitation(preview);
        }
        if (["invite", "verify", "reset"].includes(mode) && !secret)
          setError(
            "В ссылке отсутствует код. Откройте полную ссылку из письма.",
          );
      } catch (e) {
        if (!cancelled) setError(errorMessage(e));
      } finally {
        if (!cancelled) setReady(true);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [mode, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    const data = Object.fromEntries(
      new FormData(event.currentTarget).entries(),
    );
    try {
      if (mode === "register") {
        const result = await api<{ message: string }>("auth/register", data);
        setNotice(result.message);
      } else if (mode === "login") {
        await api<Session>("auth/login", data);
        const pending = sessionStorage.getItem("crm-pending-invite");
        router.replace(
          pending ? `/invite#token=${encodeURIComponent(pending)}` : "/",
        );
      } else if (mode === "verify") {
        await api<Session>("auth/verify", { token });
        router.replace("/");
      } else if (mode === "invite") {
        const result = await api<Session & { organization_id: string }>(
          "invitations/accept",
          { ...data, token },
        );
        sessionStorage.removeItem("crm-pending-invite");
        router.replace(`/c/${result.organization_id}`);
      } else if (mode === "forgot") {
        const result = await api<{ message: string }>("auth/forgot", data);
        setNotice(result.message);
      } else if (mode === "reset") {
        const result = await api<{ message: string }>("auth/reset", {
          ...data,
          token,
          uid,
        });
        setNotice(result.message);
      }
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function inviteLogin() {
    sessionStorage.setItem("crm-pending-invite", token);
    router.push("/login");
  }

  return (
    <main className="auth-shell">
      <aside className="auth-story">
        <Brand light />
        <div className="auth-story-content">
          <span className="eyebrow light">ЛЮДИ. КОМАНДА. ЗАБОТА.</span>
          <h1>
            Больше внимания
            <br />
            людям.
            <br />
            <span>Меньше рутины.</span>
          </h1>
          <p>
            Единое рабочее пространство для команды реабилитационного центра.
          </p>
          <div className="story-illustration" aria-hidden="true">
            <div className="story-orbit" />
            <div className="story-center">
              <Building2 size={38} />
            </div>
            <span className="orbit-node node-1">
              <Users size={23} />
            </span>
            <span className="orbit-node node-2">
              <ShieldCheck size={23} />
            </span>
            <span className="orbit-node node-3">
              <Check size={23} />
            </span>
          </div>
          <div className="story-bottom">
            <ShieldCheck size={19} />
            <span>Отдельное пространство для каждой компании</span>
          </div>
        </div>
        <span className="auth-copyright">
          RehubPro CRM · Создано для вашей команды
        </span>
      </aside>
      <section className="auth-main">
        <div className="auth-mobile-brand">
          <Brand />
        </div>
        <div className="auth-top-link">
          {mode === "register" ? (
            <>
              Уже есть аккаунт?{" "}
              <Link href="/login">
                Войти <ArrowUpRight size={15} />
              </Link>
            </>
          ) : (
            <>
              Первый раз здесь?{" "}
              <Link href="/register">
                Создать компанию <ArrowUpRight size={15} />
              </Link>
            </>
          )}
        </div>
        <div className="auth-card">
          <span className="eyebrow">ВАШЕ РАБОЧЕЕ ПРОСТРАНСТВО</span>
          <h2>{headings[mode][0]}</h2>
          <p className="muted auth-description">{headings[mode][1]}</p>
          {!ready ? (
            <div className="loading-state" role="status">
              Подготавливаем безопасный вход…
            </div>
          ) : (
            <>
              {error && (
                <div className="alert error" role="alert">
                  {error}
                </div>
              )}
              {notice ? (
                <div className="success-panel" role="status">
                  <span className="success-icon">
                    <Mail size={24} />
                  </span>
                  <h3>
                    {mode === "reset"
                      ? "Пароль обновлён"
                      : "Проверьте вашу почту"}
                  </h3>
                  <p>{notice}</p>
                  <Link href="/login" className="button secondary">
                    Перейти ко входу <ArrowRight size={16} />
                  </Link>
                </div>
              ) : (
                <>
                  {invitation && (
                    <div className="invitation-summary">
                      <Building2 size={24} />
                      <div>
                        <strong>{invitation.company_name}</strong>
                        <span>
                          {invitation.email} · {invitation.role_label}
                        </span>
                      </div>
                    </div>
                  )}
                  <form onSubmit={submit} className="auth-form">
                    {(mode === "register" ||
                      (mode === "invite" && !session?.user)) && (
                      <label>
                        Ваше имя
                        <input
                          name="name"
                          autoComplete="name"
                          required
                          maxLength={120}
                          placeholder="Как к вам обращаться"
                        />
                      </label>
                    )}
                    {mode === "register" && (
                      <label>
                        Название компании
                        <input
                          name="company_name"
                          autoComplete="organization"
                          required
                          maxLength={160}
                          placeholder="Например, центр «Новая жизнь»"
                        />
                      </label>
                    )}
                    {["login", "register", "forgot"].includes(mode) && (
                      <label>
                        Электронная почта
                        <input
                          name="email"
                          type="email"
                          autoComplete="email"
                          maxLength={254}
                          required
                          placeholder="you@company.kz"
                        />
                      </label>
                    )}
                    {(["login", "register", "reset"].includes(mode) ||
                      (mode === "invite" && !session?.user)) && (
                      <label>
                        Пароль
                        <input
                          name="password"
                          type="password"
                          autoComplete={
                            mode === "login"
                              ? "current-password"
                              : "new-password"
                          }
                          minLength={mode === "login" ? undefined : 10}
                          maxLength={128}
                          required
                          placeholder={
                            mode === "login"
                              ? "Введите пароль"
                              : "Не менее 10 символов"
                          }
                        />
                      </label>
                    )}
                    {mode === "login" && (
                      <Link href="/forgot" className="forgot-link">
                        Забыли пароль?
                      </Link>
                    )}
                    {mode === "verify" && (
                      <div className="verification-note">
                        <ShieldCheck size={28} />
                        <p>
                          Подтверждая почту, вы создадите компанию и станете её
                          владельцем.
                        </p>
                      </div>
                    )}
                    {mode === "invite" && session?.user && (
                      <p className="small muted">
                        Вы вошли как {session.user.email}.
                      </p>
                    )}
                    <button
                      className="button primary full"
                      disabled={
                        busy ||
                        (["verify", "reset", "invite"].includes(mode) &&
                          !token) ||
                        (mode === "invite" && !invitation)
                      }
                    >
                      {busy
                        ? "Подождите…"
                        : {
                            login: "Войти в пространство",
                            register: "Создать компанию",
                            verify: "Подтвердить и открыть компанию",
                            invite: "Присоединиться к команде",
                            forgot: "Отправить ссылку",
                            reset: "Сохранить пароль",
                          }[mode]}
                      {!busy && <ArrowRight size={17} />}
                    </button>
                  </form>
                  {mode === "invite" && !session?.user && (
                    <button
                      className="text-button invite-login"
                      onClick={inviteLogin}
                    >
                      У меня уже есть аккаунт — войти
                    </button>
                  )}
                  {mode === "invite" && session?.user && (
                    <button
                      className="text-button invite-login"
                      onClick={async () => {
                        try {
                          await api("auth/logout", {});
                          setSession(await api<Session>("auth/session"));
                        } catch (e) {
                          setError(errorMessage(e));
                        }
                      }}
                    >
                      Выйти и сменить аккаунт
                    </button>
                  )}
                  {mode === "register" && (
                    <p className="form-note">
                      <ShieldCheck size={14} /> Сначала подтвердим почту. Затем
                      вы сможете пригласить команду.
                    </p>
                  )}
                </>
              )}
            </>
          )}
        </div>
        <div className="auth-footer">
          RehubPro CRM <span>Пространство для совместной работы</span>
        </div>
      </section>
    </main>
  );
}
