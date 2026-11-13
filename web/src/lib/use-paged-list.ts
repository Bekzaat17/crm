"use client";
import { useCallback, useEffect, useState } from "react";
import { api, errorMessage } from "./api";
import type { Page } from "./types";

/** Список с постраничной догрузкой. Смена фильтров начинает с первой страницы. */
export function usePagedList<T extends { id: string }>(
  path: string | null,
  query: Record<string, string> = {},
) {
  const key = `${path}?${new URLSearchParams(query)}`;
  const [cursor, setCursor] = useState({ key, page: 1, revision: 0 });
  const page = cursor.key === key ? cursor.page : 1;
  const revision = cursor.revision;
  const [items, setItems] = useState<T[]>([]);
  const [meta, setMeta] = useState<Omit<Page<T>, "items">>({
    total: 0,
    has_more: false,
  });
  const [loading, setLoading] = useState(Boolean(path));
  const [error, setError] = useState("");
  useEffect(() => {
    if (!path) return;
    let active = true;
    setLoading(true);
    const params = new URLSearchParams({ ...query, page: String(page) });
    api<Page<T>>(`${path}?${params}`)
      .then((result) => {
        if (!active) return;
        const { items: rows, ...rest } = result;
        setItems((old) =>
          page === 1
            ? rows
            : [...old, ...rows.filter((r) => !old.some((o) => o.id === r.id))],
        );
        setMeta(rest);
        setError("");
      })
      .catch((cause) => {
        if (active) setError(errorMessage(cause));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
    // query входит в key; отдельная зависимость вызвала бы лишние запросы.
  }, [key, page, revision]);
  const loadMore = useCallback(
    () => setCursor({ key, page: page + 1, revision }),
    [key, page, revision],
  );
  const reload = useCallback(
    () => setCursor((c) => ({ key, page: 1, revision: c.revision + 1 })),
    [key],
  );
  return {
    items,
    setItems,
    total: meta.total,
    hasMore: meta.has_more,
    counts: meta.counts || {},
    setCounts: (counts: Record<string, number>) =>
      setMeta((m) => ({ ...m, counts })),
    page,
    loading,
    error,
    loadMore,
    reload,
  };
}
