import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";

export default tseslint.config(
  // vite.config.js/.d.ts son artefactos de `tsc -b` (gitignored)
  { ignores: ["dist", "node_modules", "coverage", "e2e", "vite.config.js", "vite.config.d.ts", "_*.mjs"] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    plugins: {
      "react-hooks": reactHooks,
      "react-refresh": reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "react-refresh/only-export-components": ["warn", {
        allowConstantExport: true,
        // Los hooks de contexto (useAuth, useConfirm…) viven junto a su
        // provider por convención React; no rompen fast-refresh.
        allowExportNames: ["useAuth", "useProject", "useConfirm", "useThemeMode"],
      }],
      // purity: regla del React Compiler que produce falsos positivos en
      // callbacks que no se ejecutan durante render (mutationFn, handlers)
      "react-hooks/purity": "off",
      "@typescript-eslint/no-explicit-any": "warn",
      "@typescript-eslint/no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
  {
    // Tests: mocks de APIs y errores tipados de forma laxa es aceptable
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    rules: { "@typescript-eslint/no-explicit-any": "off" },
  }
);
