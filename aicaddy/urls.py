"""
Main URL configuration for the aicaddy project.
This file includes the URLs from the caddy application.
"""
from django.contrib import admin
from django.urls import path, include # Make sure 'include' is imported

urlpatterns = [
    path('admin/', admin.site.urls),
    # This line tells Django that for any URL that isn't '/admin/',
    # it should look for further instructions in the 'caddy.urls' file.
    path('', include('caddy.urls')), 
]