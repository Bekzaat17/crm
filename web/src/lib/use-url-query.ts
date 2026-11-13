"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** Параметр URL с черновиком поля ввода: адрес обновляется после паузы ввода.
 *  Компонент, который вызывает хук, должен находиться внутри <Suspense>. */
export function useUrlQuery(name: string, delay = 250) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const value = params.get(name) || "";
  const [draft, setDraft] = useState(value);
  // Адрес изменился снаружи (Назад, ссылка в меню): черновик следует за ним.
  const [synced, setSynced] = useState(value);
  if (synced !== value) {
    setSynced(value);
    setDraft(value);
  }
  // Актуальные параметры на момент срабатывания таймера, а не на момент ввода.
  const latest = useRef({ params, pathname });
  useEffect(() => {
    latest.current = { params, pathname };
  }, [params, pathname]);

  const write = (next: string) => {
    const query = new URLSearchParams(latest.current.params);
    if (next) query.set(name, next);
    else query.delete(name);
    const suffix = query.toString();
    const path = latest.current.pathname;
    router.replace(suffix ? `${path}?${suffix}` : path, { scroll: false });
  };
  const set = (next: string) => {
    setDraft(next);
    setSynced(next);
    write(next);
  };
  useEffect(() => {
    if (draft === synced) return;
    const timer = setTimeout(() => {
      setSynced(draft);
      write(draft);
    }, delay);
    return () => clearTimeout(timer);
    // write читает актуальные параметры из ref.
  }, [draft, synced, delay]);
  return { value, draft, setDraft, set };
}
