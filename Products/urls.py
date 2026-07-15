    # Accounts/urls.py
from django.urls import path
from . import views
from Products import views as product_views 


urlpatterns = [
    
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
    path("collections/",views.user_collections,name="collections",),
    path("collections/search-suggestions/",views.product_search_suggestions,name="product_search_suggestions",),
     
]