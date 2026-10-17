from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("upload/", views.upload, name="upload"),
    path("upload/detect/", views.upload_detect, name="upload_detect"),
    path("documents/<int:pk>/", views.document, name="document"),
    path("documents/<int:pk>/edit/", views.edit_details, name="edit_details"),
    path("documents/<int:pk>/delete/", views.delete_document, name="delete_document"),
    path("documents/<int:pk>/pages/<int:number>/", views.document, name="document_page"),
    path("documents/<int:pk>/pages/<int:number>/retry/", views.page_retry, name="page_retry"),
    path("documents/<int:pk>/pdf/", views.document_pdf, name="document_pdf"),
]
