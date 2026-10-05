# Política de ciclo de vida y retirada

## Estados de un componente/feature

`propuesto → experimental → beta → estable → deprecado → fuera de soporte → eliminado`

| Estado | Significado | Compromiso |
|---|---|---|
| propuesto | idea/ADR sin código | ninguno |
| experimental | funciona pero sin garantías | puede romperse sin aviso; feature flag |
| beta | usable, puede cambiar | aviso en CHANGELOG si rompe |
| estable | feature completa | compatibilidad + tests obligatorios |
| deprecado | sigue funcionando, hay alternativa | fecha de retirada anunciada |
| fuera de soporte | no se corrige | solo eliminación pendiente |
| eliminado | código, flags, métricas y docs fuera | — |

Las features y su nivel real viven en `docs/maturity.md`; una que
afirme nivel ≥5 debe pasar la Definition of Done de CONTRIBUTING.

## Retirar una API o feature

1. Identificar consumidores (schema OpenAPI, búsqueda en código,
   telemetría si existe).
2. Anuncio en `CHANGELOG.md` + la respuesta gana `Deprecation` header
   o el endpoint devuelve warning en el body.
3. Alternativa documentada con fecha de retirada (mínimo 1 release
   completo si el proyecto versiona; si no, un periodo razonable
   anunciado en CHANGELOG).
4. Bloquear usos nuevos (lint, error 410 para APIs viejas si procede).
5. Retirar: código + flags + métricas + docs + tests del feature.

## Deprecar una decisión arquitectónica

El ADR viejo se queda (nunca se borra) — se marca `Superseded by
ADR-XXX` y el nuevo ADR lo referencia.
