from django.urls import path
from . import views

urlpatterns = [
    path('health/', views.health),
    path('hoy/', views.hoy),
    path('auth/registro/', views.registro),
    path('auth/login/', views.login),
    path('actividades/', views.actividades),
    path('actividades/<str:actividad_id>/', views.actividad_detalle),
    path('actividades/<str:actividad_id>/subtareas/', views.subtareas),
    path('actividades/<str:actividad_id>/subtareas/<str:subtarea_id>/', views.subtarea_detalle),
]