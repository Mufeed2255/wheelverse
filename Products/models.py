from django.db import models
from django.conf import settings
from adminpanel.models import ProductVariant
from decimal import Decimal
import uuid


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE, 
                             related_name="cart_items")
    variant = models.ForeignKey(ProductVariant,
                                on_delete=models.CASCADE,
                                related_name="cart_items")
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


class Order(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("SHIPPED", "Shipped"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("RETURN_REQUESTED", "Return Requested"),
        ("RETURNED", "Returned"),
    )

    PAYMENT_CHOICES = (
        ("COD", "Cash on Delivery"),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, 
                             on_delete=models.CASCADE, 
                             related_name="orders")
    order_id = models.CharField(max_length=30, 
                                unique=True, 
                                editable=False)

    subtotal = models.DecimalField(max_digits=10, 
                                   decimal_places=2, 
                                   default=Decimal("0.00"))
    discount = models.DecimalField(max_digits=10, 
                                   decimal_places=2, 
                                   default=Decimal("0.00"))
    shipping_charge = models.DecimalField(max_digits=10, 
                                          decimal_places=2, 
                                          default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=10, 
                                       decimal_places=2, 
                                       default=Decimal("0.00"))

    payment_method = models.CharField(max_length=20, 
                                      choices=PAYMENT_CHOICES, 
                                      default="COD")
    status = models.CharField(max_length=25, 
                              choices=STATUS_CHOICES, 
                              default="PENDING")

    cancel_reason = models.TextField(blank=True, null=True)
    return_reason = models.TextField(blank=True, null=True)

    ordered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"WLV-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_id


class OrderAddress(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, 
                                 related_name="shipping_address")

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=80)
    state = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.full_name} - {self.order.order_id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, 
                              related_name="items")
    variant = models.ForeignKey(ProductVariant, 
                                on_delete=models.SET_NULL, 
                                null=True, blank=True)

    product_name = models.CharField(max_length=150)
    variant_color = models.CharField(max_length=80, blank=True, null=True)
    variant_size = models.CharField(max_length=80, blank=True, null=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    item_total = models.DecimalField(max_digits=10, decimal_places=2)

    is_cancelled = models.BooleanField(default=False)
    cancel_reason = models.TextField(blank=True, null=True)

    is_return_requested = models.BooleanField(default=False)
    return_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"