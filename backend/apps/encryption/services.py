"""Servicio para E2E encryption: gestión de claves y tareas cifradas."""
from .models import UserPublicKey, EncryptedTask, EncryptedKeyShare


def register_public_key(user, public_key, key_id, algorithm="RSA-OA-256"):
    """Registra una clave pública de usuario."""
    # Desactivar claves anteriores
    UserPublicKey.objects.filter(user=user, is_active=True).update(is_active=False)
    key, created = UserPublicKey.objects.update_or_create(
        user=user,
        key_id=key_id,
        defaults={
            "public_key": public_key,
            "algorithm": algorithm,
            "is_active": True,
        },
    )
    return key


def get_active_public_key(user):
    """Obtiene la clave pública activa de un usuario."""
    return UserPublicKey.objects.filter(user=user, is_active=True).first()


def create_encrypted_task(user, encrypted_data, encryption_key_id, iv, auth_tag="", algorithm="AES-256-GCM"):
    """Crea una tarea cifrada E2E."""
    return EncryptedTask.objects.create(
        owner=user,
        encrypted_data=encrypted_data,
        encryption_key_id=encryption_key_id,
        iv=iv,
        auth_tag=auth_tag,
        algorithm=algorithm,
    )


def add_key_share(encrypted_task, user, encrypted_key, user_public_key):
    """Añade una clave compartida para que otro usuario pueda descifrar la tarea."""
    return EncryptedKeyShare.objects.create(
        encrypted_task=encrypted_task,
        user=user,
        encrypted_key=encrypted_key,
        user_public_key=user_public_key,
    )


def list_encrypted_tasks(user):
    """Lista tareas cifradas del usuario."""
    return EncryptedTask.objects.filter(owner=user)


def list_shared_encrypted_tasks(user):
    """Lista tareas cifradas compartidas con el usuario."""
    shares = EncryptedKeyShare.objects.filter(user=user).select_related("encrypted_task")
    return [
        {
            "id": share.encrypted_task.id,
            "encrypted_data": share.encrypted_task.encrypted_data,
            "iv": share.encrypted_task.iv,
            "auth_tag": share.encrypted_task.auth_tag,
            "algorithm": share.encrypted_task.algorithm,
            "encrypted_key": share.encrypted_key,
            "shared_by": share.encrypted_task.owner.email,
            "created_at": share.encrypted_task.created_at.isoformat(),
        }
        for share in shares
    ]
