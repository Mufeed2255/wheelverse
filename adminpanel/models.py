from django.db import models
from django.conf import settings

# --- 1. CATEGORY MODEL ---
class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True) 
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']  

    def __str__(self):
        return self.name


# --- 2. PRODUCT MODEL ---
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


# --- 4. PRODUCT VARIANT MODEL (FIXED TYPO & RELATION) ---
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


# --- 5. ADMIN ACTIVITY LOG MODEL ---
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