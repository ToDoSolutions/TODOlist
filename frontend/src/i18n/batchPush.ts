// Tarjeta de notificaciones push (ProfilePage) + helpers de suscripción.
// Claves namespaced bajo p.push.*.
export default {
  es: {
    "p.push.title": "Notificaciones push",
    "p.push.desc": "Recibe avisos en este dispositivo aunque el navegador esté cerrado.",
    "p.push.switchLabel": "Recibir notificaciones push en este dispositivo",
    "p.push.statusOn": "Activadas.",
    "p.push.statusOff": "Desactivadas.",
    "p.push.checking": "Comprobando estado…",
    "p.push.unsupported":
      "Este navegador no admite notificaciones push (se requiere HTTPS y Service Worker).",
    "p.push.noServerKey":
      "El servidor no tiene push configurado (falta la clave VAPID). Inténtalo más tarde.",
    "p.push.permissionDenied":
      "Las notificaciones están bloqueadas. Actívalas en la configuración del navegador para este sitio.",
    "p.push.permissionRequired":
      "El navegador te pedirá permiso la primera vez que las actives.",
    "p.push.subscribed": "Notificaciones push activadas",
    "p.push.unsubscribed": "Notificaciones push desactivadas",
    "p.push.subscribeError": "No se pudieron activar las notificaciones push.",
    "p.push.unsubscribeError": "No se pudieron desactivar las notificaciones push.",
  } as Record<string, string>,
  en: {
    "p.push.title": "Push notifications",
    "p.push.desc": "Get alerts on this device even when the browser is closed.",
    "p.push.switchLabel": "Receive push notifications on this device",
    "p.push.statusOn": "Enabled.",
    "p.push.statusOff": "Disabled.",
    "p.push.checking": "Checking status…",
    "p.push.unsupported":
      "This browser doesn't support push notifications (HTTPS and Service Worker required).",
    "p.push.noServerKey":
      "The server doesn't have push configured (missing VAPID key). Try again later.",
    "p.push.permissionDenied":
      "Notifications are blocked. Enable them in your browser settings for this site.",
    "p.push.permissionRequired":
      "The browser will ask for permission the first time you enable them.",
    "p.push.subscribed": "Push notifications enabled",
    "p.push.unsubscribed": "Push notifications disabled",
    "p.push.subscribeError": "Could not enable push notifications.",
    "p.push.unsubscribeError": "Could not disable push notifications.",
  } as Record<string, string>,
};
