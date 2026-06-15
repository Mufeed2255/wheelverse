from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid
import random
import string
from django.conf import settings
from adminpanel.models import ProductVariant

class CustomUser(AbstractUser):
    user_name = models.CharField(max_length=150, blank=True, null=True)
    
    phone = models.CharField(max_length=15, blank=True, null=True)

    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        blank=True,
        null=True
    )

    referral_code = models.CharField(
        max_length=12, unique=True, blank=True, null=True, 
        help_text="Auto-generated unique referral code for this user."
    )
    referred_by = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='referrals',
        help_text="The user who referred this account."
    )

    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        help_text="IP address captured at account registration."
    )

    @property
    def full_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        return name if name else self.username

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=8)
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.username
    
class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics', blank=True)

    def __str__(self):
        return f'{self.user.username} Profile'
    

class Address(models.Model):
    
    class AddressType(models.TextChoices):
        HOME = "HOME", "Home"
        GARAGE = "GARAGE", "Garage"
        WORK = "WORK", "Work"
        OTHER = "OTHER", "Other"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="addresses",
        help_text="The collector profile owner matching this database node."
    )
    
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=50)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    country = models.CharField(max_length=100, default="INDIA")
    
    address_type = models.CharField(
        max_length=10,
        choices=AddressType.choices,
        default=AddressType.HOME
    )
    
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Address"
        verbose_name_plural = "Addresses"
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.name} - {self.address_type} ({self.city})"
    
    
    class Category(models.Model):
        name = models.CharField(max_length=255)
        slug = models.SlugField(unique=True, blank=True)
        description = models.TextField(blank=True, null=True)
        is_active = models.BooleanField(default=True)
        created_at = models.DateTimeField(auto_now_add=True)
        updated_at = models.DateTimeField(auto_now=True)

        class Meta:
            verbose_name = "Category"
            verbose_name_plural = "Categories"
            ordering = ['name']

        def __str__(self):
            return self.name
    
    
    # --- 2. PRODUCT MODEL ---
class Product(models.Model):
    RARITY_CHOICES = [
        ('COMMON', 'Common'),
        ('RARE', 'Rare'),
        ('ULTRA RARE', 'Ultra Rare'),
        ('LEGENDARY', 'Legendary'),
    ]


    category = models.ForeignKey('Category', on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=50, unique=True, help_text="Unique Stock Keeping Unit")
    rarity = models.CharField(max_length=50, choices=RARITY_CHOICES, default='LEGENDARY')
    
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00) 
    total_stock = models.IntegerField(default=0)
    
    is_active = models.BooleanField(default=True) 
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.name
    
    


class Cart(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "variant")

    def subtotal(self):
        return self.variant.price * self.quantity

    def __str__(self):
        return f"{self.user} - {self.variant}"
    
class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "variant")

    def __str__(self):
        return f"{self.user} - {self.variant}"