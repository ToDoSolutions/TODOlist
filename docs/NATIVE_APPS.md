# Apps nativas (iOS/Android) con Capacitor

La app React se empaqueta como aplicación nativa vía [Capacitor](https://capacitorjs.com/):
el WebView nativo carga el build de `frontend/dist/` y habla con la API Django igual que
la PWA. Es la misma codebase — sin reescritura (estrategia equivalente a Electron/Cordova
usada por Slack, Obsidian, etc.).

## Setup

```bash
cd frontend
npm install                    # ya incluye @capacitor/core + @capacitor/cli
npm run build                  # genera dist/
npx cap add android            # crea android/ (necesita Android Studio instalado)
npx cap add ios                # crea ios/ (necesita macOS + Xcode)
npm run cap:android            # build + sync + abre Android Studio
npm run cap:ios                # build + sync + abre Xcode
```

`capacitor.config.ts` → `webDir: "dist"`. Los directorios `android/` e `ios/`
generados se commitean (Capacitor recomienda versionarlos para ajustar firma/icons).

## Requisitos del backend para la app nativa

El WebView nativo corre en origen `capacitor://localhost` (iOS) u `https://localhost`
(Android), distinto del dominio web. El backend debe aceptarlo:

1. **`VITE_API_URL`** debe apuntar a la URL pública del backend (`https://api.…/api`),
   no a `/api` relativo — el WebView no comparte origen con el servidor.

2. **CORS** — añadir los orígenes nativos en `CORS_ALLOWED_ORIGINS` del backend:
   `capacitor://localhost`, `https://localhost` (y `http://localhost` para emulador dev
   con `server.url`).

3. **Cookies de sesión** — al ser cross-site, el backend debe servir cookies con
   `SameSite=None; Secure` (configurable en settings de sesión/CSRF cuando se
   despliegue tras HTTPS) y `CSRF_TRUSTED_ORIGINS` incluyendo los mismos orígenes.

4. **Push nativo** — el Web Push de la web (push-sw.js) funciona en el WebView de
   Android; para notificaciones nativas completas (APNs) se añadiría
   `@capacitor/push-notifications` como paso posterior.

## En desarrollo

Para live-reload dentro de la app: descomenta `server.url` en `capacitor.config.ts`
apuntando a `http://<ip-de-tu-pc>:5173` con `cleartext: true` (Android), y levanta
`npm run dev` + `python manage.py runserver 0.0.0.0:8000`.
