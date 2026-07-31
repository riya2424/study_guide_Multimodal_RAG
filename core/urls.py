from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("upload/", views.upload_view, name="upload"),
    path("document/<uuid:doc_id>/", views.document_detail, name="document_detail"),
    path("document/<uuid:doc_id>/chat/", views.chat_view, name="chat"),
    path(
        "document/<uuid:doc_id>/chat/<uuid:session_id>/api/",
        views.chat_api,
        name="chat_api",
    ),
    path("document/<uuid:doc_id>/quiz/", views.quiz_view, name="quiz"),
]
