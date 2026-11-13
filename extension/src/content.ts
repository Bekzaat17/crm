import { readerFor } from "./adapters/index.js";

type Request = { type: "rehub:read" };

chrome.runtime.onMessage.addListener((request: Request, _sender, respond) => {
  if (request?.type !== "rehub:read") return;
  try {
    const result = readerFor(location).read(document);
    respond({ ok: true, result });
  } catch (error) {
    respond({
      ok: false,
      error:
        error instanceof Error ? error.message : "Не удалось прочитать диалог.",
    });
  }
});
