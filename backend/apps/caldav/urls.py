from django.urls import path

from .views import caldav_collection, caldav_object, caldav_root

urlpatterns = [
    path("caldav/", caldav_root, name="caldav_root"),
    path("caldav/tasks/", caldav_collection, name="caldav_collection"),
    path("caldav/tasks/<str:name>", caldav_object, name="caldav_object"),
]
