from django.urls import path

from .views import (
    wallet_view,
    add_money,
    verify_wallet_payment,
    wallet_payment_success,
    wallet_payment_failed,
)

urlpatterns = [
    path("", wallet_view, name="wallet"),
    path("add-money/", add_money, name="add_money"),
    path("verify-payment/", verify_wallet_payment, name="verify_wallet_payment"),
    path("payment-success/<int:txn_id>/", wallet_payment_success, name="wallet_payment_success"),
    path("payment-failed/<int:txn_id>/", wallet_payment_failed, name="wallet_payment_failed"),
]