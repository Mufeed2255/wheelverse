from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('Accounts.urls')), 
    path('accounts/', include('allauth.urls')),
    path('adminpanel/', include('adminpanel.urls')),
    path("", include("Products.urls")),
    path('orders/', include('Orders.urls')),
    path('wallet/', include('Wallet.urls')),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    from django.conf import settings
from django.conf.urls.static import static

