# Accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
   
    path('', views.landing_page, name='landing_page'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile_view'),
    path('profile/change-email/', views.change_email_view, name='change_email'),
    path('profile/change-email/verify/', views.change_email_otp_view, name='change_email_otp'),
    path('profile/change-email/resend/', views.resend_email_change_otp_view, name='resend_email_change_otp'),
    path('profile/change-password/', views.change_profile_password_view, name='change_profile_pass'),   
  
    path('signup/', views.signup_view, name='signup'),
    path('signup-verify/', views.signup_verify_view, name='signup_verify'),
    
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('resend-otp/', views.resend_signup_otp_view, name='resend_otp'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    
    path("addresses/", views.address_list, name="address_list"),
    path("addresses/add/", views.add_address, name="add_address"),    
    path("addresses/<int:id>/edit/", views.edit_address, name="edit_address" ),
    path("addresses/<int:id>/delete/", views.delete_address, name="delete_address"),    
    path("addresses/<int:id>/set-default/", views.set_default_address, name="set_default_address"),
    
   
    path("collections/", views.user_collections, name="collections"),
    path("product/<int:product_id>/", views.product_detail, name="product_detail"),

    path("cart/", views.cart_view, name="cart"),
    path("cart/add/", views.add_to_cart, name="add_to_cart"),
    path("cart/increase/<int:item_id>/", views.increase_cart_item, name="increase_cart_item"),
    path("cart/decrease/<int:item_id>/", views.decrease_cart_item, name="decrease_cart_item"),
    path("cart/remove/<int:item_id>/", views.remove_cart_item, name="remove_cart_item"),
    
    path("wishlist/", views.wishlist_view, name="wishlist"),
    path("wishlist/add/", views.add_to_wishlist, name="add_to_wishlist"),
    path("wishlist/remove/<int:item_id>/", views.remove_wishlist, name="remove_wishlist"),
    path("wishlist/move-to-cart/<int:item_id>/", views.move_wishlist_to_cart, name="move_wishlist_to_cart"),
]
