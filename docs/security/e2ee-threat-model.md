# Threat Model: cifrado del lado del cliente (EncryptedTask)

> **Nota de naming**: la funcionalidad se denomina internamente "E2E", pero el
> modelo real es **cifrado del lado del cliente con gestión de claves por
> servidor** (sin verificación de fingerprints entre usuarios). Este documento
> describe honestamente qué protege y qué no.

## 1. Activos protegidos

- Título, descripción y contenido de `EncryptedTask` (`encrypted_data`, AES-256-GCM).
- La clave AES por tarea, distribuida como `EncryptedKeyShare` cifrada con la
  clave pública (RSA-OA-256 / X25519) de cada participante.

## 2. Activos NO protegidos (metadatos visibles al servidor)

- Existencia de la tarea, fechas (`created_at`/`updated_at`/`due_date`),
  estado, prioridad, proyecto, sprint, tags, asignación.
- Quién tiene key shares (grafo de acceso).
- Comentarios y adjuntos de la tarea asociada (no están cifrados).
- Tamaño del payload cifrado (filtra longitud aproximada del contenido).

## 3. Adversarios

| Adversario | Mitigación |
|---|---|
| Lectura de BD filtrada | Contenido cifrado; sin clave AES no hay plaintext |
| Acceso a backups | Igual que BD |
| Admin de la plataforma curioso | **Parcial**: el servidor nunca almacena la clave privada del usuario, pero sirve las claves públicas — un servidor malicioso podría sustituir una clave pública por una propia (MITM clásico de server-side key distribution) |
| Usuario con dispositivo comprometido | Rotación de `UserPublicKey` (`rotated_at`) + revocación de `SyncDevice` |

## 4. Limitaciones conocidas (aceptadas)

1. **Sin verificación de claves**: no hay fingerprinting/QR/SAS para que los
   usuarios verifiquen las claves públicas de otros. Un servidor malicioso
   puede interceptar la distribución de claves. → Mitigación futura: verificación
   manual de fingerprints.
2. **Sin forward secrecy**: una clave privada comprometida descifra todo el
   historial de shares de ese usuario.
3. **La tarea `Task` asociada existe en claro** (metadatos): el servidor ve que
   "hay una tarea" aunque no su contenido.
4. **Las tareas cifradas se excluyen de**: FTS (`TaskViewSet.search`),
   búsqueda global, asistente IA, y automatizaciones que lean contenido —
   porque el servidor no puede procesar ciphertext. Esto es por diseño.
5. **PWA/IndexedDB**: si el cliente cachea plaintext descifrado, un dispositivo
   compartido lo expone. El cliente no persiste plaintext descifrado.
6. **Clave privada en localStorage** (`todolist.e2e.privateKey`, pkcs8 base64):
   un XSS o extensión maliciosa podría exfiltrarla — mismo alcance que "cliente
   comprometido" (§6). La UI ofrece exportación PEM para backup/otro dispositivo.
   Mitigación futura: passphrase de wrapping (AES-GCM con clave derivada por
   PBKDF2) o IndexedDB con CryptoKey no extraíble.

## 5. Flujos

### Implementación cliente

`frontend/src/lib/e2ee.ts` (WebCrypto API): RSA-OAEP-2048/SHA-256 para
`wrapKey`/`unwrapKey` de la clave AES-256-GCM de cada tarea. El tag GCM va
separado (`auth_tag`, últimos 16 bytes del output de WebCrypto). Las claves
públicas viajan como SPKI base64; `GET /api/public-keys/lookup/?email=` resuelve
la pública activa del destinatario al compartir. Al crear una tarea cifrada el
cliente genera también un self-share (EncryptedKeyShare hacia el propio
usuario) — es la única forma de recuperar la clave AES después.

### Crear tarea cifrada
```
cliente: genera AES-256 key K
cliente: encrypted_data = AES-GCM(K, {title, description, ...})
cliente: para cada participante → EncryptedKeyShare(user, RSA_OAEP(pk_user, K))
servidor: almacena ciphertext + shares (nunca K ni plaintext)
```

### Rotación de clave de usuario
```
UserPublicKey.is_active=False + rotated_at=now para la anterior
nueva clave pública registrada; shares antiguos NO se recifran
automáticamente (limitación: el owner de la tarea debe re-emitir shares)
```

### Revocación de dispositivo
```
SyncDevice.is_active=False → el dispositivo pierde acceso API;
los key shares existentes en ese dispositivo no se borran remotamente
(limitación inherente a cifrado cliente)
```

## 6. Qué NO intenta defender

- Adversario con ejecución de código en el cliente (XSS, extensión maliciosa).
- Adversario que controle el servidor Y sustituya claves públicas (sin
  verificación out-of-band, esto es indetectable — igual que cualquier
  sistema server-mediated sin fingerprinting).
- Metadatos de tráfico (cuándo se cifra, tamaño, frecuencia).

## 7. Tests que cubren el modelo

- `test_encryption*`: registro de claves, creación de EncryptedTask, key shares,
  rotación, exclusión de FTS/IA, revocación de dispositivos.
- `test_security_horizontal*`: aislamiento — un usuario no ve EncryptedTasks
  ajenas ni sus shares.
