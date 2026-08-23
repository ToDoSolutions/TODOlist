from django.contrib import admin

from .models import Task, Subtask, Comment


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "state", "priority", "due_date", "project")
    list_filter = ("state", "priority", "project")
    search_fields = ("title", "description")
    date_hierarchy = "due_date"


@admin.register(Subtask)
class SubtaskAdmin(admin.ModelAdmin):
    list_display = ("title", "task", "is_done", "order")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "created_at")
    search_fields = ("body",)
