/* global self, clients, URL */
// Service worker dedicado a Web Push. Es independiente del SW de precache
// que genera vite-plugin-pwa (generateSW): este archivo se sirve tal cual
// desde /public y solo gestiona los eventos `push` y `notificationclick`.
// Se registra aparte desde src/push.ts (navigator.serviceWorker.register).

self.addEventListener("push", (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch {
      // Payload no-JSON: usar el texto plano como cuerpo.
      data = { body: event.data.text() };
    }
  }
  const title = data.title || "TODOlist";
  const options = {
    body: data.body || "",
    icon: data.icon || "/pwa-192x192.png",
    badge: data.badge || "/favicon.svg",
    tag: data.tag || "todolist-push",
    // `data.url` es la ruta destino al hacer click en la notificación.
    data: { url: data.url || data.link || "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/";
  const url = new URL(target, self.location.origin).href;
  event.waitUntil(
    clients
      .matchAll({ type: "window", includeUncontrolled: true })
      .then((windowClients) => {
        // Si ya hay una ventana de la app abierta, enfocarla y navegar al
        // destino; si no, abrir una nueva.
        for (const client of windowClients) {
          if (client.url === url && "focus" in client) {
            return client.focus();
          }
        }
        for (const client of windowClients) {
          if ("focus" in client) {
            client.focus();
            if ("navigate" in client) {
              return client.navigate(url);
            }
            return client;
          }
        }
        return clients.openWindow(url);
      }),
  );
});
