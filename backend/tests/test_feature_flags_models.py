import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.feature_flags.models import FeatureFlag

User = get_user_model()


@pytest.mark.django_db
class TestFeatureFlag:
    def test_str(self):
        flag = FeatureFlag.objects.create(key="flag1", name="Flag 1", is_enabled=True)
        assert "flag1" in str(flag)
        assert "on" in str(flag)
        flag.is_enabled = False
        assert "off" in str(flag)

    def test_defaults(self):
        flag = FeatureFlag.objects.create(key="flag1", name="Flag 1")
        assert flag.is_enabled is False
        assert flag.description == ""
        assert flag.enabled_percentage == 0

    def test_unique_key(self):
        FeatureFlag.objects.create(key="flag1", name="Flag 1")
        with pytest.raises(IntegrityError):
            FeatureFlag.objects.create(key="flag1", name="Flag 2")

    def test_ordering(self):
        f1 = FeatureFlag.objects.create(key="flag1", name="Flag 1")
        f2 = FeatureFlag.objects.create(key="flag2", name="Flag 2")
        # auto_now_add puede asignar el mismo timestamp en SQLite: fijar explícito
        from django.utils import timezone as tz
        FeatureFlag.objects.filter(pk=f1.pk).update(created_at=tz.now() - tz.timedelta(hours=2))
        FeatureFlag.objects.filter(pk=f2.pk).update(created_at=tz.now() - tz.timedelta(hours=1))
        flags = list(FeatureFlag.objects.all())
        assert flags[0] == f2  # ordering by -created_at
