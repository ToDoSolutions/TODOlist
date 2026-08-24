from django.conf import settings
from django.db import models


class Objective(models.Model):
    """An Objective (OKR) tracked over a quarter of a year."""

    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("in_progress", "In Progress"),
        ("achieved", "Achieved"),
        ("missed", "Missed"),
    ]

    QUARTER_CHOICES = [
        ("Q1", "Q1"),
        ("Q2", "Q2"),
        ("Q3", "Q3"),
        ("Q4", "Q4"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="objectives",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    quarter = models.CharField(max_length=2, choices=QUARTER_CHOICES)
    year = models.IntegerField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="planned"
    )
    progress = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-quarter", "-created_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.quarter} {self.year})"


class KeyResult(models.Model):
    """A measurable key result that contributes to an Objective."""

    UNIT_CHOICES = [
        ("count", "Count"),
        ("percentage", "Percentage"),
        ("days", "Days"),
    ]

    objective = models.ForeignKey(
        Objective,
        on_delete=models.CASCADE,
        related_name="key_results",
    )
    title = models.CharField(max_length=255)
    target_value = models.FloatField(default=0)
    current_value = models.FloatField(default=0)
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default="count")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="key_results",
    )
    due_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title


class KeyResultUpdate(models.Model):
    """A historical record of a value change on a KeyResult."""

    key_result = models.ForeignKey(
        KeyResult,
        on_delete=models.CASCADE,
        related_name="updates",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="key_result_updates",
    )
    old_value = models.FloatField()
    new_value = models.FloatField()
    note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Update for {self.key_result}: {self.old_value} -> {self.new_value}"
