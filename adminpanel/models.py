
from django.utils import timezone
from django.db import models
from django.conf import settings
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import Q


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


class Product(models.Model):
    RARITY_CHOICES = [
        ("COMMON", "Common"),
        ("RARE", "Rare"),
        ("EPIC", "Epic"),
        ("LEGENDARY", "Legendary"),
    ]

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products"
    )

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, unique=True)

    rarity = models.CharField(
        max_length=50,
        choices=RARITY_CHOICES,
        default="LEGENDARY"
    )

    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_stock = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants"
    )

    size = models.CharField(max_length=100)
    color = models.CharField(max_length=100)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    stock = models.IntegerField(default=1)
    is_deleted = models.BooleanField(default=False)

    image = models.ImageField(
        upload_to="variants/",
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - {self.size} ({self.color})"


class ProductVariantImage(models.Model):
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="images"
    )

    image = models.ImageField(upload_to="variant_images/")
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_primary", "created_at"]

    def __str__(self):
        return str(self.variant)


class AdminActivityLog(models.Model):
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_activity_logs"
    )

    action = models.CharField(max_length=30)
    description = models.CharField(
        max_length=500,
        blank=True
    )

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="action_received_logs"
    )

    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.admin} - {self.action}"
    
    
class Coupon(models.Model):
    DISCOUNT_TYPE_CHOICES = (
        ("PERCENTAGE", "Percentage"),
        ("FIXED", "Fixed Amount"),
    )

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, unique=True)

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default="PERCENTAGE"
    )

    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    min_cart_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    usage_limit = models.PositiveIntegerField(default=0)
    used_count = models.PositiveIntegerField(default=0)

    valid_from = models.DateField(default=timezone.now)
    valid_till = models.DateField()

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return self.valid_till < timezone.now().date()

    def __str__(self):
        return self.code


class Offer(models.Model):
    OFFER_TYPE_CHOICES = (
        ("PRODUCT", "Product Based"),
        ("CATEGORY", "Category Based"),
    )

    DISCOUNT_TYPE_CHOICES = (
        ("PERCENTAGE", "Percentage"),
        ("FIXED", "Fixed Amount"),
    )

    title = models.CharField(max_length=120)

    offer_type = models.CharField(
        max_length=20,
        choices=OFFER_TYPE_CHOICES,
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="offers",
        null=True,
        blank=True,
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="offers",
        null=True,
        blank=True,
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default="PERCENTAGE",
    )

    discount_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    start_date = models.DateField()
    end_date = models.DateField()

    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

        indexes = [
            models.Index(
                fields=[
                    "offer_type",
                    "is_active",
                    "is_deleted",
                ]
            ),
            models.Index(
                fields=[
                    "start_date",
                    "end_date",
                ]
            ),
        ]

        constraints = [
            models.CheckConstraint(
                condition=Q(discount_value__gt=0),
                name="offer_discount_value_gt_zero",
            ),
        ]

    def clean(self):
        errors = {}

        if self.offer_type == "PRODUCT":
            if not self.product_id:
                errors["product"] = (
                    "Select a product for a product-based offer."
                )

            if self.category_id:
                errors["category"] = (
                    "Category must be empty for a product-based offer."
                )

        elif self.offer_type == "CATEGORY":
            if not self.category_id:
                errors["category"] = (
                    "Select a category for a category-based offer."
                )

            if self.product_id:
                errors["product"] = (
                    "Product must be empty for a category-based offer."
                )

        if (
            self.start_date
            and self.end_date
            and self.end_date < self.start_date
        ):
            errors["end_date"] = (
                "End date must be on or after the start date."
            )

        if self.discount_type == "PERCENTAGE":
            if (
                self.discount_value is not None
                and self.discount_value > Decimal("90.00")
            ):
                errors["discount_value"] = (
                    "Percentage discount cannot exceed 90%."
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.offer_type == "PRODUCT":
            self.category = None

        elif self.offer_type == "CATEGORY":
            self.product = None

        self.full_clean()

        super().save(*args, **kwargs)

    @property
    def target_name(self):
        if (
            self.offer_type == "PRODUCT"
            and self.product
        ):
            return self.product.name

        if (
            self.offer_type == "CATEGORY"
            and self.category
        ):
            return self.category.name

        return "No target"

    @property
    def status_label(self):
        today = timezone.localdate()

        if self.is_deleted:
            return "DELETED"

        if not self.is_active:
            return "INACTIVE"

        if self.start_date > today:
            return "UPCOMING"

        if self.end_date < today:
            return "EXPIRED"

        return "ACTIVE"

    def __str__(self):
        return self.title