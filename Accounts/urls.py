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
    path('signup/resend-otp/', views.resend_signup_otp_view, name='resend_signup_otp'),


    
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('google-login/user/', views.google_login_user, name='google_login_user'),
    path('google-login/admin/', views.google_login_admin, name='google_login_admin'),
    
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('forgot-password/resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    path('reset-password/', views.reset_password_view, name='reset_password'),
    
    path("addresses/", views.address_list, name="address_list"),
    path("addresses/add/", views.add_address, name="add_address"),    
    path("addresses/<int:id>/edit/", views.edit_address, name="edit_address" ),
    path("address/edit/<int:id>/", views.edit_address, name="edit_address"),
    path("addresses/<int:id>/delete/", views.delete_address, name="delete_address"),    
    path("addresses/<int:id>/set-default/", views.set_default_address, name="set_default_address"),
    
]