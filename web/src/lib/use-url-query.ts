"use client";
import { useEffect, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

/** Параметр URL с черновиком поля ввода: адрес обновляется после паузы ввода.
 *  Компонент, который вызывает хук, должен находиться внутри <Suspense>. */
export function useUrlQuery(name: string, delay = 250) {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const value = params.get(name) || "";
  const [draft, setDraft] = useState(value);
  const set = (next: string) => {
    const query = new URLSearchParams(params);
    if (next) query.set(name, next);
    else query.delete(name);
    const suffix = query.toString();
    router.replace(suffix ? `${pathname}?${suffix}` : pathname, {
      scroll: false,
    });
  };
  useEffect(() => {
    if (draft === value) return;
    const timer = setTimeout(() => set(draft), delay);
    return () => clearTimeout(timer);
    // set зависит от params и пути, которые уже отражены в value.
  }, [draft, value, delay]);
  return { value, draft, setDraft, set };
}
