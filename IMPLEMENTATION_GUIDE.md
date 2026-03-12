# Inventory Tracking System - Individual Item Feature Implementation Guide

## Summary of Changes

This implementation adds comprehensive support for tracking individual items with unique identifiers (IMEIs) within your inventory system. The system now operates at both unit level (for aggregated data) and individual item level (for detailed tracking).

---

## Key Changes Made

### 1. **Data Model Updates** (`models.py`)

#### New Model: `SerializedItem`
- Represents individual items with unique identifiers
- Fields:
  - `imei`: Unique identifier (required, must be unique across system)
  - `date_added`: When the item was added
  - `price`: Item price (optional)
  - `condition`: New, Used, or Faulty
  - `status`: Available or Issued
  - `inventory_item`: Foreign key to InventoryItem (the unit type)
  - `created_by`: User who added the item
  - `created_at`: Timestamp of creation

#### Updated Model: `InventoryTransaction`
- Now includes optional `serialized_item` field to track individual items
- When linking to specific items, quantity is automatically 1
- Manages status updates (marking items as Issued when checked out)

### 2. **Database Migration**

A new migration file has been created: `0004_serializeditem_tracking.py`

**To apply the migration:**
```bash
python manage.py migrate
```

### 3. **Admin Interface Updates** (`admin.py`)

- **SerializedItemAdmin**: New admin interface for managing individual items
  - View/filter by condition, status, category, date
  - Search by IMEI or item name
- **InventoryItemAdmin**: Updated to show count of available items
- **InventoryTransactionAdmin**: Updated to display IMEI when transaction involves a serialized item

### 4. **Views Updates** (`views.py`)

#### Stock Out (Issue Items)
- **New Workflow**: Select item type → Select specific IMEI to issue
- Shows list of available items for the selected unit type
- Creates transaction with specific serialized item reference
- Automatically marks item as "Issued"

#### Stock In (Receipt Items)
- **New Workflow**: Select item type → Enter individual item details
- Fields:
  - Item selection (required)
  - IMEI (required, must be unique)
  - Price (optional)
  - Condition (required: New/Used/Faulty)
  - Date Added (optional)
  - Purpose (optional)
- IMEI uniqueness validation prevents duplicates

#### Bulk Upload Feature
- **Download Template**: Excel template for batch imports
- **Bulk Upload**: Upload Excel file with multiple items
- Error handling: Shows success count and detailed error messages
- File format: .xlsx or .xls
- Columns required: Item Name, IMEI, Date Added, Price, Condition

#### Reports Updated
- Shows individual items issued/received (by IMEI)
- Opening and closing balances calculated per item type
- Category-based usage tracking
- Item details visible in transactions

#### Dashboard
- Still displays unit-level data (MDVR count, not individual IMEIs)
- Counts available serialized items instead of quantity field
- Category distribution based on available items

#### Inventory List
- Shows both total items and available items for each unit
- Available count = count of serialized items with status "Available"

### 5. **Updated Templates**

#### `stock_out_form.html`
- Two-step process: Select item type → Select IMEI to issue
- Shows IMEI, condition, and price for each available item
- Dropdown list of available items

#### `stock_in_form.html`
- Form to add individual items with all properties
- Shows example of recently added items for the selected unit
- Links to bulk upload and template download

#### `bulk_upload_form.html` (New)
- Instructions for bulk upload process
- Download template button
- File upload form
- Preview of expected format

#### `transactions.html`
- Updated table to show IMEI column
- Shows condition for individual items
- Better transaction visibility with individual item details

---

## New API Routes

```
/inventory/stock-out/          - Issue individual items
/inventory/stock-in/           - Add individual items
/inventory/bulk-upload/        - Bulk upload interface
/inventory/bulk-upload-template/ - Download Excel template
```

---

## Workflow Guide

### Adding Individual Items (One at a time)
1. Go to "Receipt Stock" page
2. Select the item type (e.g., MDVR)
3. Enter IMEI (must be unique)
4. Enter optional: Price, Condition, Date Added
5. Click "Add Item"

### Adding Items in Bulk
1. Go to "Receipt Stock" → "Bulk Upload Items" or "Download Template"
2. Download Excel template
3. Fill in items with columns: Item Name, IMEI, Date Added, Price, Condition
4. Upload file
5. View results (success/error count)

### Issuing Items
1. Go to "Issue Stock"
2. Select item type (e.g., MDVR)
3. See list of available items by IMEI
4. Select specific IMEI to issue
5. Add purpose and date
6. Click "Issue Item"

### Viewing Transactions
- Transactions now show IMEI for individual items
- Can filter by date, date range, and type
- Shows condition of items for reference

