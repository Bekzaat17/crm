import { cp } from "node:fs/promises";

await cp(
  new URL("../static/", import.meta.url),
  new URL("../dist/", import.meta.url),
  {
    recursive: true,
  },
);
console.log("Расширение собрано в extension/dist");
