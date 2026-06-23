from django.db import models
from django.conf import settings
from adminpanel.models import ProductVariant
 
 
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
# Create your models here.
