from django.urls import path
from .views import admin_login
from .views import user_management
from .views import product_management

urlpatterns = [
    path('admin-login/', admin_login.admin_login, name='admin_login'),
    path('admin-dashboard/', admin_login.admin_dashboard, name='admin_dashboard'),
    path('admin-logout/', admin_login.admin_logout_view, name='admin_logout'),
    path("admin-users/", user_management.admin_users, name="admin_users"),
    path("admin-users/<int:user_id>/", user_management.view_user, name="view_user"),
    path("admin-users/<int:user_id>/status/", user_management.toggle_user_status, name="toggle_user_status"),
    
    
    path('admin_products/', product_management.product_management, name='admin_products'),
    path('products/delete/<int:product_id>/', product_management.delete_product, name='delete_product'),    
    path('products/add/', product_management.add_product, name='add_product'),
    path('products/edit/<int:product_id>/', product_management.edit_product, name='edit_product'),
    
    
    
    path('categories/', product_management.category_list, name='admin_category'),
    path('categories/add/', product_management.add_category, name='add_category'),
    path('categories/edit/<int:category_id>/', product_management.edit_category, name='edit_category'),
    path('categories/delete/<int:category_id>/', product_management.delete_category, name='delete_category'),
    
    
    path('products/<int:product_id>/variants/', product_management.manage_variants, name='manage_variants'),
    path('products/<int:product_id>/variants/add/', product_management.add_variant, name='add_variant'),
    path('variants/<int:variant_id>/edit/', product_management.edit_variant, name='edit_variant'),
    path('variant/<int:variant_id>/toggle/', product_management.toggle_variant_status, name='toggle_variant_status'),
    path('variants/<int:variant_id>/delete/', product_management.delete_variant, name='delete_variant'),
    
    path('products/<int:product_id>/toggle/', product_management.toggle_product_status, name='toggle_product_status'),
]
