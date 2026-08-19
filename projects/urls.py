from django.urls import path
from . import views

urlpatterns = [
    path('prueba/', views.interfaz_prueba, name='interfaz_prueba'),
    path('prueba/exportar/', views.pagina_exportar, name='pagina_exportar'),
]