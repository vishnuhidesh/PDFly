from django.urls import path
from . import views

app_name = 'pdfapp'

urlpatterns = [
    path('', views.index_view, name='index'),
    path('tool/<slug:slug>/', views.tool_view, name='tool'),
    path('api/preview/', views.api_preview, name='api_preview'),
    path('api/process/<slug:slug>/', views.api_process, name='api_process'),
    path('download/<str:file_id>/', views.download_view, name='download'),
    path('api/cleanup/<str:file_id>/', views.api_cleanup, name='api_cleanup'),
]
