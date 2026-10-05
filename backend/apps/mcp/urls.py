from django.urls import path

from .views import mcp_endpoint

urlpatterns = [
    path("mcp/", mcp_endpoint, name="mcp_endpoint"),
]
