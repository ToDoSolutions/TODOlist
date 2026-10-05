// Cifrado de extremo a extremo en cliente (WebCrypto).
// RSA-OAEP-4096 por dispositivo envuelve una clave AES-256-GCM por tarea;
// la privada solo vive en este dispositivo (backup = PEM descargable).
// El servidor nunca ve plaintext ni la clave AES sin envolver.

const RSA_ALG = { name: "RSA-OAEP", hash: "SHA-256" } as const;
const AES_ALG = "AES-GCM";
const AES_KEY_LEN = 256;
const GCM_IV_LEN = 12; // bytes recomendados para GCM
const GCM_TAG_BITS = 128;
const GCM_TAG_BYTES = GCM_TAG_BITS / 8;
const STORAGE_KEY = "todolist-e2ee-private-key";

// ---------- utilidades base64 / PEM ----------

function bufToB64(buf: ArrayBuffer | Uint8Array): string {
  const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function b64ToBuf(b64: string): Uint8Array {
  const s = atob(b64.trim());
  const out = new Uint8Array(s.length);
  for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
  return out;
}

/** Quita cabeceras/armadura de un PEM y devuelve el base64 interno. */
export function pemToB64(pem: string): string {
  return pem
    .replace(/-----BEGIN [^-]+-----/g, "")
    .replace(/-----END [^-]+-----/g, "")
    .replace(/\s+/g, "");
}

/** Envuelve un base64 en armadura PEM (líneas de 64 chars). */
export function b64ToPem(b64: string, label: string): string {
  const body = b64.replace(/\s+/g, "").replace(/.{1,64}/g, "$&\n").trim();
  return `-----BEGIN ${label}-----\n${body}\n-----END ${label}-----\n`;
}

// ---------- RSA-OAEP (par de claves del dispositivo) ----------

export function generateRsaKeyPair(): Promise<CryptoKeyPair> {
  return crypto.subtle.generateKey(
    { ...RSA_ALG, modulusLength: 4096, publicExponent: new Uint8Array([1, 0, 1]) },
    true,
    ["wrapKey", "unwrapKey"],
  );
}

export async function exportPublicKeyB64(key: CryptoKey): Promise<string> {
  return bufToB64(await crypto.subtle.exportKey("spki", key));
}

export async function exportPrivateKeyB64(key: CryptoKey): Promise<string> {
  return bufToB64(await crypto.subtle.exportKey("pkcs8", key));
}

export function importPublicKeyB64(b64: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("spki", b64ToBuf(b64) as BufferSource, RSA_ALG, false, [
    "wrapKey",
  ]);
}

export function importPrivateKeyB64(b64: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("pkcs8", b64ToBuf(b64) as BufferSource, RSA_ALG, false, [
    "unwrapKey",
  ]);
}

// ---------- almacenamiento local de la privada ----------

export function storePrivateKey(b64: string): void {
  localStorage.setItem(STORAGE_KEY, b64);
}

export function loadPrivateKeyB64(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function clearPrivateKey(): void {
  localStorage.removeItem(STORAGE_KEY);
}

// ---------- AES-256-GCM (clave por tarea) ----------

export function generateAesKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey(
    { name: AES_ALG, length: AES_KEY_LEN },
    true, // extractable: hace falta para wrapAesKey
    ["encrypt", "decrypt"],
  );
}

export interface EncryptedPayload {
  encrypted_data: string;
  iv: string;
  auth_tag: string;
}

/** Cifra un objeto JSON. WebCrypto concatena ct||tag; se separan para el backend. */
export async function encryptJson(
  aes: CryptoKey,
  data: unknown,
): Promise<EncryptedPayload> {
  const iv = crypto.getRandomValues(new Uint8Array(GCM_IV_LEN));
  const plain = new TextEncoder().encode(JSON.stringify(data));
  const buf = new Uint8Array(
    await crypto.subtle.encrypt(
      { name: AES_ALG, iv, tagLength: GCM_TAG_BITS },
      aes,
      plain,
    ),
  );
  return {
    encrypted_data: bufToB64(buf.subarray(0, buf.length - GCM_TAG_BYTES)),
    iv: bufToB64(iv),
    auth_tag: bufToB64(buf.subarray(buf.length - GCM_TAG_BYTES)),
  };
}

/** Descifra {encrypted_data, iv, auth_tag} y parsea el JSON resultante. */
export async function decryptJson<T>(
  aes: CryptoKey,
  payload: EncryptedPayload,
): Promise<T> {
  const ct = b64ToBuf(payload.encrypted_data);
  const tag = b64ToBuf(payload.auth_tag || "");
  const buf = new Uint8Array(ct.length + tag.length);
  buf.set(ct);
  buf.set(tag, ct.length);
  const plain = await crypto.subtle.decrypt(
    { name: AES_ALG, iv: b64ToBuf(payload.iv) as BufferSource, tagLength: GCM_TAG_BITS },
    aes,
    buf,
  );
  return JSON.parse(new TextDecoder().decode(plain)) as T;
}

/** Envuelve la clave AES con la pública RSA del destinatario. */
export async function wrapAesKey(aes: CryptoKey, publicKey: CryptoKey): Promise<string> {
  const wrapped = await crypto.subtle.wrapKey("raw", aes, publicKey, RSA_ALG);
  return bufToB64(wrapped);
}

/** Desenvuelve una clave AES con la privada RSA de este dispositivo. */
export function unwrapAesKey(wrappedB64: string, privateKey: CryptoKey): Promise<CryptoKey> {
  return crypto.subtle.unwrapKey(
    "raw",
    b64ToBuf(wrappedB64) as BufferSource,
    privateKey,
    RSA_ALG,
    { name: AES_ALG, length: AES_KEY_LEN },
    false,
    ["encrypt", "decrypt"],
  );
}
