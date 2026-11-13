"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError, errorMessage } from "./api";
import { useInterval } from "./use-interval";

type Options = {
  /** Автообновление, мс. */
  refreshMs?: number;
  /** Приостановить автообновление, например на время редактирования. */
  paused?: boolean;
};

/** Загрузка одного ресурса API с отменой устаревших ответов и обновлением. */
export function useResource<T>(path: string | null, options: Options = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState(0);
  const [loading, setLoading] = useState(Boolean(path));
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!path) return;
    let active = true;
    setLoading(true);
    api<T>(path)
      .then((result) => {
        if (!active) return;
        setData(result);
        setError("");
        setStatus(0);
      })
      .catch((cause) => {
        if (!active) return;
        setError(errorMessage(cause));
        setStatus(cause instanceof ApiError ? cause.status : 0);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, revision]);
  const reload = useCallback(() => setRevision((value) => value + 1), []);
  useInterval(
    reload,
    options.refreshMs && !options.paused ? options.refreshMs : null,
  );
  return { data, setData, error, status, loading, reload };
}
