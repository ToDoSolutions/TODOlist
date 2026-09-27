// Comprueba que toda clave t("...") usada en src/ existe en los recursos
// es/en (core de i18n/index.ts + batches). Uso: node _check_i18n.mjs
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const SRC = new URL("./src", import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1");

const files = [];
const walk = (d) => {
  for (const e of readdirSync(d)) {
    const p = join(d, e);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(tsx?|ts)$/.test(e)) files.push(p);
  }
};
walk(SRC);

const used = new Map(); // key -> [files]
const re = /\bt\(\s*["']([a-zA-Z][\w.]*)["']/g;
for (const f of files) {
  if (f.includes("\\i18n\\") || f.endsWith(".test.ts") || f.endsWith(".test.tsx")) continue;
  const src = readFileSync(f, "utf8");
  for (const m of src.matchAll(re)) {
    if (!used.has(m[1])) used.set(m[1], []);
    used.get(m[1]).push(f);
  }
}

// Recursos definidos: core (inline en index.ts) + batches
const defined = new Set();
const indexSrc = readFileSync(join(SRC, "i18n", "index.ts"), "utf8");
for (const m of indexSrc.matchAll(/"([\w.]+)":\s*['"]/g)) defined.add(m[1]);
const dupRe = /"([\w.]+)"\s*:\s*['"]/g;
for (const e of readdirSync(join(SRC, "i18n"))) {
  if (!e.startsWith("batch")) continue;
  const src = readFileSync(join(SRC, "i18n", e), "utf8");
  const enIdx = src.search(/\ben\s*:\s*\{/);
  // dups solo dentro de cada bloque (es|en), no entre ellos
  for (const [name, blk] of [["es", src.slice(0, enIdx)], ["en", src.slice(enIdx)]]) {
    const seen = new Map();
    for (const m of blk.matchAll(dupRe)) {
      defined.add(m[1]);
      seen.set(m[1], (seen.get(m[1]) || 0) + 1);
    }
    for (const [k, n] of seen) if (n > 1) console.log(`  DUP ${e}[${name}]: ${k} ×${n}`);
  }
}

// i18next resuelve plurales con sufijos _one/_other: si existen, la base vale
const definedOrPlural = (k) =>
  defined.has(k) || defined.has(`${k}_one`) || defined.has(`${k}_other`);
const missing = [...used.keys()].filter((k) => !definedOrPlural(k));
console.log(`usadas: ${used.size} | definidas: ${defined.size} | faltan: ${missing.length}`);
for (const k of missing.sort()) {
  console.log(`  MISSING ${k}  <- ${[...new Set(used.get(k).map((f) => f.split("\\").pop()))].join(", ")}`);
}
process.exit(missing.length ? 1 : 0);
