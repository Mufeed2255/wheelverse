from django.urls import path

from . import views


urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("checkout/add-address/", views.checkout_add_address, name="checkout_add_address"),
    path("checkout/apply-coupon/", views.apply_coupon, name="apply_coupon"),
    path("checkout/remove-coupon/", views.remove_coupon, name="remove_coupon"),
    path("place-order/", views.place_order, name="place_order"),

    path("payment/<int:order_id>/", views.payment_view, name="payment"),
    path("confirm-payment/<int:order_id>/", views.confirm_payment, name="confirm_payment"),
    path("verify-razorpay/<int:order_id>/", views.verify_razorpay_payment, name="verify_razorpay_payment"),

    path("success/<int:order_id>/", views.order_success, name="order_success"),
    path("failed/", views.order_failed, name="order_failed"),
    path("failed/<int:order_id>/", views.order_failed, name="order_failed_with_order"),

    path("my-orders/", views.my_orders, name="my_orders"),
    path("detail/<int:order_id>/", views.order_detail, name="order_detail"),
    path("invoice/<int:order_id>/", views.download_invoice, name="download_invoice"),

    path("cancel-item/<int:item_id>/", views.cancel_order_item, name="cancel_order_item"),
    path("cancel/<int:order_id>/", views.cancel_order, name="cancel_order"),

    path("return/<int:order_id>/", views.return_order, name="return_order"),
    path("return-item/<int:item_id>/", views.return_order_item, name="return_order_item"),

    path("review/<int:item_id>/", views.add_product_review, name="add_product_review"),
]