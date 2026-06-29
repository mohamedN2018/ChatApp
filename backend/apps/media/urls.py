"""Media routes (mounted under /api/v1/media/)."""

from __future__ import annotations

from django.urls import path

from . import views

app_name = "media"

urlpatterns = [
    path("", views.MediaListView.as_view(), name="list"),
    path("upload/", views.DirectUploadView.as_view(), name="upload"),
    # Chunked / resumable upload
    path("uploads/", views.StartUploadView.as_view(), name="upload-start"),
    path("uploads/<uuid:upload_id>/", views.UploadSessionView.as_view(), name="upload-session"),
    path(
        "uploads/<uuid:upload_id>/chunks/<int:index>/",
        views.UploadChunkView.as_view(),
        name="upload-chunk",
    ),
    path(
        "uploads/<uuid:upload_id>/complete/",
        views.CompleteUploadView.as_view(),
        name="upload-complete",
    ),
    # Keep last so it doesn't shadow the literal paths above.
    path("<uuid:media_id>/", views.MediaDetailView.as_view(), name="detail"),
]
