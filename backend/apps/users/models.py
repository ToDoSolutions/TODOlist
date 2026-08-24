from django.contrib.auth.models import AbstractUser
from django.db import models
import secrets


class User(AbstractUser):
    """Usuario custom con campos extra para el perfil."""

    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    timezone = models.CharField(max_length=64, default="UTC")
    locale = models.CharField(max_length=10, default="es")

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
            # Actualizar last_used_at
            api_key.last_used_at = timezone.now()
            api_key.save(update_fields=["last_used_at"])
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
        """Genera códigos de backup de un solo uso."""
        import secrets as _secrets
        self.backup_codes = [_secrets.token_hex(4).upper() for _ in range(count)]
        self.save(update_fields=["backup_codes"])
        return self.backup_codes

    def use_backup_code(self, code):
        """Verifica y consume un código de backup. Retorna True si era válido."""
        if code.upper() in self.backup_codes:
            self.backup_codes.remove(code.upper())
            self.save(update_fields=["backup_codes"])
            return True
        return False

    def verify_totp(self, code):
        """Verifica un código TOTP."""
        import pyotp
        totp = pyotp.TOTP(self.secret)
        return totp.verify(code, valid_window=1)
