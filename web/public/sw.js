/* Service worker RehubPro CRM: только уведомления, без кеширования страниц. */
const sameOriginPath = (value) =>
  typeof value === "string" && value.startsWith("/") && !value.startsWith("//")
    ? value
    : "/";

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  event.waitUntil(
    self.registration.showNotification(data.title || "RehubPro CRM", {
      body: data.body || "",
      tag: data.tag,
      data: { url: sameOriginPath(data.url) },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = new URL(event.notification.data?.url || "/", self.location.origin)
    .href;
  event.waitUntil(
    self.clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windows) => {
        const open = windows.find((w) => w.url === url && "focus" in w);
        return open ? open.focus() : self.clients.openWindow(url);
      }),
  );
});
