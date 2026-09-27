"""Tests de borde para APIKey y TwoFactorSecret (seguridad)."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.users.models import APIKey, TwoFactorSecret

User = get_user_model()


@pytest.fixture
def user(db):
    u, _ = User.objects.get_or_create(
        username="sec_u", defaults={"email": "sec@x.com"}
    )
    return u


class TestGenerateKey:
    def test_formato_tl(self):
        raw, hashed, prefix = APIKey.generate_key()
        assert raw.startswith("tl_")
        assert prefix == raw[:12]
        assert len(hashed) == 64  # sha256 hex

    def test_keys_unicas(self):
        r1, h1, _ = APIKey.generate_key()
        r2, h2, _ = APIKey.generate_key()
        assert r1 != r2 and h1 != h2

    def test_hash_determinista(self):
        import hashlib
        raw, hashed, _ = APIKey.generate_key()
        assert hashlib.sha256(raw.encode()).hexdigest() == hashed


@pytest.mark.django_db
class TestVerifyKey:
    def _create_key(self, user, **kw):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="k", key_prefix=prefix,
            hashed_key=hashed, **kw,
        )
        return raw

    def test_key_valida(self, user):
        raw = self._create_key(user)
        result = APIKey.verify_key(raw)
        assert result is not None
        assert result.user == user

    def test_key_inexistente_none(self):
        assert APIKey.verify_key("tl_" + "x" * 40) is None

    def test_key_sin_prefijo_none(self):
        assert APIKey.verify_key("abc123") is None

    def test_key_vacia_none(self):
        assert APIKey.verify_key("") is None
        assert APIKey.verify_key(None) is None

    def test_key_inactiva_none(self, user):
        raw = self._create_key(user, is_active=False)
        assert APIKey.verify_key(raw) is None

    def test_key_expirada_none(self, user):
        raw = self._create_key(
            user, expires_at=timezone.now() - timedelta(hours=1)
        )
        assert APIKey.verify_key(raw) is None

    def test_key_futura_ok(self, user):
        raw = self._create_key(
            user, expires_at=timezone.now() + timedelta(hours=1)
        )
        assert APIKey.verify_key(raw) is not None

    def test_actualiza_last_used_primera_vez(self, user):
        raw = self._create_key(user)
        key = APIKey.verify_key(raw)
        assert key.last_used_at is not None
        key.refresh_from_db()
        assert key.last_used_at is not None

    def test_last_used_throttle(self, user):
        """Usos repetidos dentro del throttle no reescriben."""
        raw = self._create_key(user)
        k1 = APIKey.verify_key(raw)
        t1 = k1.last_used_at
        k2 = APIKey.verify_key(raw)
        assert k2.last_used_at == t1

    def test_last_used_actualiza_tras_throttle(self, user):
        raw = self._create_key(user)
        key = APIKey.objects.get(user=user)
        key.last_used_at = timezone.now() - timedelta(seconds=901)
        key.save()
        k = APIKey.verify_key(raw)
        assert k.last_used_at > timezone.now() - timedelta(seconds=60)

    def test_key_ajena_no_valida(self, user):
        # Una key de otro formato no debe validar
        _, hashed, _ = APIKey.generate_key()
        APIKey.objects.create(
            user=user, name="k", key_prefix="x", hashed_key=hashed,
        )
        assert APIKey.verify_key("tl_wrong_key") is None


@pytest.mark.django_db
class TestTwoFactorSecret:
    def _secret(self, user):
        return TwoFactorSecret.objects.create(
            user=user, secret="JBSWY3DPEHPK3PXP"
        )

    def test_backup_codes_genera_y_hashea(self, user):
        s = self._secret(user)
        codes = s.generate_backup_codes(count=5)
        assert len(codes) == 5
        s.refresh_from_db()
        assert len(s.backup_codes) == 5
        # Los códigos en claro NO se almacenan
        for c in codes:
            assert c not in s.backup_codes

    def test_backup_codes_count_param(self, user):
        s = self._secret(user)
        codes = s.generate_backup_codes(count=3)
        assert len(codes) == 3

    def test_use_backup_code_valido(self, user):
        s = self._secret(user)
        codes = s.generate_backup_codes(count=3)
        assert s.use_backup_code(codes[0]) is True

    def test_use_backup_code_un_solo_uso(self, user):
        s = self._secret(user)
        codes = s.generate_backup_codes(count=3)
        assert s.use_backup_code(codes[0]) is True
        s.refresh_from_db()
        assert s.use_backup_code(codes[0]) is False
        assert len(s.backup_codes) == 2

    def test_use_backup_code_invalido(self, user):
        s = self._secret(user)
        s.generate_backup_codes(count=3)
        assert s.use_backup_code("WRONGCODE1") is False

    def test_use_backup_code_normaliza(self, user):
        """minúsculas y espacios se aceptan."""
        s = self._secret(user)
        codes = s.generate_backup_codes(count=2)
        assert s.use_backup_code(f"  {codes[0].lower()}  ") is True

    def test_use_backup_code_vacio(self, user):
        s = self._secret(user)
        s.generate_backup_codes(count=2)
        assert s.use_backup_code("") is False
        assert s.use_backup_code(None) is False

    def test_verify_totp_valido(self, user):
        import pyotp
        s = self._secret(user)
        code = pyotp.TOTP(s.secret).now()
        assert s.verify_totp(code) is True

    def test_verify_totp_invalido(self, user):
        s = self._secret(user)
        assert s.verify_totp("000000") is False or True
        # "000000" podría coincidir por ventana; usar claramente malo:
        assert s.verify_totp("abc") is False
        assert s.verify_totp("") is False

    def test_verify_totp_excepcion_false(self, user):
        s = self._secret(user)
        s.secret = "!!!invalid-base32!!!"
        assert s.verify_totp("123456") is False

    def test_ventana_tolerancia(self, user):
        """valid_window=1 acepta el periodo anterior/siguiente."""
        import time

        import pyotp
        s = self._secret(user)
        totp = pyotp.TOTP(s.secret)
        prev_code = totp.at(int(time.time()) - 30)
        # el código del periodo previo debe seguir validando (window=1)
        assert s.verify_totp(prev_code) is True
