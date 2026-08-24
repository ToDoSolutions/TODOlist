from rest_framework import serializers

from .models import Project


class ProjectSerializer(serializers.ModelSerializer):
    tasks_count = serializers.SerializerMethodField()
    sprints_count = serializers.SerializerMethodField()
    epics_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id", "name", "description", "color",
            "is_archived", "tasks_count", "sprints_count", "epics_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_tasks_count(self, obj):
        return obj.tasks.count()

    def get_sprints_count(self, obj):
        return obj.sprints.count()

    def get_epics_count(self, obj):
        return obj.epics.count()
