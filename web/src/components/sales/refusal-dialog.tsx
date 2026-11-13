"use client";
import { useState } from "react";
import { Dialog } from "@/components/ui/dialog";

/** Причина отказа обязательна для этапа типа «Отказ». */
export function RefusalDialog({
  stageName,
  onConfirm,
  onClose,
}: {
  stageName: string;
  onConfirm: (reason: string) => void;
  onClose: () => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <Dialog title={`Перевести в «${stageName}»`} onClose={onClose}>
      <form
        className="auth-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (reason.trim()) onConfirm(reason.trim());
        }}
      >
        <label>
          Причина отказа
          <textarea
            autoFocus
            required
            maxLength={500}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </label>
        <button className="button primary">Сохранить</button>
      </form>
    </Dialog>
  );
}
