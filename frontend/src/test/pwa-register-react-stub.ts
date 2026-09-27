// Stub de virtual:pwa-register/react para tests (jsdom no resuelve
// los módulos virtuales de vite-plugin-pwa).
export function useRegisterSW() {
  return {
    needRefresh: [false, () => {}] as [boolean, (v: boolean) => void],
    offlineReady: [false, () => {}] as [boolean, (v: boolean) => void],
    updateServiceWorker: async () => {},
  };
}
