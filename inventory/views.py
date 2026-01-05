from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.core.serializers.json import DjangoJSONEncoder
from datetime import datetime, timedelta
import json
import csv
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from .models import InventoryItem, InventoryTransaction


def root_view(request):
    """Root view - redirects to dashboard if authenticated, else to login"""
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')
    return redirect('inventory:login')


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('inventory:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'inventory/login.html')


@login_required
def logout_view(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out successfully.')
    return redirect('inventory:login')


def forgot_password_view(request):
    """Forgot password view (simplified - token-based reset)"""
    if request.method == 'POST':
        username = request.POST.get('username')
        try:
            user = User.objects.get(username=username)
            # In a real application, you would send an email with reset token
            # For this demo, we'll just show a message
            messages.info(request, 
                f'Password reset instructions would be sent to the email associated with {username}. '
                'Please contact your administrator for password reset.')
        except User.DoesNotExist:
            messages.error(request, 'Username not found.')
    
    return render(request, 'inventory/forgot_password.html')


@login_required
def dashboard(request):
    """Interactive dashboard with statistics and charts"""
    # Total items in inventory
    total_items = InventoryItem.objects.count()
    
    # Inventory count per category
    category_counts = InventoryItem.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Total items issued (stock-out)
    total_issued = InventoryTransaction.objects.filter(
        transaction_type='OUT'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Total items increased (stock-in)
    total_increased = InventoryTransaction.objects.filter(
        transaction_type='IN'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Recently added items (last 10)
    recently_added = InventoryItem.objects.all()[:10]
    
    # Recently issued items (last 10)
    recently_issued = InventoryTransaction.objects.filter(
        transaction_type='OUT'
    )[:10]
    
    # Recently increased items (last 10)
    recently_increased = InventoryTransaction.objects.filter(
        transaction_type='IN'
    )[:10]
    
    # Inventory distribution by category (for chart)
    category_distribution = {}
    for item in InventoryItem.objects.all():
        category_distribution[item.category] = category_distribution.get(item.category, 0) + item.available_quantity()
    
    # Total available items (sum of all available quantities)
    total_available = 0
    for item in InventoryItem.objects.all():
        total_available += item.available_quantity()
    
    # Available items by name (for pie chart)
    available_by_item = {}
    for item in InventoryItem.objects.all():
        available_qty = item.available_quantity()
        if available_qty > 0:  # Only include items with available quantity
            available_by_item[item.name] = available_qty
    
    # Items used per category
    usage_by_category = {}
    for transaction in InventoryTransaction.objects.filter(transaction_type='OUT'):
        category = transaction.item.category
        usage_by_category[category] = usage_by_category.get(category, 0) + transaction.quantity
    
    context = {
        'total_items': total_items,
        'category_counts': category_counts,
        'total_issued': total_issued,
        'total_increased': total_increased,
        'total_available': total_available,
        'recently_added': recently_added,
        'recently_issued': recently_issued,
        'recently_increased': recently_increased,
        'category_distribution': json.dumps(category_distribution),
        'available_by_item': json.dumps(available_by_item),
        'usage_by_category': json.dumps(usage_by_category),
    }
    
    return render(request, 'inventory/dashboard.html', context)


@login_required
def inventory_list(request):
    """List all inventory items with search and filter"""
    items = InventoryItem.objects.all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query) |
            Q(category__icontains=search_query)
        )
    
    # Filter by category
    category_filter = request.GET.get('category', '')
    if category_filter:
        items = items.filter(category=category_filter)
    
    # Add available quantity to each item
    for item in items:
        item.available_qty = item.available_quantity()
    
    # Pagination
    paginator = Paginator(items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    categories = InventoryItem.CATEGORY_CHOICES
    
    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'category_filter': category_filter,
        'categories': categories,
    }
    
    return render(request, 'inventory/inventory_list.html', context)


@login_required
def inventory_add(request):
    """Add new inventory item"""
    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        
        # Validation: Name and Category are required
        if not name or not category:
            messages.error(request, 'Name and Category are required fields.')
            return render(request, 'inventory/inventory_form.html', {
                'categories': InventoryItem.CATEGORY_CHOICES,
            })
        
        try:
            item = InventoryItem.objects.create(
                name=name,
                category=category,
                price=None,
                brand=None,
                imei=None,
                condition='New',  # Default condition
                quantity=1,
                created_by=request.user,
            )
            messages.success(request, f'Item "{item.name}" added successfully!')
            return redirect('inventory:inventory_list')
        except Exception as e:
            messages.error(request, f'Error adding item: {str(e)}')
    
    return render(request, 'inventory/inventory_form.html', {
        'categories': InventoryItem.CATEGORY_CHOICES,
    })


@login_required
def inventory_edit(request, item_id):
    """Edit existing inventory item"""
    item = get_object_or_404(InventoryItem, id=item_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        category = request.POST.get('category')
        
        # Validation: Name and Category are required
        if not name or not category:
            messages.error(request, 'Name and Category are required fields.')
            return render(request, 'inventory/inventory_form.html', {
                'item': item,
                'categories': InventoryItem.CATEGORY_CHOICES,
            })
        
        try:
            item.name = name
            item.category = category
            # Preserve existing values for price, brand, imei, quantity, condition (not editable in UI)
            item.save()
            
            messages.success(request, f'Item "{item.name}" updated successfully!')
            return redirect('inventory:inventory_list')
        except Exception as e:
            messages.error(request, f'Error updating item: {str(e)}')
    
    return render(request, 'inventory/inventory_form.html', {
        'item': item,
        'categories': InventoryItem.CATEGORY_CHOICES,
    })


@login_required
def inventory_delete(request, item_id):
    """Delete inventory item"""
    item = get_object_or_404(InventoryItem, id=item_id)
    
    if request.method == 'POST':
        item_name = item.name
        item.delete()
        messages.success(request, f'Item "{item_name}" deleted successfully!')
        return redirect('inventory:inventory_list')
    
    return render(request, 'inventory/inventory_confirm_delete.html', {'item': item})


@login_required
def stock_out(request):
    """Issue items from inventory (stock-out)"""
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        purpose = request.POST.get('purpose', '')
        
        item = get_object_or_404(InventoryItem, id=item_id)
        available_qty = item.available_quantity()
        
        # Validation: Cannot issue more than available
        if quantity > available_qty:
            messages.error(request, 
                f'Cannot issue {quantity} items. Only {available_qty} available.')
            return redirect('inventory:inventory_list')
        
        try:
            transaction = InventoryTransaction.objects.create(
                item=item,
                transaction_type='OUT',
                quantity=quantity,
                purpose=purpose,
                issued_by=request.user,
            )
            messages.success(request, 
                f'Issued {quantity} x {item.name} successfully!')
            return redirect('inventory:transactions')
        except Exception as e:
            messages.error(request, f'Error issuing item: {str(e)}')
    
    # GET request - show form
    item_id = request.GET.get('item_id')
    if item_id:
        item = get_object_or_404(InventoryItem, id=item_id)
        return render(request, 'inventory/stock_out_form.html', {
            'item': item,
            'available_qty': item.available_quantity(),
        })
    
    # Show all items for selection
    items = InventoryItem.objects.all()
    for item in items:
        item.available_qty = item.available_quantity()
    
    return render(request, 'inventory/stock_out_form.html', {
        'items': items,
    })


@login_required
def stock_in(request):
    """Receive items in inventory (stock-in)"""
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        purpose = request.POST.get('purpose', '')
        
        item = get_object_or_404(InventoryItem, id=item_id)
        
        try:
            transaction = InventoryTransaction.objects.create(
                item=item,
                transaction_type='IN',
                quantity=quantity,
                purpose=purpose,
                issued_by=request.user,
            )
            # Update the base quantity
            item.quantity += quantity
            item.save()
            
            messages.success(request, 
                f'Received {quantity} x {item.name} successfully!')
            return redirect('inventory:transactions')
        except Exception as e:
            messages.error(request, f'Error receiving item: {str(e)}')
    
    # GET request - show form
    item_id = request.GET.get('item_id')
    if item_id:
        item = get_object_or_404(InventoryItem, id=item_id)
        return render(request, 'inventory/stock_in_form.html', {
            'item': item,
            'current_qty': item.quantity,
        })
    
    # Show all items for selection
    items = InventoryItem.objects.all()
    for item in items:
        item.available_qty = item.available_quantity()
    
    return render(request, 'inventory/stock_in_form.html', {
        'items': items,
    })


@login_required
def transactions(request):
    """List all inventory transactions"""
    transactions_list = InventoryTransaction.objects.all().select_related('item', 'issued_by')
    
    # Filter by date range
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if start_date:
        transactions_list = transactions_list.filter(date_taken__gte=start_date)
    if end_date:
        transactions_list = transactions_list.filter(date_taken__lte=end_date)
    
    # Filter by transaction type
    transaction_type = request.GET.get('type', '')
    if transaction_type:
        transactions_list = transactions_list.filter(transaction_type=transaction_type)
    
    # Pagination
    paginator = Paginator(transactions_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'start_date': start_date,
        'end_date': end_date,
        'transaction_type': transaction_type,
    }
    
    return render(request, 'inventory/transactions.html', context)


@login_required
def reports(request):
    """Generate inventory reports"""
    # Default to current month
    today = timezone.now().date()
    start_date = request.GET.get('start_date', today.replace(day=1).isoformat())
    end_date = request.GET.get('end_date', today.isoformat())
    
    # Parse dates
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except:
        start = today.replace(day=1)
        end = today
    
    # Items added during period
    items_added = InventoryItem.objects.filter(
        date_added__date__gte=start,
        date_added__date__lte=end
    )
    
    # Items taken out during period
    items_taken_out = InventoryTransaction.objects.filter(
        transaction_type='OUT',
        date_taken__date__gte=start,
        date_taken__date__lte=end
    )
    
    # Items increased during period
    items_increased = InventoryTransaction.objects.filter(
        transaction_type='IN',
        date_taken__date__gte=start,
        date_taken__date__lte=end
    )
    
    # Total items used
    total_used = items_taken_out.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Total items increased
    total_increased = items_increased.aggregate(total=Sum('quantity'))['total'] or 0
    
    # Items taken out summary (aggregated per item)
    items_taken_out_summary = {}
    for transaction in items_taken_out:
        item_name = transaction.item.name
        if item_name not in items_taken_out_summary:
            items_taken_out_summary[item_name] = {
                'category': transaction.item.category,
                'total_quantity': 0,
            }
        items_taken_out_summary[item_name]['total_quantity'] += transaction.quantity
    
    # Items received summary (aggregated per item)
    items_received_summary = {}
    for transaction in items_increased:
        item_name = transaction.item.name
        if item_name not in items_received_summary:
            items_received_summary[item_name] = {
                'category': transaction.item.category,
                'total_quantity': 0,
            }
        items_received_summary[item_name]['total_quantity'] += transaction.quantity
    
    # Quantity used per item (for combined view)
    usage_per_item = {}
    for transaction in items_taken_out:
        item_name = transaction.item.name
        if item_name not in usage_per_item:
            usage_per_item[item_name] = {
                'category': transaction.item.category,
                'quantity': 0,
                'increased': 0,
            }
        usage_per_item[item_name]['quantity'] += transaction.quantity
    
    # Quantity increased per item (for combined view)
    for transaction in items_increased:
        item_name = transaction.item.name
        if item_name not in usage_per_item:
            usage_per_item[item_name] = {
                'category': transaction.item.category,
                'quantity': 0,
                'increased': 0,
            }
        usage_per_item[item_name]['increased'] += transaction.quantity
    
    # Usage per category
    usage_by_category = {}
    for transaction in items_taken_out:
        category = transaction.item.category
        usage_by_category[category] = usage_by_category.get(category, 0) + transaction.quantity
    
    # Increases per category
    increases_by_category = {}
    for transaction in items_increased:
        category = transaction.item.category
        increases_by_category[category] = increases_by_category.get(category, 0) + transaction.quantity
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'items_added': items_added,
        'items_taken_out_summary': items_taken_out_summary,
        'items_received_summary': items_received_summary,
        'total_used': total_used,
        'total_increased': total_increased,
        'usage_per_item': usage_per_item,
        'usage_by_category': usage_by_category,
        'increases_by_category': increases_by_category,
    }
    
    return render(request, 'inventory/reports.html', context)


@login_required
def export_report_csv(request):
    """Export report as CSV"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        messages.error(request, 'Start date and end date are required.')
        return redirect('inventory:reports')
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except:
        messages.error(request, 'Invalid date format.')
        return redirect('inventory:reports')
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="inventory_report_{start_date}_to_{end_date}.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow(['Report Period', f'{start_date} to {end_date}'])
    writer.writerow([])
    
    # Items taken out summary (aggregated)
    writer.writerow(['ITEMS TAKEN OUT (SUMMARY)'])
    writer.writerow(['Item Name', 'Category', 'Total Quantity Issued'])
    items_taken_out = InventoryTransaction.objects.filter(
        transaction_type='OUT',
        date_taken__date__gte=start,
        date_taken__date__lte=end
    ).select_related('item')
    
    items_taken_out_summary = {}
    total_used = 0
    for transaction in items_taken_out:
        item_name = transaction.item.name
        if item_name not in items_taken_out_summary:
            items_taken_out_summary[item_name] = {
                'category': transaction.item.category,
                'total_quantity': 0,
            }
        items_taken_out_summary[item_name]['total_quantity'] += transaction.quantity
        total_used += transaction.quantity
    
    for item_name, data in sorted(items_taken_out_summary.items()):
        writer.writerow([
            item_name, data['category'], data['total_quantity']
        ])
    
    writer.writerow([])
    writer.writerow(['Total Items Used', total_used])
    writer.writerow([])
    
    # Items received summary (aggregated)
    writer.writerow(['ITEMS RECEIVED (SUMMARY)'])
    writer.writerow(['Item Name', 'Category', 'Total Quantity Received'])
    items_increased = InventoryTransaction.objects.filter(
        transaction_type='IN',
        date_taken__date__gte=start,
        date_taken__date__lte=end
    ).select_related('item')
    
    items_received_summary = {}
    total_increased = 0
    for transaction in items_increased:
        item_name = transaction.item.name
        if item_name not in items_received_summary:
            items_received_summary[item_name] = {
                'category': transaction.item.category,
                'total_quantity': 0,
            }
        items_received_summary[item_name]['total_quantity'] += transaction.quantity
        total_increased += transaction.quantity
    
    for item_name, data in sorted(items_received_summary.items()):
        writer.writerow([
            item_name, data['category'], data['total_quantity']
        ])
    
    writer.writerow([])
    writer.writerow(['Total Items Received', total_increased])
    
    writer.writerow([])
    writer.writerow(['Total Items Used', total_used])
    writer.writerow([])
    
    # Usage by category
    writer.writerow(['USAGE BY CATEGORY'])
    writer.writerow(['Category', 'Quantity Used'])
    usage_by_category = {}
    for transaction in items_taken_out:
        category = transaction.item.category
        usage_by_category[category] = usage_by_category.get(category, 0) + transaction.quantity
    
    for category, quantity in sorted(usage_by_category.items()):
        writer.writerow([category, quantity])
    
    writer.writerow([])
    
    # Increases by category
    writer.writerow(['RECEIPTS BY CATEGORY'])
    writer.writerow(['Category', 'Quantity Received'])
    increases_by_category = {}
    for transaction in items_increased:
        category = transaction.item.category
        increases_by_category[category] = increases_by_category.get(category, 0) + transaction.quantity
    
    for category, quantity in sorted(increases_by_category.items()):
        writer.writerow([category, quantity])
    
    return response


@login_required
def export_report_excel(request):
    """Export report as Excel"""
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    if not start_date or not end_date:
        messages.error(request, 'Start date and end date are required.')
        return redirect('inventory:reports')
    
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
    except:
        messages.error(request, 'Invalid date format.')
        return redirect('inventory:reports')
    
    # Create Excel workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventory Report"
    
    # Styles
    header_fill = PatternFill(start_color="000000", end_color="000000", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=12)
    title_font = Font(bold=True, size=14)
    section_font = Font(bold=True, size=12)
    
    # Header
    ws['A1'] = 'Report Period'
    ws['B1'] = f'{start_date} to {end_date}'
    ws['A1'].font = title_font
    ws['B1'].font = title_font
    
    row = 3
    
    # Items taken out summary
    ws[f'A{row}'] = 'ITEMS TAKEN OUT (SUMMARY)'
    ws[f'A{row}'].font = section_font
    row += 1
    
    ws[f'A{row}'] = 'Item Name'
    ws[f'B{row}'] = 'Category'
    ws[f'C{row}'] = 'Total Quantity Issued'
    for col in ['A', 'B', 'C']:
        cell = ws[f'{col}{row}']
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    
    items_taken_out = InventoryTransaction.objects.filter(
        transaction_type='OUT',
        date_taken__date__gte=start,
        date_taken__date__lte=end
    ).select_related('item')
    
    items_taken_out_summary = {}
    total_used = 0
    for transaction in items_taken_out:
        item_name = transaction.item.name
        if item_name not in items_taken_out_summary:
            items_taken_out_summary[item_name] = {
                'category': transaction.item.category,
                'total_quantity': 0,
            }
        items_taken_out_summary[item_name]['total_quantity'] += transaction.quantity
        total_used += transaction.quantity
    
    for item_name, data in sorted(items_taken_out_summary.items()):
        ws[f'A{row}'] = item_name
        ws[f'B{row}'] = data['category']
        ws[f'C{row}'] = data['total_quantity']
        row += 1
    
    ws[f'A{row}'] = 'Total Items Used'
    ws[f'C{row}'] = total_used
    ws[f'A{row}'].font = Font(bold=True)
    ws[f'C{row}'].font = Font(bold=True)
    row += 2
    
    # Items received summary
    ws[f'A{row}'] = 'ITEMS RECEIVED (SUMMARY)'
    ws[f'A{row}'].font = section_font
    row += 1
    
    ws[f'A{row}'] = 'Item Name'
    ws[f'B{row}'] = 'Category'
    ws[f'C{row}'] = 'Total Quantity Received'
    for col in ['A', 'B', 'C']:
        cell = ws[f'{col}{row}']
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    
    items_increased = InventoryTransaction.objects.filter(
        transaction_type='IN',
        date_taken__date__gte=start,
        date_taken__date__lte=end
    ).select_related('item')
    
    items_received_summary = {}
    total_increased = 0
    for transaction in items_increased:
        item_name = transaction.item.name
        if item_name not in items_received_summary:
            items_received_summary[item_name] = {
                'category': transaction.item.category,
                'total_quantity': 0,
            }
        items_received_summary[item_name]['total_quantity'] += transaction.quantity
        total_increased += transaction.quantity
    
    for item_name, data in sorted(items_received_summary.items()):
        ws[f'A{row}'] = item_name
        ws[f'B{row}'] = data['category']
        ws[f'C{row}'] = data['total_quantity']
        row += 1
    
    ws[f'A{row}'] = 'Total Items Received'
    ws[f'C{row}'] = total_increased
    ws[f'A{row}'].font = Font(bold=True)
    ws[f'C{row}'].font = Font(bold=True)
    row += 2
    
    # Usage by category
    ws[f'A{row}'] = 'USAGE BY CATEGORY'
    ws[f'A{row}'].font = section_font
    row += 1
    
    ws[f'A{row}'] = 'Category'
    ws[f'B{row}'] = 'Quantity Used'
    for col in ['A', 'B']:
        cell = ws[f'{col}{row}']
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    
    usage_by_category = {}
    for transaction in items_taken_out:
        category = transaction.item.category
        usage_by_category[category] = usage_by_category.get(category, 0) + transaction.quantity
    
    for category, quantity in sorted(usage_by_category.items()):
        ws[f'A{row}'] = category
        ws[f'B{row}'] = quantity
        row += 1
    
    row += 1
    
    # Receipts by category
    ws[f'A{row}'] = 'RECEIPTS BY CATEGORY'
    ws[f'A{row}'].font = section_font
    row += 1
    
    ws[f'A{row}'] = 'Category'
    ws[f'B{row}'] = 'Quantity Received'
    for col in ['A', 'B']:
        cell = ws[f'{col}{row}']
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
    row += 1
    
    increases_by_category = {}
    for transaction in items_increased:
        category = transaction.item.category
        increases_by_category[category] = increases_by_category.get(category, 0) + transaction.quantity
    
    for category, quantity in sorted(increases_by_category.items()):
        ws[f'A{row}'] = category
        ws[f'B{row}'] = quantity
        row += 1
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width
    
    # Create HTTP response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="inventory_report_{start_date}_to_{end_date}.xlsx"'
    
    wb.save(response)
    return response