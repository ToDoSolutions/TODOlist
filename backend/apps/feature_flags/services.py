import hashlib

from django.conf import settings

from .models import FeatureFlag


def _hash_percentage(key: str, user_id: int) -> int:
    """Devuelve un valor 0-100 determinista basado en key + user_id."""
    raw = f"{key}:{user_id}".encode("utf-8")
    digest = hashlib.md5(raw).hexdigest()
    return int(digest, 16) % 100


def is_enabled(key: str, user=None) -> bool:
    """Comprueba si un feature flag está activo.

    Orden de evaluación:
    1. Si el flag no existe o no está habilitado globalmente, se evalúa
       por usuario y por porcentaje.
    2. Si está habilitado globalmente (is_enabled=True), retorna True.
    3. Si se pasa un usuario y está en enabled_users, retorna True.
    4. Si enabled_percentage > 0 y se pasa un usuario, evalúa por hash.
    """
    try:
        flag = FeatureFlag.objects.get(key=key)
    except FeatureFlag.DoesNotExist:
        return False

    if flag.is_enabled:
        return True

    if user is not None and user.is_authenticated:
        if flag.enabled_users.filter(pk=user.pk).exists():
            return True
        if flag.enabled_percentage > 0:
            return _hash_percentage(key, user.pk) < flag.enabled_percentage

    return False


def enable(key: str) -> FeatureFlag:
    """Activa un flag globalmente."""
    flag = FeatureFlag.objects.get(key=key)
    flag.is_enabled = True
    flag.save(update_fields=["is_enabled", "updated_at"])
    return flag


def disable(key: str) -> FeatureFlag:
    """Desactiva un flag globalmente."""
    flag = FeatureFlag.objects.get(key=key)
    flag.is_enabled = False
    flag.save(update_fields=["is_enabled", "updated_at"])
    return flag


def enable_for_user(key: str, user) -> FeatureFlag:
    """Habilita un flag para un usuario específico."""
    flag = FeatureFlag.objects.get(key=key)
    flag.enabled_users.add(user)
    return flag


def disable_for_user(key: str, user) -> FeatureFlag:
    """Deshabilita un flag para un usuario específico."""
    flag = FeatureFlag.objects.get(key=key)
    flag.enabled_users.remove(user)
    return flag
