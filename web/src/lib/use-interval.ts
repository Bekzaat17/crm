"use client";
import { useEffect, useRef } from "react";

/** Таймер с актуальным обработчиком; delay=null останавливает его. */
export function useInterval(callback: () => void, delay: number | null) {
  const saved = useRef(callback);
  useEffect(() => {
    saved.current = callback;
  }, [callback]);
  useEffect(() => {
    if (delay === null) return;
    const timer = setInterval(() => saved.current(), delay);
    return () => clearInterval(timer);
  }, [delay]);
}
