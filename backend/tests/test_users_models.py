from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.users.models import APIKey, TwoFactorSecret

User = get_user_model()


@pytest.mark.django_db
class TestAPIKey:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="u1", email="u1@u.com", password="pass")

    def test_generate_key(self):
        raw, hashed, prefix = APIKey.generate_key()
        assert raw.startswith("tl_")
        assert len(raw) == 46  # tl_ + 43 urlsafe chars
        assert len(hashed) == 64
        assert len(prefix) == 12
        assert raw[:12] == prefix

    def test_verify_key(self):
        raw, hashed, prefix = APIKey.generate_key()
        api_key = APIKey.objects.create(user=self.user, name="test", key_prefix=prefix, hashed_key=hashed)
        result = APIKey.verify_key(raw)
        assert result == api_key
        api_key.refresh_from_db()
        assert api_key.last_used_at is not None

    def test_verify_key_invalid(self):
        assert APIKey.verify_key("invalid") is None
        assert APIKey.verify_key("") is None
        assert APIKey.verify_key(None) is None

    def test_verify_key_inactive(self):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(user=self.user, name="test", key_prefix=prefix, hashed_key=hashed, is_active=False)
        assert APIKey.verify_key(raw) is None

    def test_verify_key_expired(self):
        raw, hashed, prefix = APIKey.generate_key()
        APIKey.objects.create(user=self.user, name="test", key_prefix=prefix, hashed_key=hashed, expires_at=timezone.now() - timedelta(days=1))
        assert APIKey.verify_key(raw) is None


@pytest.mark.django_db
class TestTwoFactorSecret:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="u2", email="u2@u.com", password="pass")
        self.totp = TwoFactorSecret.objects.create(user=self.user, secret="JBSWY3DPEHPK3PXP")

    def test_generate_backup_codes(self):
        codes = self.totp.generate_backup_codes(5)
        assert len(codes) == 5
        assert all(len(c) == 10 for c in codes)
        assert all(c.isupper() or c.isdigit() for c in codes)
        self.totp.refresh_from_db()
        # En BD se guardan los hashes, no los códigos en claro
        assert self.totp.backup_codes != codes
        assert all(len(h) == 64 for h in self.totp.backup_codes)

    def test_use_backup_code(self):
        codes = self.totp.generate_backup_codes(2)
        code = codes[0]
        assert self.totp.use_backup_code(code) is True
        self.totp.refresh_from_db()
        assert code not in self.totp.backup_codes
        assert self.totp.use_backup_code(code) is False

    def test_use_backup_code_invalid(self):
        assert self.totp.use_backup_code("INVALID") is False
        assert self.totp.use_backup_code("") is False

    def test_verify_totp(self):
        import pyotp
        totp = pyotp.TOTP("JBSWY3DPEHPK3PXP")
        code = totp.now()
        assert self.totp.verify_totp(code) is True
        assert self.totp.verify_totp("000000") is False
