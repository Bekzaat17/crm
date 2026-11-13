/** Подписка браузера на Web Push через service worker /sw.js. */
export const pushSupported = () =>
  typeof window !== "undefined" &&
  "serviceWorker" in navigator &&
  "PushManager" in window &&
  "Notification" in window;

function applicationServerKey(base64: string) {
  const padded = (base64 + "=".repeat((4 - (base64.length % 4)) % 4))
    .replace(/-/g, "+")
    .replace(/_/g, "/");
  return Uint8Array.from(atob(padded), (c) => c.charCodeAt(0));
}

export async function currentSubscription() {
  if (!pushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration("/");
  return (await registration?.pushManager.getSubscription()) || null;
}

export async function subscribePush(publicKey: string) {
  const permission = await Notification.requestPermission();
  if (permission !== "granted")
    throw new Error("Браузер не разрешил уведомления для этого сайта.");
  const registration = await navigator.serviceWorker.register("/sw.js", {
    scope: "/",
  });
  await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  return (
    existing ||
    registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: applicationServerKey(publicKey),
    })
  );
}
