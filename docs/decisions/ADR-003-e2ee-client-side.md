# ADR-003: E2EE en cliente, clave privada solo en dispositivo

## Contexto

Requisito de privacidad: contenido de tareas cifrado de extremo a
extremo sin que el servidor pueda leerlo, con soporte multi-dispositivo.

## Decisión

RSA-OAEP-4096 por dispositivo envolviendo una clave AES-GCM simétrica
por tarea (`frontend/src/lib/e2ee.ts`). La privada nunca sale del
dispositivo; el backup va cifrado con passphrase del usuario. La
rotación de clave pública es atómica y conserva la anterior — los
shares antiguos siguen descifrables.

Threat model completo: `docs/security/e2ee-threat-model.md`.

## Consecuencias

+ El servidor solo ve ciphertext: breach de DB no filtra contenido.
+ Tareas cifradas se excluyen de FTS y del asistente IA (no hay
  plaintext que procesar) — documentado en AGENTS.md.
+ Perder la privada sin backup = pérdida de datos irrecuperable
  (trade-off inherente al E2EE; documentado en backup-restore.md).
+ No hay búsqueda server-side sobre contenido cifrado — limitación
  aceptada y visible al usuario.
