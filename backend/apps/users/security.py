"""Helpers de seguridad: rate limiting para 2FA y utilidades de hash."""
import hashlib
import hmac
import secrets

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


def hash_backup_code(code: str, salt: str | None = None) -> str:
    """Hash PBKDF2-HMAC-SHA256 con sal por código.

    Formato: ``pbkdf2$<salt_hex>$<digest_hex>``. La sal impide rainbow
    tables y la KDF encarece la fuerza bruta offline ante una fuga de BD.
    """
    normalized = code.strip().upper()
    if salt is None:
        salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac(
        "sha256", normalized.encode(), bytes.fromhex(salt), 60_000
    ).hex()
    return f"pbkdf2${salt}${digest}"


def verify_backup_code(code: str, stored: str) -> bool:
    """Comprueba ``code`` contra un hash almacenado.

    Acepta el formato ``pbkdf2$...`` y el legacy SHA-256 sin sal (hashes
    generados antes de la migración de formato), en tiempo constante.
    """
    normalized = code.strip().upper()
    if stored.startswith("pbkdf2$"):
        try:
            _, salt, _ = stored.split("$", 2)
        except ValueError:
            return False
        candidate = hash_backup_code(normalized, salt)
    else:
        candidate = hashlib.sha256(normalized.encode()).hexdigest()
    return hmac.compare_digest(candidate, stored)
