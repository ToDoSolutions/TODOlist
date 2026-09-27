"""Helpers de seguridad: rate limiting para 2FA y utilidades de hash."""
import hashlib

from django.core.cache import cache

# Máximo de intentos fallidos de TOTP/backup antes de bloquear temporalmente
TOTP_MAX_FAILURES = 10
TOTP_LOCKOUT_SECONDS = 300  # 5 minutos


def _attempts_key(user_id) -> str:
    return f"2fa:failures:{user_id}"


def is_2fa_locked(user) -> bool:
    """True si el usuario está temporalmente bloqueado por fallos 2FA."""
    return cache.get(_attempts_key(user.id), 0) >= TOTP_MAX_FAILURES


def record_2fa_failure(user) -> None:
    """Registra un intento fallido de verificación 2FA."""
    key = _attempts_key(user.id)
    try:
        cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=TOTP_LOCKOUT_SECONDS)
    else:
        # Asegurar TTL también en incrementos (locmem/redis no renuevan TTL)
        cache.touch(key, timeout=TOTP_LOCKOUT_SECONDS)


def reset_2fa_failures(user) -> None:
    """Limpia el contador tras una verificación correcta."""
    cache.delete(_attempts_key(user.id))


def hash_backup_code(code: str) -> str:
    """Hash SHA-256 de un código de backup (nunca se guarda en claro)."""
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()
