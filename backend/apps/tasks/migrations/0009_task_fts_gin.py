"""FTS indexado para Task: columna tsvector persistida + trigger + GIN.

Los índices funcionales sobre ``to_tsvector(...)`` no se usan con queries
parametrizadas (el ORM envía COALESCE(title, $1) y Postgres exige
coincidencia textual). Por eso se materializa la columna ``search_vector``
mantenida por trigger y se indexa con GIN.

La columna no forma parte del estado del modelo (no hay field en Task);
solo existe a nivel BD y se consulta vía expresión raw en el search view.
En SQLite/tests es un no-op.
"""
from django.db import migrations

_SETUP_SQL = """
ALTER TABLE tasks_task ADD COLUMN IF NOT EXISTS search_vector tsvector;

CREATE OR REPLACE FUNCTION tasks_task_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        to_tsvector('spanish'::regconfig,
            coalesce(NEW.title, '') || ' ' || coalesce(NEW.description, ''))
        || to_tsvector('english'::regconfig,
            coalesce(NEW.title, '') || ' ' || coalesce(NEW.description, ''));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tasks_task_search_vector_trigger ON tasks_task;
CREATE TRIGGER tasks_task_search_vector_trigger
    BEFORE INSERT OR UPDATE OF title, description ON tasks_task
    FOR EACH ROW EXECUTE FUNCTION tasks_task_search_vector_update();

UPDATE tasks_task SET search_vector =
    to_tsvector('spanish'::regconfig,
        coalesce(title, '') || ' ' || coalesce(description, ''))
    || to_tsvector('english'::regconfig,
        coalesce(title, '') || ' ' || coalesce(description, ''));

CREATE INDEX IF NOT EXISTS task_fts_gin ON tasks_task USING GIN (search_vector);
"""

_TEARDOWN_SQL = """
DROP TRIGGER IF EXISTS tasks_task_search_vector_trigger ON tasks_task;
DROP FUNCTION IF EXISTS tasks_task_search_vector_update();
DROP INDEX IF EXISTS task_fts_gin;
ALTER TABLE tasks_task DROP COLUMN IF EXISTS search_vector;
"""


def setup(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(_SETUP_SQL)


def teardown(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(_TEARDOWN_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("tasks", "0008_add_assignee_to_task"),
    ]

    operations = [
        migrations.RunPython(setup, teardown),
    ]
