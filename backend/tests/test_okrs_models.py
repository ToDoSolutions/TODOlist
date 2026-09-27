import pytest
from django.contrib.auth import get_user_model

from apps.okrs.models import KeyResult, KeyResultUpdate, Objective

User = get_user_model()


@pytest.mark.django_db
class TestOkrsModels:
    @pytest.fixture(autouse=True)
    def setup_data(self, db):
        self.user = User.objects.create_user(username="om", email="om@om.com", password="pass")

    def test_objective_str(self):
        o = Objective.objects.create(owner=self.user, title="Obj1", quarter="Q1", year=2024)
        assert "Obj1" in str(o)
        assert "Q1" in str(o)
        assert "2024" in str(o)

    def test_objective_choices(self):
        assert Objective.STATUS_CHOICES == [
            ("planned", "Planned"),
            ("in_progress", "In Progress"),
            ("achieved", "Achieved"),
            ("missed", "Missed"),
        ]
        assert Objective.QUARTER_CHOICES == [
            ("Q1", "Q1"),
            ("Q2", "Q2"),
            ("Q3", "Q3"),
            ("Q4", "Q4"),
        ]

    def test_objective_defaults(self):
        o = Objective.objects.create(owner=self.user, title="Obj1", quarter="Q1", year=2024)
        assert o.status == "planned"
        assert o.progress == 0
        assert o.description == ""

    def test_key_result_str(self):
        o = Objective.objects.create(owner=self.user, title="Obj1", quarter="Q1", year=2024)
        kr = KeyResult.objects.create(objective=o, owner=self.user, title="KR1")
        assert str(kr) == "KR1"

    def test_key_result_choices(self):
        assert KeyResult.UNIT_CHOICES == [
            ("count", "Count"),
            ("percentage", "Percentage"),
            ("days", "Days"),
        ]

    def test_key_result_defaults(self):
        o = Objective.objects.create(owner=self.user, title="Obj1", quarter="Q1", year=2024)
        kr = KeyResult.objects.create(objective=o, owner=self.user, title="KR1")
        assert kr.target_value == 0
        assert kr.current_value == 0
        assert kr.unit == "count"

    def test_key_result_update_str(self):
        o = Objective.objects.create(owner=self.user, title="Obj1", quarter="Q1", year=2024)
        kr = KeyResult.objects.create(objective=o, owner=self.user, title="KR1")
        u = KeyResultUpdate.objects.create(key_result=kr, user=self.user, old_value=0, new_value=50)
        assert "Update for" in str(u)
        assert "0" in str(u)
        assert "50" in str(u)

    def test_key_result_update_defaults(self):
        o = Objective.objects.create(owner=self.user, title="Obj1", quarter="Q1", year=2024)
        kr = KeyResult.objects.create(objective=o, owner=self.user, title="KR1")
        u = KeyResultUpdate.objects.create(key_result=kr, user=self.user, old_value=0, new_value=50)
        assert u.note == ""
