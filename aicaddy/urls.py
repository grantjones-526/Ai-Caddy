"""
Main URL configuration for the aicaddy project.
This file includes the URLs from the dashboard application.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # This line tells Django that for any URL that isn't '/admin/',
    # it should look for further instructions in the 'dashboard.urls' file.
    path('', include('dashboard.urls')), 
]

# Serve static files during development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # Also serve from STATICFILES_DIRS
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns
    urlpatterns += staticfiles_urlpatterns()