from decimal import Decimal
import uuid

from django.conf import settings
from django.db import models

from adminpanel.models import Product, ProductVariant


class Order(models.Model):
    STATUS_CHOICES = [
        ("PAYMENT_PENDING", "Payment Pending"),
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("SHIPPED", "Shipped"),
        ("OUT_FOR_DELIVERY", "Out for Delivery"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("RETURN_REQUESTED", "Return Requested"),
        ("RETURN_APPROVED", "Return Approved"),
        ("RETURN_REJECTED", "Return Rejected"),
        ("RETURNED", "Returned"),
    ]

    PAYMENT_CHOICES = [
        ("COD", "Cash on Delivery"),
        ("WALLET", "Wallet"),
        ("RAZORPAY", "Razorpay"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders"
    )

    order_id = models.CharField(
        max_length=30,
        unique=True,
        editable=False
    )

    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    offer_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    coupon_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    shipping_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default="COD"
    )

    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="PAYMENT_PENDING"
    )

    cancel_reason = models.TextField(
        blank=True,
        null=True
    )

    return_reason = models.TextField(
        blank=True,
        null=True
    )

    razorpay_order_id = models.CharField(
        max_length=120,
        blank=True,
        null=True
    )

    razorpay_payment_id = models.CharField(
        max_length=120,
        blank=True,
        null=True
    )

    razorpay_signature = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    coupon_code = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    ordered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_id:
            self.order_id = f"WLV-{uuid.uuid4().hex[:10].upper()}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_id


class CouponUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )

    coupon = models.ForeignKey(
        "adminpanel.Coupon",
        on_delete=models.CASCADE
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )

    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "coupon", "order"],
                name="unique_coupon_usage_per_order"
            )
        ]

    def __str__(self):
        return f"{self.user} - {self.coupon.code}"


class OrderAddress(models.Model):
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="shipping_address"
    )

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
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_items"
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="variant_order_items"
    )

    product_name = models.CharField(max_length=255)

    variant_color = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    variant_size = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    original_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    offer_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    offer_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    offer_name = models.CharField(
        max_length=120,
        blank=True,
        null=True
    )

    offer_type = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField(default=1)

    # Final amount for this order item.
    item_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    is_cancelled = models.BooleanField(default=False)

    cancelled_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Quantity cancelled by the customer."
    )

    cancel_reason = models.TextField(
        blank=True,
        null=True
    )

    is_return_requested = models.BooleanField(default=False)

    return_requested_quantity = models.PositiveIntegerField(default=0)

    return_reason = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.item_total is None or self.item_total == 0:
            self.item_total = self.price * self.quantity

        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        """
        Compatibility property for old code that uses item.subtotal.
        """
        return self.item_total

    @property
    def active_quantity(self):
        return max(self.quantity - self.cancelled_quantity, 0)

    @property
    def cancelled_amount(self):
        if self.quantity <= 0:
            return Decimal("0.00")

        unit_total = self.item_total / self.quantity
        return (unit_total * self.cancelled_quantity).quantize(
            Decimal("0.01")
        )

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"


class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ("REQUESTED", "Requested"),
        ("APPROVED", "Approved"),
        ("PICKED_UP", "Picked Up"),
        ("REJECTED", "Rejected"),
        ("REFUNDED", "Refunded"),
    ]

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="order_return_requests"
    )

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="order_return_requests"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="order_return_requests"
    )

    return_quantity = models.PositiveIntegerField(default=1)

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="REQUESTED"
    )

    admin_note = models.TextField(
        blank=True,
        null=True
    )

    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00")
    )

    picked_up_at = models.DateTimeField(
        blank=True,
        null=True
    )

    refunded_at = models.DateTimeField(
        blank=True,
        null=True
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return (
            f"{self.order.order_id} - "
            f"Qty {self.return_quantity} - "
            f"{self.status}"
        )


class ReturnRequestImage(models.Model):
    return_request = models.ForeignKey(
        ReturnRequest,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(
        upload_to="return_requests/",
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Image for {self.return_request.order.order_id}"


class ProductReview(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reviews"
    )

    order_item = models.OneToOneField(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="review"
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews"
    )

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews"
    )

    rating = models.PositiveSmallIntegerField()
    review = models.TextField()
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name} - {self.rating} stars"


class ProductReviewImage(models.Model):
    review = models.ForeignKey(
        ProductReview,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(
        upload_to="product_reviews/"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    