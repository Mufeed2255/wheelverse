from django.urls import path
from .views import admin_login
from .views import user_management
from .views import product_management
from .views.order_management import (
    admin_orders,
    admin_order_detail,
    admin_update_order_status,
    admin_cancel_order,
    admin_returns,
    return_action_page,
    approve_return,     
    reject_return,      
    process_refund,  
    admin_return_detail,
    mark_return_picked_up,   
)
from adminpanel.views.coupon_management import (
    admin_coupons,
    add_coupon,
    delete_coupon_confirm,
    edit_coupon,
    delete_coupon,
)

from .views.sales_report import export_sales_excel, export_sales_pdf, sales_report




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
    path('products/<int:product_id>/toggle/', product_management.toggle_product_status, name='toggle_product_status'),
    
    
    path('categories/', product_management.category_list, name='admin_category'),
    path('categories/add/', product_management.add_category, name='add_category'),
    path('categories/edit/<int:category_id>/', product_management.edit_category, name='edit_category'),
    path('categories/delete/<int:category_id>/', product_management.delete_category, name='delete_category'),
    
    
    path('products/<int:product_id>/variants/', product_management.manage_variants, name='manage_variants'),
    path('products/<int:product_id>/variants/add/', product_management.add_variant, name='add_variant'),
    path('variants/<int:variant_id>/edit/', product_management.edit_variant, name='edit_variant'),
    path('variant/<int:variant_id>/toggle/', product_management.toggle_variant_status, name='toggle_variant_status'),
    path('variants/<int:variant_id>/delete/', product_management.delete_variant, name='delete_variant'),
    
    path("orders/", admin_orders, name="admin_orders"),
    path("orders/<int:order_id>/", admin_order_detail, name="admin_order_detail"),
    path("orders/<int:order_id>/update-status/", admin_update_order_status, name="admin_update_order_status"),
    path("orders/<int:order_id>/cancel/", admin_cancel_order, name="admin_cancel_order"),
    
    path("admin-returns/", admin_returns, name="admin_returns"),
    path("admin-returns/<int:return_id>/detail/",admin_return_detail,name="admin_return_detail"),
    path("admin-returns/<int:return_id>/action/",return_action_page,name="return_action_page"),

    path("admin-returns/<int:return_id>/approve/", approve_return, name="approve_return"),
    path("admin-returns/<int:return_id>/reject/", reject_return, name="reject_return"),
    path("admin-returns/<int:return_id>/refund/", process_refund, name="process_refund"),
    path("returns/<int:return_id>/picked-up/",mark_return_picked_up,name="mark_return_picked_up"),
         

    path("coupons/", admin_coupons, name="admin_coupons"),
    path("coupons/add/", add_coupon, name="add_coupon"),
    path("coupons/edit/<int:coupon_id>/", edit_coupon, name="edit_coupon"),
    path("coupons/delete-confirm/<int:coupon_id>/", delete_coupon_confirm, name="delete_coupon_confirm"),
    path("coupons/delete/<int:coupon_id>/", delete_coupon, name="delete_coupon"),
    path("sales-report/",sales_report,name="sales_report"),

    path("sales-report/export/excel/",export_sales_excel,name="export_sales_excel"),

    path("sales-report/export/pdf/",export_sales_pdf ,name="export_sales_pdf"),

]
    