### Viewing Reports
- Reports show individual items issued/received
- Opening/closing balances by item type
- Usage by category (count-based)

---

## Important Notes

### IMEI Uniqueness
- System validates that no two items can have the same IMEI
- This prevents accidental duplicates
- If trying to add duplicate IMEI, you'll get an error message

### Dashboard Logic
- Dashboard still shows unit-level aggregated data (not just types)
- "Stock" card is now labelled **Total Units in Stock** and uses a new
  `total_units` calculation that reflects only the number of serialized
  records; the legacy ``quantity`` field is ignored whenever any serials
  exist.  This matches the behaviour of the admin count and prevents
  inflation due to stale quantity values.  The previous "item types"
  metric has been removed to avoid confusion.
  that currently have any serialized records (i.e., MDVR counts as 1, whether
  its units are available, issued, or damaged). This provides a high-level
  view of item type diversity in stock.
- Available count = Count of serialized items with status='Available'
- Issued count = Count of transactions with type='OUT'
- Category distribution chart now reflects only **available** units by category, not total serialized units

### Backward Compatibility
- System can handle both old (quantity-based) and new (IMEI-based) transactions
- InventoryItem.quantity field is still available but not used in new workflows

### Inventory Calculations
- Available items = SerializedItem records with status='Available'
- Dashboard/availability charts exclude items marked 'Faulty'; the admin list now
  follows the same rule.
- The `InventoryItem.quantity` field is legacy and no longer shown in the admin forms.
- Total items = All SerializedItem records for that item type
- Dashboard aggregates across all item types

---

## Database Schema Changes

### New Table: `inventory_serializeditem`
```sql
-id (Primary Key)
- imei (VARCHAR 20, UNIQUE)
- inventory_item_id (FK to inventory_inventoryitem)
- date_added (DATETIME)
- price (DECIMAL 10,2)
- condition (VARCHAR 20)
- status (VARCHAR 20)
- created_by_id (FK to auth_user)
- created_at (DATETIME)
```

### Updated Table: `inventory_inventorytransaction`
- Added: `serialized_item_id` (FK to inventory_serializeditem, NULL)
- Modified: `quantity` field now defaults to 1

---

## Next Steps

1. **Run Migration**:
   ```bash
   python manage.py migrate
   ```

2. **Test the System**:
   - Add a new item with IMEI using the Receipt Stock page
   - Issue that item using the Issue Stock page
   - Verify it shows in transactions with IMEI

3. **Bulk Upload Testing**:
   - Download the template
   - Add sample data
   - Upload and verify items are created

4. **Check Reports**:
   - View transactions to see IMEI tracking
   - Check reports for balanced calculations

---

## Troubleshooting

### IMEI Validation Errors
- Ensure IMEI is unique across the system
- Check for duplicate entries in admin interface

### Bulk Upload Failures
- Verify Item Name exactly matches existing items
- Check IMEI is unique
- Ensure date format is YYYY-MM-DD
- Price should be numeric or blank

### Missing Items in Stock Out
- Verify items have been added via Stock In
- Items must have status='Available' to appear in dropdowns
- Check admin interface to see item status

---

## Features Implemented

✅ Individual item tracking with unique IMEIs
✅ Item properties: IMEI, Date, Price, Condition
✅ Dual-level system: Units + Individual Items
✅ Stock In: Single and bulk item addition
✅ Stock Out: Select by IMEI
✅ Item status tracking (Available/Issued)
✅ IMEI uniqueness validation
✅ Bulk upload with Excel template
✅ Updated transactions view with IMEI
✅ Updated reports with item-level details
✅ Dashboard showing unit-level aggregates
✅ Admin interface for all models
✅ Transaction history per item

---

## File Changes Summary

### Backend
- `inventory/models.py` - Added SerializedItem model, updated models
- `inventory/admin.py` - Registered SerializedItem, updated admins  
- `inventory/views.py` - Updated all views for new workflows
- `inventory/urls.py` - Added bulk upload routes
- `inventory/migrations/0004_serializeditem_tracking.py` - Database migration

### Frontend
- `templates/inventory/stock_out_form.html` - IMEI selection
- `templates/inventory/stock_in_form.html` - Individual item creation
- `templates/inventory/bulk_upload_form.html` - New bulk upload form
- `templates/inventory/transactions.html` - Added IMEI column
- `templates/inventory/inventory_list.html` - Show total and available counts

---

## Support & Questions

For detailed implementation, refer to the code comments in:
- `inventory/models.py` - Model definitions
- `inventory/views.py` - View logic and workflows
- Templates - UI logic and forms
