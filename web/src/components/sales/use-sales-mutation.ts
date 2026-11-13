"use client";
import { useState } from "react";
import { errorMessage } from "@/lib/api";

/** Общая обработка состояния форм без зависимости от конкретной операции. */
export function useSalesMutation(onSaved: () => void) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function run(operation: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await operation();
      onSaved();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, run };
}
