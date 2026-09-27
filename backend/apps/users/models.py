import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Usuario custom con campos extra para el perfil."""

    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    timezone = models.CharField(max_length=64, default="UTC")
    locale = models.CharField(max_length=10, default="es")
    # Token opaco y revocable para el feed iCal (?token=...): los clientes de
    # calendario (Google/Outlook/Apple) no pueden enviar JWT ni cookies.
    ical_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    # Token opaco y revocable para email-to-task: el provider de inbound
    # email envía a task-<token>@<dominio> y el payload se convierte en
    # Task (o Comment si el subject referencia [task-<id>]).
    inbound_email_token = models.CharField(max_length=64, null=True, blank=True, unique=True)
    # Marca cuando el usuario confirma su email vía enlace. Social auth y
    # superusuarios pueden considerarse verificados sin este flag.
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    # Capacidad semanal configurable para workload management
    # (GET /api/tasks/workload/ la usa en vez del default 40h).
    weekly_capacity_hours = models.DecimalField(
        max_digits=5, decimal_places=1, default=40
    )
    # Out of office (estilo Asana): marca "ausente" + fecha opcional de
    # regreso. Se expone en el perfil (/api/auth/me/, /api/users/me/) para
    # que los compañeros vean la disponibilidad.
    out_of_office = models.BooleanField(default=False)
    out_of_office_until = models.DateField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self) -> str:
        return self.email


class APIKey(models.Model):
    """API key para acceso programático a la API pública."""

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="api_keys"
    )
    name = models.CharField(max_length=120, help_text="Nombre descriptivo")
    key_prefix = models.CharField(max_length=12, help_text="Primeros caracteres para identificación")
    hashed_key = models.CharField(max_length=255, unique=True)
    scopes = models.JSONField(
        default=list, blank=True,
        help_text="Permisos: read, write, admin"
    )
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.key_prefix}...)"

    @staticmethod
    def generate_key():
        """Genera una API key y retorna (raw_key, hashed_key, prefix)."""
        import hashlib
        raw = f"tl_{secrets.token_urlsafe(32)}"
        hashed = hashlib.sha256(raw.encode()).hexdigest()
        prefix = raw[:12]
        return raw, hashed, prefix

    @staticmethod
    def verify_key(raw_key):
        """Verifica una API key y retorna el usuario o None."""
        import hashlib
        if not raw_key or not raw_key.startswith("tl_"):
            return None
        hashed = hashlib.sha256(raw_key.encode()).hexdigest()
        from django.utils import timezone
        try:
            api_key = APIKey.objects.select_related("user").get(
                hashed_key=hashed, is_active=True
            )
            if api_key.expires_at and api_key.expires_at < timezone.now():
                return None
            # Actualizar last_used_at con throttle: una escritura por request
            # genera hot-write + bloat; el dato solo necesita granularidad ~15min
            from django.conf import settings
            throttle = getattr(settings, "APIKEY_LAST_USED_THROTTLE_SECONDS", 900)
            now = timezone.now()
            if not api_key.last_used_at or (
                now - api_key.last_used_at
            ).total_seconds() >= throttle:
                APIKey.objects.filter(pk=api_key.pk).update(last_used_at=now)
                api_key.last_used_at = now
            return api_key
        except APIKey.DoesNotExist:
            return None


class TwoFactorSecret(models.Model):
    """Secreto TOTP para autenticación de dos factores."""

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="twofactor"
    )
    secret = models.CharField(max_length=64)
    is_enabled = models.BooleanField(default=False)
    backup_codes = models.JSONField(default=list, blank=True)
    enabled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"2FA for {self.user.email} ({'enabled' if self.is_enabled else 'disabled'})"

    def generate_backup_codes(self, count=10):
        """Genera códigos de backup de un solo uso.

        Devuelve los códigos en claro (se muestran al usuario una sola vez)
        pero almacena SOLO los hashes SHA-256.
        """
        import secrets as _secrets

        from .security import hash_backup_code
        codes = [_secrets.token_hex(5).upper() for _ in range(count)]
        self.backup_codes = [hash_backup_code(c) for c in codes]
        self.save(update_fields=["backup_codes"])
        return codes

    def use_backup_code(self, code):
        """Verifica y consume un código de backup. Retorna True si era válido.

        Solo se aceptan hashes SHA-256 (la migración 0004 rehasa los
        códigos legacy en claro).
        """
        from .security import hash_backup_code
        normalized = (code or "").strip().upper()
        hashed = hash_backup_code(normalized)
        if hashed in self.backup_codes:
            self.backup_codes.remove(hashed)
            self.save(update_fields=["backup_codes"])
            return True
        return False

    def verify_totp(self, code):
        """Verifica un código TOTP."""
        import pyotp
        try:
            totp = pyotp.TOTP(self.secret)
            return totp.verify(code, valid_window=1)
        except Exception:  # noqa: BLE001  # boundary intencional: fallo externo no rompe el flujo
            return False
