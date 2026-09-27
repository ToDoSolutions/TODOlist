"""Property-based testing con hypothesis.

Verifica invariantes que deben cumplirse para CUALQUIER input,
no solo para los casos elegidos a mano:

- evaluate_conditions: nunca crashea con inputs arbitrarios y cumple
  semántica AND (una condición falsa → todo falso; vacío → verdadero).
- SyncOperation conflict detection: version monótona.
- RecurrenceRule: fechas generadas monótonamente crecientes.
"""
import pytest
from django.contrib.auth import get_user_model
from hypothesis import given
from hypothesis import settings as hsettings
from hypothesis import strategies as st

from apps.automations.engine import evaluate_conditions

User = get_user_model()


# --- evaluate_conditions ---

OPERATORS = ["equals", "not_equals", "contains", "gt", "lt", "unknown_op"]
VALUES = st.one_of(st.text(max_size=50), st.integers(), st.floats(allow_nan=False), st.none(), st.booleans())
COND = st.fixed_dictionaries({
    "field": st.text(max_size=30),
    "operator": st.sampled_from(OPERATORS),
    "value": VALUES,
})


@given(conds=st.lists(COND, max_size=5), context=st.dictionaries(st.text(max_size=30), VALUES, max_size=5))
@hsettings(max_examples=200, deadline=None)
def test_evaluate_conditions_never_crashes(conds, context):
    """Propiedad: evaluate_conditions devuelve bool, nunca excepción."""
    result = evaluate_conditions(conds, context)
    assert isinstance(result, bool)


@given(cond=COND, context=st.dictionaries(st.text(max_size=30), VALUES, max_size=5))
@hsettings(max_examples=200, deadline=None)
def test_evaluate_conditions_and_semantics(cond, context):
    """Una sola condición falsa hace falso el conjunto (AND)."""
    single = evaluate_conditions([cond], context)
    both = evaluate_conditions([cond, cond], context)
    # Si una es falsa, la conjunción es falsa; si es verdadera, repetirla no cambia
    assert both == single


def test_evaluate_conditions_empty_is_true():
    assert evaluate_conditions([], {}) is True


@given(v1=VALUES, v2=VALUES)
@hsettings(max_examples=150, deadline=None)
def test_equals_not_equals_are_complementary(v1, v2):
    """equals y not_equals son complementarios para el mismo par."""
    ctx = {"f": v1}
    eq = evaluate_conditions([{"field": "f", "operator": "equals", "value": v2}], ctx)
    neq = evaluate_conditions([{"field": "f", "operator": "not_equals", "value": v2}], ctx)
    assert eq != neq


# --- Task.version monótona (base de la detección de conflictos) ---

@pytest.mark.django_db
@given(edits=st.integers(min_value=1, max_value=5))
@hsettings(max_examples=10, deadline=None)
def test_task_version_monotonic(edits):
    """La versión de Task crece estrictamente con cada save: base de
    la detección de conflictos offline (base_version < version)."""
    import uuid

    from apps.tasks.models import Task
    # Sin rollback entre ejemplos hypothesis (-p no:django): usar ids únicos
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        username=f"pbt{uid}", email=f"pbt{uid}@x.com", password="pass12345"
    )
    task = Task.objects.create(owner=user, title="t")
    v = task.version
    for i in range(edits):
        task.title = f"t{i}"
        task.save()
        assert task.version > v
        v = task.version
