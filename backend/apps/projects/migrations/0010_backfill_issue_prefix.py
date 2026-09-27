from django.db import migrations


def derive_issue_prefix(name):
    """Replica de models.derive_issue_prefix (versión histórica de la
    migración — las migraciones no deben importar código vivo)."""
    words = [w for w in name.split() if w]
    if len(words) >= 2:
        prefix = "".join(w[0] for w in words).upper()
    else:
        prefix = "".join(c for c in name if c.isalnum()).upper()[:3]
    return prefix[:4] or "PRJ"


def backfill_issue_prefix(apps, schema_editor):
    """Deriva ``issue_prefix`` para proyectos existentes que lo tienen
    en blanco. Desambigua colisiones dentro de un mismo owner añadiendo
    un dígito (MP, MP2, MP3…) — el prefijo no es unique a nivel DB pero
    dos proyectos del mismo dueño con la misma sigla serían confusos.
    """
    Project = apps.get_model("projects", "Project")
    seen_by_owner = {}
    for p in Project.objects.filter(issue_prefix="").order_by("owner_id", "id"):
        owner_id = p.owner_id
        used = seen_by_owner.setdefault(owner_id, set())
        # Incluir también los prefijos ya asignados del owner para no
        # chocar con proyectos que sí tenían prefijo explícito.
        if not used:
            used.update(
                Project.objects.filter(owner_id=owner_id)
                .exclude(issue_prefix="")
                .values_list("issue_prefix", flat=True)
            )
        base = derive_issue_prefix(p.name)
        prefix = base
        n = 1
        while prefix in used:
            n += 1
            prefix = f"{base}{n}"[:6]
        Project.objects.filter(pk=p.pk).update(issue_prefix=prefix)
        used.add(prefix)


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0009_project_issue_prefix_projectsection"),
    ]

    operations = [
        migrations.RunPython(
            backfill_issue_prefix, reverse_code=migrations.RunPython.noop
        ),
    ]
