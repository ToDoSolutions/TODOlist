from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_archived", "created_at")
    list_filter = ("is_archived",)
    search_fields = ("name", "description")
