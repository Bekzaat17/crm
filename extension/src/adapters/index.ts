import { ReadError, type ConversationReader } from "../types.js";
import { instagramReader } from "./instagram.js";
import { whatsappReader } from "./whatsapp.js";

const READERS: ConversationReader[] = [whatsappReader, instagramReader];

/** Фабрика адаптеров: новый мессенджер добавляется в список READERS. */
export function readerFor(location: Location): ConversationReader {
  const reader = READERS.find((r) => r.matches(location));
  if (!reader)
    throw new ReadError("Откройте диалог WhatsApp Web или Instagram Direct.");
  return reader;
}
