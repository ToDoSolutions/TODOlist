from rest_framework import serializers

from .models import WikiPage


class WikiPageSerializer(serializers.ModelSerializer):
    children_count = serializers.SerializerMethodField()
    updated_by_email = serializers.CharField(
        source="updated_by.email", read_only=True
    )

    class Meta:
        model = WikiPage
        fields = [
            "id", "title", "content", "project", "parent",
            "is_published", "version", "children_count",
            "updated_by_email", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "version", "created_at", "updated_at"]

    def get_children_count(self, obj):
        # Usa la anotación del queryset si existe (evita N+1 en list)
        ann = getattr(obj, "children_count_ann", None)
        return ann if ann is not None else obj.children.count()

    def validate_parent(self, value):
        """Evita ciclos triviales: la página no puede ser su propio padre."""
        if self.instance and value and value.id == self.instance.id:
            raise serializers.ValidationError(
                "Una página no puede ser su propio padre."
            )
        return value

    def validate(self, data):
        """El padre debe pertenecer al mismo proyecto."""
        project = data.get("project", getattr(self.instance, "project", None))
        parent = data.get("parent", getattr(self.instance, "parent", None))
        if parent and parent.project_id != (project.id if project else None):
            raise serializers.ValidationError(
                {"parent": "La página padre debe ser del mismo proyecto."}
            )
        return data
