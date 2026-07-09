from django.db import models
from django.conf import settings
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']  

    def __str__(self):
        return self.name


class Product(models.Model):
    RARITY_CHOICES = [
        ('COMMON', 'Common'),
        ('RARE', 'Rare'),
        ('EPIC', 'Epic'),
        ('LEGENDARY', 'Legendary'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, unique=True, help_text="Unique Stock Keeping Unit")
    
    rarity = models.CharField(max_length=50, choices=RARITY_CHOICES, default='LEGENDARY')
    
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) 
    total_stock = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True) 
    is_deleted = models.BooleanField(default=False)  # Soft Delete ഫീൽഡ്
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.name


# --- 3. PRODUCT IMAGE MODEL (FOR MULTIPLE IMAGES) ---
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/luxury_wheels/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.product.name}"


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    size = models.CharField(max_length=100, help_text="e.g., 20-inch, 21-inch")
    color = models.CharField(max_length=100, help_text="e.g., Rosso Corsa Red, Matte Black")
    
    price = models.DecimalField(max_digits=12, decimal_places=2) 
    stock = models.IntegerField(default=1)
    is_deleted = models.BooleanField(default=False)  
    image = models.ImageField(upload_to='variants/', blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.product.name} - {self.size} ({self.color})"

class ProductVariantImage(models.Model):

    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image = models.ImageField(
        upload_to='variant_images/'
    )

    is_primary = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = ['-is_primary', 'created_at']   # primary image always first

    def __str__(self):
        return f"{self.variant}"

class AdminActivityLog(models.Model):
    ACTION_CHOICES = [
        ('ACTIVATE_USER', 'Activated User'),
        ('DEACTIVATE_USER', 'Deactivated User'),
        ('VIEW_USER', 'Viewed User'),
        ('LOGIN', 'Admin Login'),
        ('LOGOUT', 'Admin Logout'),
        ('OTHER', 'Other Action'),
    ]

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_activity_logs',
        help_text="The admin who performed this action."
    )
    action = models.CharField(
        max_length=30,
        choices=ACTION_CHOICES,
        default='OTHER'
    )
    description = models.CharField(
        max_length=500,
        blank=True,
        help_text="Human-readable description of what happened."
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='action_received_logs',
        help_text="The user this action was performed on (if applicable)."
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Admin Activity Log'
        verbose_name_plural = 'Admin Activity Logs'

    def __str__(self):
       return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.admin.username} → {self.get_action_display()}"
 
 
 
class Order(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("CONFIRMED", "Confirmed"),
        ("PROCESSING", "Processing"),
        ("SHIPPED", "Shipped"),
        ("DELIVERED", "Delivered"),
        ("CANCELLED", "Cancelled"),
        ("PICKED_UP", "Picked Up"),
        ("RETURN_REQUESTED", "Return Requested"),
        ("RETURN_APPROVED", "Return Approved"),
        ("RETURN_REJECTED", "Return Rejected"),
        ("RETURNED", "Returned"),
    ]

    PAYMENT_CHOICES = [
        ("COD", "Cash On Delivery"),
        ("RAZORPAY", "Razorpay"),
        ("WALLET", "Wallet"),
        ("UPI", "UPI"),
        ("CARD", "Card"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_orders"
    )

    order_id = models.CharField(max_length=30, unique=True, blank=True)

    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)

    address_line = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_CHOICES,
        default="COD"
    )

    payment_status = models.CharField(max_length=20, default="PENDING")

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    cancel_reason = models.TextField(blank=True, null=True)
    return_reason = models.TextField(blank=True, null=True)

    tracking_id = models.CharField(max_length=100, blank=True, null=True)
    courier_partner = models.CharField(max_length=100, blank=True, null=True)

    estimated_delivery = models.DateField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.order_id:
            last_order = Order.objects.order_by("-id").first()
            next_number = 100001 if not last_order else last_order.id + 100001
            self.order_id = f"#WLV-{next_number}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_id


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
    variant_size = models.CharField(max_length=100, blank=True, null=True)
    variant_color = models.CharField(max_length=100, blank=True, null=True)

    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    is_cancelled = models.BooleanField(default=False)
    is_return_requested = models.BooleanField(default=False)
    return_requested_quantity = models.PositiveIntegerField(default=0)
    return_reason = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def item_total(self):
        return self.subtotal

    def __str__(self):
        return f"{self.product_name} x {self.quantity}"
    
class ReturnRequest(models.Model):
    STATUS_CHOICES = (
        ("REQUESTED", "Requested"),
        ("APPROVED", "Approved"),
        ("PICKED_UP", "Picked Up"),
        ("REJECTED", "Rejected"),
        ("REFUNDED", "Refunded"),
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="admin_return_requests"
    )

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="admin_return_requests"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="admin_return_requests"
    )

    return_quantity = models.PositiveIntegerField(default=1)
    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="REQUESTED"
    )

    admin_note = models.TextField(blank=True, null=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    picked_up_at = models.DateTimeField(blank=True, null=True)
    refunded_at = models.DateTimeField(blank=True, null=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.order.order_id} - {self.status}"
    
    
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