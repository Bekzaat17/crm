"use client";
import { useCallback, useState } from "react";
import { errorMessage } from "./api";

/** Состояние выполнения операции: занятость и текст ошибки. */
export function useMutation(onDone?: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const run = useCallback(
    async (operation: () => Promise<unknown>) => {
      setBusy(true);
      setError("");
      try {
        await operation();
        onDone?.();
        return true;
      } catch (cause) {
        setError(errorMessage(cause));
        return false;
      } finally {
        setBusy(false);
      }
    },
    [onDone],
  );
  return { busy, error, setError, run };
}
