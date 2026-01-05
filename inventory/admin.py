from django.contrib import admin
from .models import InventoryItem, InventoryTransaction


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'brand', 'quantity', 'condition', 'date_added', 'created_by')
    list_filter = ('category', 'condition', 'date_added')
    search_fields = ('name', 'brand', 'imei')
    readonly_fields = ('date_added', 'created_by')
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('item', 'transaction_type', 'quantity', 'date_taken', 'issued_by', 'purpose')
    list_filter = ('transaction_type', 'date_taken', 'item__category')
    search_fields = ('item__name', 'purpose', 'issued_by__username')
    readonly_fields = ('issued_by',)
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)