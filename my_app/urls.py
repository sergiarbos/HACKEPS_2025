from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('formulari/', views.form_view, name='formulari'),
    path('resultat/', views.result_view, name='resultat'),
]
