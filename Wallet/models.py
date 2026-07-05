import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} Wallet - ₹{self.balance}"


class WalletTransaction(models.Model):
    TYPE_CHOICES = (
        ("CREDIT", "Credit"),
        ("DEBIT", "Debit"),
    )

    PURPOSE_CHOICES = (
        ("CANCEL_REFUND", "Cancel Refund"),
        ("RETURN_REFUND", "Return Refund"),
        ("WALLET_PAYMENT", "Wallet Payment"),
        ("ADMIN_ADJUSTMENT", "Admin Adjustment"),
    )

    STATUS_CHOICES = (
        ("COMPLETED", "Completed"),
        ("PENDING", "Pending"),
        ("FAILED", "Failed"),
    )

    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions"
    )

    order = models.ForeignKey(
        "Orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions"
    )

    return_request = models.ForeignKey(
        "Orders.ReturnRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wallet_transactions"
    )

    transaction_id = models.CharField(max_length=40, unique=True, editable=False)
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    purpose = models.CharField(max_length=30, choices=PURPOSE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="COMPLETED")
    description = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=120, unique=True, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            self.transaction_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction_id} - {self.transaction_type} - ₹{self.amount}"