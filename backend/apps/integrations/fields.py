"""Campos de modelo con cifrado en reposo (AES-256-GCM).

Gestión de claves desacoplada de SECRET_KEY:

- Las claves se definen en ``settings.DATA_ENCRYPTION_KEYS`` (lista ordenada;
  la última es la activa para nuevas escrituras).
- Formato de los valores: ``v3:k<idx>:gcm:<b64(iv+ct)>`` — el índice permite
  rotación progresiva: lecturas aceptan cualquier clave conocida, escrituras
  usan siempre la más reciente.
- Compatibilidad hacia atrás: ``v2:gcm:`` (clave derivada de SECRET_KEY) y
  ``gAAAA`` (Fernet legado) siguen siendo legibles para migración.
- Si ``DATA_ENCRYPTION_KEYS`` no está definido se deriva de SECRET_KEY
  (comportamiento legado, documentado como fallback de desarrollo).
"""
import base64
import hashlib
import logging
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

_GCM_PREFIX_V3 = "v3:"
_GCM_PREFIX_V2 = "v2:gcm:"
_FERNET_PREFIX = "gAAAA"


def _data_keys() -> list[bytes]:
    """Lista de claves de 32 bytes. La última es la activa para escritura."""
    raw = getattr(settings, "DATA_ENCRYPTION_KEYS", None) or []
    keys = [hashlib.sha256(k.encode()).digest() for k in raw if k]
    if not keys:
        # Fallback legado: deriva de SECRET_KEY (equivale a v2)
        keys = [hashlib.sha256(settings.SECRET_KEY.encode()).digest()]
    return keys


def _encrypt(plaintext: str) -> str:
    keys = _data_keys()
    idx = len(keys) - 1
    iv = os.urandom(12)
    ct = AESGCM(keys[idx]).encrypt(iv, plaintext.encode(), None)
    return f"{_GCM_PREFIX_V3}k{idx}:gcm:" + base64.urlsafe_b64encode(iv + ct).decode()


def _decrypt_v3(value: str):
    """v3:k<idx>:gcm:<b64> — descifra con la clave idx si está disponible."""
    try:
        _, kpart, _, b64 = value.split(":", 3)
        idx = int(kpart[1:])
        keys = _data_keys()
        if idx >= len(keys):
            logger.error("EncryptedTextField: clave k%s no disponible", idx)
            return None
        raw = base64.urlsafe_b64decode(b64.encode())
        return AESGCM(keys[idx]).decrypt(raw[:12], raw[12:], None).decode()
    except (InvalidTag, ValueError, IndexError):
        return None


def _decrypt_v2(value: str):
    """v2:gcm:<b64> — clave derivada de SECRET_KEY (formato anterior)."""
    try:
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        raw = base64.urlsafe_b64decode(value[len(_GCM_PREFIX_V2):].encode())
        return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode()
    except (InvalidTag, ValueError, IndexError):
        return None


def _decrypt_legacy_fernet(value: str):
    """Descifra valores Fernet antiguos (prefijo gAAAA) para migración."""
    try:
        from cryptography.fernet import Fernet
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        )
        return Fernet(key).decrypt(value.encode()).decode()
    except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
        return None


def _is_encrypted(value) -> bool:
    s = str(value)
    return s.startswith((_GCM_PREFIX_V3, _GCM_PREFIX_V2, _FERNET_PREFIX))


def _decrypt_any(value: str):
    """Intenta descifrar con todos los formatos conocidos."""
    if value.startswith(_GCM_PREFIX_V3):
        return _decrypt_v3(value)
    if value.startswith(_GCM_PREFIX_V2):
        return _decrypt_v2(value)
    if value.startswith(_FERNET_PREFIX):
        return _decrypt_legacy_fernet(value)
    return None


class EncryptedTextField(models.TextField):
    """TextField que cifra el valor en reposo y lo descifra al leer.

    Transparente para el código existente: leer el atributo devuelve
    el texto en claro; en BD se almacena AES-256-GCM con versión de clave
    (prefijo ``v3:kN:gcm:``). Los valores antiguos (``v2:gcm:``, Fernet
    ``gAAAA`` y texto en claro) se leen tal cual, así la rotación es
    transparente: al re-escribir un valor se recifra con la clave activa.
    """

    def get_prep_value(self, value):
        value = super().get_prep_value(value)  # pylint: disable=no-member
        if value and not _is_encrypted(value):
            return _encrypt(str(value))
        return value

    def from_db_value(self, value, _expression, connection):
        if value and _is_encrypted(value):
            plain = _decrypt_any(str(value))
            if plain is None:
                logger.error("EncryptedTextField: valor no descifrable")
                return value
            return plain
        return value

    def to_python(self, value):
        value = super().to_python(value)  # pylint: disable=no-member
        if value and _is_encrypted(value):
            return _decrypt_any(str(value)) or value
        return value
