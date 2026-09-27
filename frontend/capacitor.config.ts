import type { CapacitorConfig } from "@capacitor/cli";

// Apps nativas iOS/Android via Capacitor: empaqueta el build web (dist/)
// en un WebView nativo. La API Django se sigue consumiendo por HTTP —
// requiere VITE_API_URL absoluta y CORS/CSRF configurados para los
// orígenes nativos (ver docs/native-apps.md).
const config: CapacitorConfig = {
  appId: "com.todolist.app",
  appName: "TODOlist",
  webDir: "dist",
  // En desarrollo en el dispositivo/emulador, apuntar al servidor Vite:
  // server: { url: "http://<ip-local>:5173", cleartext: true },
  android: {
    // Permitir cookies httpOnly de la API en el WebView.
    webContentsDebuggingEnabled: false,
  },
  ios: {
    contentInset: "automatic",
  },
};

export default config;
