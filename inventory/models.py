from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone


class InventoryItem(models.Model):
    """Model for inventory items"""
    
    CATEGORY_CHOICES = [
        ('Video Devices (MDVRs)', 'Video Devices (MDVRs)'),
        ('Fuel Level Sensors', 'Fuel Level Sensors'),
        ('SIM Cards', 'SIM Cards'),
        ('Cameras', 'Cameras'),
        ('Accessories', 'Accessories'),
        ('Flow Meters', 'Flow Meters'),
        ('Tracking Devices', 'Tracking Devices'),
    ]
    
    CONDITION_CHOICES = [
        ('New', 'New'),
        ('Used', 'Used'),
        ('Faulty', 'Faulty'),
    ]
    
    name = models.CharField(max_length=200, help_text="Item name (required)")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, help_text="Category (required)")
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True)
    imei = models.CharField(max_length=50, null=True, blank=True, verbose_name="IMEI")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='New')
    quantity = models.IntegerField(default=1, validators=[MinValueValidator(0)])
    date_added = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_items')
    
    class Meta:
        ordering = ['-date_added']
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
    
    def __str__(self):
        return f"{self.name} ({self.category})"
    
    def available_quantity(self):
        """Calculate available quantity after stock-ins and stock-outs"""
        total_in = self.transactions.filter(transaction_type='IN').aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        total_out = self.transactions.filter(transaction_type='OUT').aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        return max(0, self.quantity + total_in - total_out)


class InventoryTransaction(models.Model):
    """Model for tracking inventory usage/stock-out transactions"""
    
    TRANSACTION_TYPES = [
        ('OUT', 'Stock Out'),
        ('IN', 'Stock In'),
    ]
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES, default='OUT')
    quantity = models.IntegerField(validators=[MinValueValidator(1)])
    date_taken = models.DateTimeField(default=timezone.now)
    purpose = models.TextField(null=True, blank=True, help_text="Reason/purpose for transaction")
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_transactions')
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-date_taken']
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"
    
    def __str__(self):
        return f"{self.transaction_type} - {self.item.name} x{self.quantity} on {self.date_taken.date()}"