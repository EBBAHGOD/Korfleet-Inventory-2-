from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.forms import ValidationError
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
    

    
    name = models.CharField(max_length=200, help_text="Item name (required)")
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, help_text="Category (required)")
    quantity = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    date_added = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_items')
    
    class Meta:
        ordering = ['-date_added']
        verbose_name = "Inventory Item"
        verbose_name_plural = "Inventory Items"
    
    def __str__(self):
        return f"{self.name} ({self.category})"
    
    @property
    def total_qty(self):
        """Return the total number of units for this item.

        If there are any serialized rows we consider those to be the
        authoritative stock level; the legacy ``quantity`` field is used
        only when no serialized items exist.  This mirrors the behaviour of
        the admin interface and avoids double‑counting older data.
        """
        serialized_count = self.serialized_items.count()
        if serialized_count:
            return serialized_count
        return self.quantity

    def available_quantity(self):
        """Number of units to *display* as available for this item.

        The visible inventory count should show only those serialized units
        that are **both not faulty and currently available**; once a serial
        is issued it is no longer considered part of the on‑hand stock.
        Legacy ``quantity`` values are used only when no serialized records
        exist, preserving behaviour for older rows.
        """
        qs = self.serialized_items
        if qs.exists():
            # only currently available, non‑faulty serials
            return qs.filter(status='Available').exclude(condition='Faulty').count()
        return self.quantity

    def usable_quantity(self):
        """Count units that can actually be issued.

        Only serials marked ``Available`` and not ``Faulty`` count.  In the
        absence of serialized records we fall back to the legacy ``quantity``
        field to keep earlier behaviour intact.
        """
        qs = self.serialized_items
        if qs.exists():
            return qs.filter(status='Available').exclude(condition='Faulty').count()
        return self.quantity

    def report_quantity(self):
        """Quantity used in reports and dashboard opening/closing calculations.

        For reporting purposes *all* serialized items are considered part of
        the stock, including those marked faulty.  This ensures the numbers
        never drop below zero and aligns with legal/inventory audit
        requirements.  Legacy ``quantity`` is used only when no serials
        exist at all.
        """
        qs = self.serialized_items
        if qs.exists():
            return qs.count()
        return self.quantity

    



class SerializedItem(models.Model):
    """Model for tracking individual items with unique identifiers"""
    
    CONDITION_CHOICES = [
        ('New', 'New'),
        ('Used', 'Used'),
        ('Faulty', 'Faulty'),
    ]
    
    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Issued', 'Issued'),
    ]
    
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='serialized_items')
    imei = models.CharField(max_length=20, unique=True, help_text="Unique IMEI/Serial number")
    date_added = models.DateTimeField(default=timezone.now)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    brand = models.CharField(max_length=100, null=True, blank=True, help_text="Manufacturer/brand (optional)")
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='New')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_serialized_items')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date_added']
        verbose_name = "Serialized Item"
        verbose_name_plural = "Serialized Items"
    
    def __str__(self):
        return f"{self.inventory_item.name} - {self.imei} ({self.condition})"

    
    def save(self, *args, **kwargs):
        # Validate IMEI uniqueness
        if self.pk:
            # Editing - check if IMEI is being changed
            existing = SerializedItem.objects.filter(imei=self.imei).exclude(pk=self.pk)
        else:
            # Creating - check if IMEI already exists
            existing = SerializedItem.objects.filter(imei=self.imei)
        
        if existing.exists():
            raise ValidationError(f"IMEI {self.imei} already exists in the system.")
        
        super().save(*args, **kwargs)


# ---------- user profile for password forcing ----------

class UserProfile(models.Model):
    """Extra data attached to each User."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    force_password_change = models.BooleanField(
        default=True,
        help_text="When True the middleware will redirect the user to set a new password."
    )

    def __str__(self):
        return f"Profile for {self.user.username}"


# signals: create profile on user creation and flag on password change
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=User)
def _cache_old_password(sender, instance, **kwargs):
    # remember the old hash so post_save can detect a change
    if instance.pk:
        try:
            instance._old_password = User.objects.get(pk=instance.pk).password
        except User.DoesNotExist:
            instance._old_password = None


@receiver(post_save, sender=User)
def ensure_profile_and_flag(sender, instance, created, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    if created:
        profile.force_password_change = True
        profile.save()
    else:
        if hasattr(instance, '_old_password') and instance._old_password != instance.password:
            profile.force_password_change = True
            profile.save()


# a lightweight profile attached to each user; keeps track of whether the
# user must choose a new password before using the rest of the system.
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    force_password_change = models.BooleanField(
        default=True,
        help_text="If True the user will be redirected to change their password on next login."
    )

    def __str__(self):
        return f"Profile for {self.user.username}"


# Signals to create profile automatically and to mark the profile flag when
# a password is updated.
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver


@receiver(pre_save, sender=User)
def _cache_old_password(sender, instance, **kwargs):
    # store the current password on the instance so post_save can compare it
    if instance.pk:
        try:
            instance._old_password = User.objects.get(pk=instance.pk).password
        except User.DoesNotExist:
            instance._old_password = None


@receiver(post_save, sender=User)
def ensure_profile_and_flag(sender, instance, created, **kwargs):
    profile, _ = UserProfile.objects.get_or_create(user=instance)
    if created:
        # brand‑new account always forces a reset
        profile.force_password_change = True
        profile.save()
    else:
        # if the password changed since pre_save, force a reset on next login
        if hasattr(instance, '_old_password') and instance._old_password != instance.password:
            profile.force_password_change = True
            profile.save()


class InventoryTransaction(models.Model):
    """Model for tracking inventory usage/stock-out transactions"""
    
    TRANSACTION_TYPES = [
        ('OUT', 'Stock Out'),
        ('IN', 'Stock In'),
    ]
    
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='transactions')
    serialized_item = models.ForeignKey(SerializedItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions')
    transaction_type = models.CharField(max_length=3, choices=TRANSACTION_TYPES, default='OUT')
    quantity = models.IntegerField(validators=[MinValueValidator(1)], default=1)
    date_taken = models.DateTimeField(default=timezone.now)
    purpose = models.TextField(null=True, blank=True, help_text="Reason/purpose for transaction")
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='issued_transactions')
    notes = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-date_taken']
        verbose_name = "Inventory Transaction"
        verbose_name_plural = "Inventory Transactions"
    
    def __str__(self):
        if self.serialized_item:
            return f"{self.transaction_type} - {self.serialized_item} on {self.date_taken.date()}"
        return f"{self.transaction_type} - {self.item.name} x{self.quantity} on {self.date_taken.date()}"
    
    def save(self, *args, **kwargs):
        if not self.pk:
            if self.transaction_type == 'OUT':
                # For stock out, mark serialized item as issued
                if self.serialized_item:
                    if self.serialized_item.status != 'Available':
                        raise ValidationError(f"Item {self.serialized_item.imei} is not available.")
                    self.serialized_item.status = 'Issued'
                    self.serialized_item.save()
                else:
                    # Legacy: bulk quantity based out
                    if self.quantity > self.item.quantity:
                        raise ValidationError("Insufficient stock.")
                    self.item.quantity -= self.quantity
                    self.item.save()
            else:  # IN
                # For stock in with serialized item
                if self.serialized_item:
                    self.serialized_item.status = 'Available'
                    self.serialized_item.save()
                else:
                    # Legacy: bulk quantity based in
                    self.item.quantity += self.quantity
                    self.item.save()

        super().save(*args, **kwargs)