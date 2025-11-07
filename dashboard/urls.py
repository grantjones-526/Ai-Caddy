"""
URL configuration for the caddy app.
This file maps URLs to views for the AI Caddy application.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Main Application URLs
    # The root URL of our app will be the dashboard
    path('', views.dashboard_view, name='dashboard'), 
    path('round/add/', views.add_round_view, name='add_round'),
    path('round/<int:round_id>/', views.round_detail_view, name='round_detail'),
    path('load_test_data/', views.load_test_data_view, name='load_test_data'),
    path('clear_all_data/', views.clear_all_data_view, name='clear_all_data'),
    path('recommendations/', views.recommendation_view, name='recommendations'),
    path('recommendations/visualization/', views.recommendation_visualization_view, name='recommendation_visualization'),
]
