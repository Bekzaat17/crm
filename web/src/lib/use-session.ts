"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import type { Session } from "./api";
import { rememberReturnPath } from "./return-path";
import { useResource } from "./use-resource";

/** Текущая сессия; без входа — переход на /login с возвратом сюда. */
export function useSession() {
  const router = useRouter();
  const session = useResource<Session>("auth/session");
  useEffect(() => {
    if (session.data && !session.data.user) {
      rememberReturnPath(window.location.pathname + window.location.search);
      router.replace("/login");
    }
  }, [session.data, router]);
  return session;
}
