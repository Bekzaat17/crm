import {
  CrmClient,
  CrmError,
  fragmentKey,
  type ChatStatus,
} from "./crm-client.js";
import { loadSettings } from "./settings.js";
import type { ReadResult } from "./types.js";

type SyncRequest = { type: "rehub:sync"; read: ReadResult };
export type SyncResponse = {
  connected: boolean;
  tracked: boolean;
  created?: number;
  error?: string;
};

const STATUS_TTL = 60_000;
const statusCache = new Map<string, { at: number; status: ChatStatus }>();

async function status(client: CrmClient, read: ReadResult) {
  const key = `${read.source}:${read.conversation.external_id}`;
  const cached = statusCache.get(key);
  if (cached && Date.now() - cached.at < STATUS_TTL) return cached.status;
  const fresh = await client.status({
    source: read.source,
    external_id: read.conversation.external_id,
  });
  statusCache.set(key, { at: Date.now(), status: fresh });
  return fresh;
}

/** Автосинхронизация: передаём только чаты с включённой галочкой. */
async function sync(read: ReadResult): Promise<SyncResponse> {
  const settings = await loadSettings();
  if (!settings.key) return { connected: false, tracked: false };
  const client = new CrmClient(settings);
  try {
    const current = await status(client, read);
    if (!current.tracked || !current.lead)
      return { connected: true, tracked: false };
    const result = await client.importFragment(
      read,
      current.lead.id,
      await fragmentKey(read),
    );
    return { connected: true, tracked: true, created: result.created };
  } catch (error) {
    if (error instanceof CrmError && error.status === 401) {
      await chrome.storage.local.remove(["key", "company"]);
      return { connected: false, tracked: false, error: error.message };
    }
    return {
      connected: true,
      tracked: true,
      error: error instanceof Error ? error.message : "Ошибка синхронизации",
    };
  }
}

chrome.runtime.onMessage.addListener(
  (request: SyncRequest | { type: string }, _sender, respond) => {
    if (request.type === "rehub:sync") {
      void sync((request as SyncRequest).read).then(respond);
      return true; // ответ асинхронный
    }
    if (request.type === "rehub:status-changed") statusCache.clear();
  },
);
