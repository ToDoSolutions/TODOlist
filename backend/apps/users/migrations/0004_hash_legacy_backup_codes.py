"""Migra backup codes en claro a SHA-256.

Los códigos generados antes del hashing se guardaban en plaintext en
backup_codes (lista JSON). Cualquier entrada que no sea un hash SHA-256
(64 hex chars) se reemplaza por su hash.
"""
import hashlib

from django.db import migrations


def _hash(code):
    return hashlib.sha256(str(code).strip().upper().encode()).hexdigest()


def forwards(apps, schema_editor):
    TwoFactorSecret = apps.get_model("users", "TwoFactorSecret")
    for tf in TwoFactorSecret.objects.all().iterator():
        codes = tf.backup_codes or []
        new_codes = [
            c if isinstance(c, str) and len(c) == 64 else _hash(c)
            for c in codes
        ]
        if new_codes != codes:
            tf.backup_codes = new_codes
            tf.save(update_fields=["backup_codes"])


def backwards(apps, schema_editor):
    # Irreversible: no se pueden recuperar los códigos en claro
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_twofactorsecret"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
