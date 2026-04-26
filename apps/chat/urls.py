from __future__ import annotations

from django.urls import path

from apps.chat import views

app_name = "chat"

urlpatterns = [
    path("", views.chat_list, name="list"),
    path("new/", views.new_conversation, name="new"),
    path("<uuid:conversation_id>/", views.chat_detail, name="detail"),
    path(
        "<uuid:conversation_id>/messages/",
        views.send_message,
        name="send_message",
    ),
]
