from django.db import models
from django.conf import settings
from adminpanel.models import ProductVariant
from decimal import Decimal
import uuid


class Cart(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="cart_items"
    )

    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "variant")

    def subtotal(self):
        return self.variant.price * self.quantity

    def __str__(self):
        return f"{self.user} - {self.variant}"


class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             related_name="wishlist_items")
    variant = models.ForeignKey(ProductVariant,
                            on_delete=models.CASCADE, 
                            related_name="wishlist_items")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "variant")

    def __str__(self):
        return f"{self.user} - {self.variant}"

