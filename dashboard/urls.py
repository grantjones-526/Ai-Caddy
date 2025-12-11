from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Main Application URLs
    path('', views.dashboard_view, name='dashboard'), 
    path('round/add/', views.add_round_view, name='add_round'),
    path('round/<int:round_id>/', views.round_detail_view, name='round_detail'),
    path('load_test_data/', views.load_test_data_view, name='load_test_data'),
    path('clear_all_data/', views.clear_all_data_view, name='clear_all_data'),
    path('recommendations/', views.recommendation_view, name='recommendations'),
    path('recommendations/visualization/', views.recommendation_visualization_view, name='recommendation_visualization'),
    path('import/', views.import_launch_monitor_view, name='import_launch_monitor'),
    path('import/<int:import_id>/confirm/', views.confirm_import_view, name='confirm_import'),
]
