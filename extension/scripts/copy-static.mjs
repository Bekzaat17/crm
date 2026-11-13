import { cp, readFile, writeFile } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const dist = new URL("dist/", root);
await cp(new URL("static/", root), dist, { recursive: true });

// Адрес CRM фиксируется при сборке: поле адреса в расширении не нужно,
// доступ к CRM указан в манифесте и не запрашивается у пользователя.
const crmUrl = new URL(process.env.CRM_URL || "http://127.0.0.1:3100");
const local = ["127.0.0.1", "localhost"].includes(crmUrl.hostname);
if (crmUrl.protocol !== "https:" && !(local && crmUrl.protocol === "http:"))
  throw new Error("CRM_URL должен начинаться с https://");
await writeFile(
  new URL("config.js", dist),
  `export const CRM_URL = ${JSON.stringify(crmUrl.origin)};\n`,
);
const manifestPath = new URL("manifest.json", dist);
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
manifest.host_permissions = [
  ...manifest.host_permissions,
  `${crmUrl.origin}/*`,
];
await writeFile(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
console.log(`Расширение собрано в extension/dist для ${crmUrl.origin}`);
