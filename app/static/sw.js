self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_) {
    payload = {};
  }

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      const hasVisibleClient = windowClients.some((client) => client.visibilityState === "visible");
      if (hasVisibleClient) {
        return undefined;
      }

      const title = payload.title || "CoyoLabs";
      const options = {
        body: payload.body || "",
        data: {
          url: payload.url || "/notifications",
        },
      };
      return self.registration.showNotification(title, options);
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || "/notifications";

  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      for (const client of windowClients) {
        if (client.url.includes(targetUrl) && "focus" in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
      return undefined;
    }),
  );
});

self.addEventListener("pushsubscriptionchange", (event) => {
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((windowClients) => {
      windowClients.forEach((client) => client.postMessage({ type: "PUSH_SUBSCRIPTION_CHANGED" }));
      return undefined;
    }),
  );
});
