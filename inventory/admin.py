from django.contrib import admin
from .models import InventoryItem, InventoryTransaction, SerializedItem


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'get_item_count', 'date_added', 'created_by')
    list_filter = ('category', 'date_added')
    search_fields = ('name',)
    readonly_fields = ('date_added', 'created_by')
    # hide the legacy quantity field from admin forms; it's no longer used
    exclude = ('quantity',)
    
    def get_item_count(self, obj):
        """Display count of serialized items excluding faulty units.

        This mirrors :meth:`InventoryItem.available_quantity` which is used
        throughout the UI for reporting.  We intentionally ignore the
        ``status`` field here so the admin list shows the same numbers as
        the dashboard and inventory pages.
        """
        return obj.serialized_items.exclude(condition='Faulty').count()
    get_item_count.short_description = 'Available Items'
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(SerializedItem)
class SerializedItemAdmin(admin.ModelAdmin):
    # show the item as the first column; ordering by item groups the
    # entries together automatically.
    list_display = ('inventory_item', 'imei', 'brand', 'condition', 'status', 'price', 'date_added', 'created_by')
    # allow quick filter by inventory item as well as the existing fields
    list_filter = ('inventory_item', 'condition', 'status', 'inventory_item__category', 'date_added')
    search_fields = ('imei', 'inventory_item__name')
    readonly_fields = ('created_at', 'created_by', 'date_added')
    fields = ('inventory_item', 'imei', 'brand', 'price', 'condition', 'status', 'created_by', 'created_at', 'date_added')
    ordering = ('inventory_item__name', 'imei')
    
    # optional: if you really want visual group headers you can override the
    # change_list_template and insert them using Django template logic.  for
    # example, create `templates/admin/inventory/serializeditem/change_list.html`
    # with a `{% regroup cl.result_list by inventory_item as grouped %}` loop
    # and print a header row before each group.  the default behaviour above is
    # often sufficient since the rows appear consecutively.
    # change_list_template = 'admin/inventory/serializeditem/change_list.html'

    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(InventoryTransaction)
class InventoryTransactionAdmin(admin.ModelAdmin):
    list_display = ('get_item_name', 'transaction_type', 'quantity', 'date_taken', 'issued_by', 'purpose')
    list_filter = ('transaction_type', 'date_taken', 'item__category')
    search_fields = ('item__name', 'serialized_item__imei', 'purpose', 'issued_by__username')
    readonly_fields = ('issued_by',)
    fields = ('item', 'serialized_item', 'transaction_type', 'quantity', 'date_taken', 'purpose', 'issued_by', 'notes')
    
    def get_item_name(self, obj):
        """Display item name or serialized item IMEI"""
        if obj.serialized_item:
            return f"{obj.serialized_item.inventory_item.name} ({obj.serialized_item.imei})"
        return obj.item.name
    get_item_name.short_description = 'Item'
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.issued_by = request.user
        super().save_model(request, obj, form, change)