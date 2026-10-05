// Creación de una tarea cifrada E2E desde cualquier flujo de creación.
// Orquesta: Task placeholder ("🔒") + EncryptedTask (AES-GCM) + self-share
// (la clave AES envuelta con la propia RSA pública — única vía de
// recuperación; el servidor nunca ve plaintext ni la clave sin envolver).
import { authApi } from "../api/auth";
import { encryptionApi, tasksApi } from "../api/resources";
import type { EncryptedTaskItem, Task } from "../types";
import {
  encryptJson,
  generateAesKey,
  importPublicKeyB64,
  pemToB64,
  wrapAesKey,
} from "./e2ee";

export interface ActiveKey {
  id: number;
  key_id: string;
  public_key: string;
}

export interface CreateEncryptedTaskInput {
  title: string;
  description?: string;
  /** Metadatos que quedan en claro en la Task (proyecto, prioridad, fecha…). */
  taskFields?: Record<string, unknown>;
}

/**
 * Crea la Task placeholder + EncryptedTask + key share propio.
 * Devuelve { task, encryptedTask }.
 */
export async function createEncryptedTask(
  input: CreateEncryptedTaskInput,
  activeKey: ActiveKey,
): Promise<{ task: Task; encryptedTask: EncryptedTaskItem }> {
  const task = (await tasksApi.create({
    title: "🔒",
    ...(input.taskFields ?? {}),
  })) as Task;

  const aes = await generateAesKey();
  const enc = await encryptJson(aes, {
    title: input.title.trim(),
    description: input.description ?? "",
  });
  const pubB64 = activeKey.public_key.includes("BEGIN")
    ? pemToB64(activeKey.public_key)
    : activeKey.public_key;
  const wrapped = await wrapAesKey(aes, await importPublicKeyB64(pubB64));

  const encryptedTask = (await encryptionApi.createEncryptedTask({
    task: task.id,
    encrypted_data: enc.encrypted_data,
    iv: enc.iv,
    auth_tag: enc.auth_tag,
    encryption_key_id: activeKey.key_id,
    algorithm: "AES-256-GCM",
  })) as EncryptedTaskItem;

  const me = await authApi.me();
  await encryptionApi.shareTask(
    encryptedTask.id,
    me.email,
    wrapped,
    activeKey.id,
  );
  return { task, encryptedTask };
}
