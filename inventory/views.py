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
from .models import InventoryItem, InventoryTransaction, SerializedItem


def root_view(request):
    """Root view - redirects to dashboard if authenticated, else to login"""
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')
    return redirect('inventory:login')


def login_view(request):
    """User login view.

    Staff users are no longer auto-forwarded to the Django admin; the
    application behaviour is to land everyone on the inventory dashboard
    after a successful login.  The admin link remains available in the
    interface for those who need it.
    """
    if request.user.is_authenticated:
        return redirect('inventory:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            # always send logged‑in users to the dashboard
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
def change_password(request):
    """Allow an authenticated user to change their password.

    This works together with the ForcePasswordChangeMiddleware and the
    UserProfile.force_password_change flag. On successful change the flag is
    cleared so the user can access the rest of the system.
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')

        # Basic validations
        if not current_password or not new_password or not confirm_password:
            messages.error(request, 'All password fields are required.')
            return render(request, 'in[o9entory/change_password.html')

        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'inventory/change_password.html')

        if new_password != confirm_password:
            messages.error(request, 'New password and confirmation do not match.')
            return render(request, 'inventory/change_password.html')

        # Update the password
        request.user.set_password(new_password)
        request.user.save()

        # Clear the force_password_change flag if profile exists
        profile = getattr(request.user, 'profile', None)
        if profile:
            profile.force_password_change = False
            profile.save()

        # Re-authenticate the user after password change
        user = authenticate(username=request.user.username, password=new_password)
        if user is not None:
            login(request, user)

        messages.success(request, 'Your password has been updated successfully.')
        return redirect('inventory:dashboard')

    return render(request, 'inventory/change_password.html')


@login_required
def dashboard(request):
    """Interactive dashboard with statistics and charts"""
    # Total units in stock is simply the count of serialized records.  The
    # UI card on the dashboard uses ``total_units`` and tests rely on that
    # name, so we compute it explicitly here (legacy quantities are ignored
    # whenever any serialized items exist, which matches
    # ``InventoryItem.total_qty`` behaviour).
    total_units = SerializedItem.objects.count()

    # Inventory count per category (number of item types)
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
    
    # Inventory distribution by category (for chart) - use available quantities
    category_distribution = {}
    for item in InventoryItem.objects.all():
        category_distribution[item.category] = (
            category_distribution.get(item.category, 0)
            + item.available_quantity()
        )
    
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
        'total_units': total_units,
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
    items = InventoryItem.objects.all()

    search_query = request.GET.get('search', '')
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query) |
            Q(category__icontains=search_query)
        )

    category_filter = request.GET.get('category', '')
    if category_filter:
        items = items.filter(category=category_filter)

    #  Evaluate to list FIRST, then annotate
    items_list = list(items)
    for item in items_list:
        item.available_qty = item.available_quantity()

    # Paginate the annotated list, not the queryset
    paginator = Paginator(items_list, 20)
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
            # the model only has name, category, quantity and created_by
            item = InventoryItem.objects.create(
                name=name,
                category=category,
                quantity=0,            # start out empty by default
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
            # quantity is managed separately; other legacy fields no longer exist
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
        # item_id may be submitted as a hidden field; if not, fall back to
        # querystring (some older links used href="?item_id=...").
        item_id = request.POST.get('item_id') or request.GET.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        serialized_id = request.POST.get('serialized_item_id')
        purpose = request.POST.get('purpose', '')
        date_taken_str = request.POST.get('date_taken', '')
        
        item = get_object_or_404(InventoryItem, id=item_id)
        usable_qty = item.usable_quantity()
        
        # Validation: Cannot issue more than what is actually free to issue
        if quantity > usable_qty:
            messages.error(request, 
                f'Cannot issue {quantity} items. Only {usable_qty} available for issue.')
            return redirect('inventory:inventory_list')
        
        try:
            # Parse the date if provided
            date_taken = timezone.now()
            if date_taken_str:
                from datetime import datetime
                dt = datetime.fromisoformat(date_taken_str)
                date_taken = timezone.make_aware(dt) if not dt.tzinfo else dt

            tx_kwargs = {
                'item': item,
                'transaction_type': 'OUT',
                'quantity': quantity,
                'purpose': purpose,
                'issued_by': request.user,
                'date_taken': date_taken,
            }
            if serialized_id:
                tx_kwargs['serialized_item'] = get_object_or_404(SerializedItem, id=serialized_id)

            transaction = InventoryTransaction.objects.create(**tx_kwargs)
            messages.success(request, 
                f'Issued {quantity} x {item.name} successfully!')
            return redirect('inventory:transactions')
        except Exception as e:
            messages.error(request, f'Error issuing item: {str(e)}')
    
    # GET request - show form
    item_id = request.GET.get('item_id')
    if item_id:
        item = get_object_or_404(InventoryItem, id=item_id)
        # items that can actually be chosen for issuing
        available_items = item.serialized_items.filter(
            status='Available'
        ).exclude(condition='Faulty')
        return render(request, 'inventory/stock_out_form.html', {
            'item': item,
            'available_items': available_items,
            'available_qty': item.available_quantity(),  # for display if needed
            'display_available': item.available_quantity(),
        })

    # Show all items for selection
    items = InventoryItem.objects.all()
    for item in items:
        # when listing types we want to indicate how many can be issued
        item.available_count = item.usable_quantity()

    return render(request, 'inventory/stock_out_form.html', {
        'items': items,
    })


@login_required
def stock_in(request):
    """Receive items in inventory (stock-in).

    This view serves two purposes depending on whether the user is
    selecting an item first or already has an ``item_id``.  The form
    rendered when the user is adding a *serialized* unit contains fields
    for IMEI, brand, price, condition, etc., and those values need to be
    propagated back to the view so a ``SerializedItem`` can be created.
    
    The original implementation only created an ``InventoryTransaction``
    and ignored all of the extra form fields which meant the dropdown for
    ``condition`` never got any data at all.  The fix below passes the
    condition choices to the template and processes the additional
    POST data when a serial number is supplied.
    """
    if request.method == 'POST':
        item_id = request.POST.get('item_id')
        imei = request.POST.get('imei', '').strip()
        brand = request.POST.get('brand') or None
        price = request.POST.get('price') or None
        condition = request.POST.get('condition') or 'New'
        date_added_str = request.POST.get('date_added', '')
        purpose = request.POST.get('purpose', '')
        # quantity is only used for legacy (non‑serialized) stock-ins;
        # keep the parameter so existing code/links continue to work but we
        # default to 1 since there is no quantity field in the form.
        quantity = int(request.POST.get('quantity', 1))
        date_taken_str = request.POST.get('date_taken', '')
        
        item = get_object_or_404(InventoryItem, id=item_id)
        
        try:
            # Parse the transaction date if provided
            date_taken = timezone.now()
            if date_taken_str:
                from datetime import datetime
                dt = datetime.fromisoformat(date_taken_str)
                date_taken = timezone.make_aware(dt) if not dt.tzinfo else dt

            # if an IMEI is supplied we are dealing with a serialized item
            if imei:
                # parse the "date added" field for the serial record
                date_added = timezone.now()
                if date_added_str:
                    from datetime import datetime
                    dt = datetime.fromisoformat(date_added_str)
                    date_added = timezone.make_aware(dt) if not dt.tzinfo else dt

                si = SerializedItem.objects.create(
                    inventory_item=item,
                    imei=imei,
                    brand=brand,
                    price=price,
                    condition=condition,
                    date_added=date_added,
                    status='Available',
                    created_by=request.user,
                )
                # record the corresponding transaction
                InventoryTransaction.objects.create(
                    item=item,
                    serialized_item=si,
                    transaction_type='IN',
                    quantity=1,
                    purpose=purpose,
                    issued_by=request.user,
                    date_taken=date_taken,
                )

                messages.success(request,
                    f'Received serial {imei} for {item.name}.')
            else:
                # legacy behaviour: adjust the item's quantity directly
                transaction = InventoryTransaction.objects.create(
                    item=item,
                    transaction_type='IN',
                    quantity=quantity,
                    purpose=purpose,
                    issued_by=request.user,
                    date_taken=date_taken,
                )
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
            # for stock‑in the "current" count isn't strictly necessary but
            # keep it consistent with available stock semantics
            'current_qty': item.available_quantity(),
            'conditions': SerializedItem.CONDITION_CHOICES,
        })
    
    # Show all items for selection
    items = InventoryItem.objects.all()
    for item in items:
        item.available_qty = item.available_quantity()
    
    return render(request, 'inventory/stock_in_form.html', {
        'items': items,
        'conditions': SerializedItem.CONDITION_CHOICES,
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

    # --- Opening and Closing Balances per item ---
    # We'll compute net transaction amounts in one pass to avoid many DB queries.
    transactions_all = InventoryTransaction.objects.select_related('item').all()

    net_since_start = {}   # sum(IN - OUT) for transactions with date >= start
    net_after_end = {}     # sum(IN - OUT) for transactions with date > end

    for t in transactions_all:
        try:
            t_date = t.date_taken.date()
        except Exception:
            # fallback if date_taken is naive/unexpected
            t_date = t.date_taken

        sign = t.quantity if t.transaction_type == 'IN' else -t.quantity
        item_id = t.item_id

        if t_date >= start:
            net_since_start[item_id] = net_since_start.get(item_id, 0) + sign

        if t_date > end:
            net_after_end[item_id] = net_after_end.get(item_id, 0) + sign

    # Build per-item balances
    item_balances = {}
    total_opening = 0
    total_closing = 0
    for item in InventoryItem.objects.all():
        # for report purposes we count every serial (even faulty)
        q_now = item.report_quantity() or 0
        # Opening = quantity at start of period (before any transactions)
        opening = q_now - net_since_start.get(item.id, 0)
        # never allow a negative opening balance
        if opening < 0:
            opening = 0
        # Closing = quantity at end of period (after later transactions)
        closing = q_now - net_after_end.get(item.id, 0)
        if closing < 0:
            closing = 0

        item_balances[item.name] = {
            'category': item.category,
            'opening': opening,
            'closing': closing,
            'current': q_now,
            'movement': closing - opening,
        }

        total_opening += opening
        total_closing += closing
    
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
        'item_balances': item_balances,
        'total_opening': total_opening,
        'total_closing': total_closing,
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


@login_required
def bulk_upload_template(request):
    """
    Serve an Excel template for bulk uploading serialized items.

    The first worksheet contains the headers plus a single example row.  A
    hidden second worksheet holds the lookup values used by the data
    validation lists on the main sheet:

    * column A (item names) = all current ``InventoryItem`` names
    * column F (condition) uses the codes from ``SerializedItem.CONDITION_CHOICES``
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Bulk Upload Template"

    headers = ["Item Name", "IMEI", "Brand", "Date Added", "Price", "Condition"]
    ws.append(headers)
    # keep one example row for clarity
    ws.append(["MDVR", "1234567890123", "AHBrands", timezone.now().date().isoformat(), "5000", "New"])

    # hidden lookup sheet for data validation lists
    lists = wb.create_sheet("lists")
    lists.sheet_state = 'hidden'

    item_names = list(InventoryItem.objects.values_list('name', flat=True))
    for idx, name in enumerate(item_names, start=1):
        lists.cell(row=idx, column=1, value=name)
    for idx, (code, _) in enumerate(SerializedItem.CONDITION_CHOICES, start=1):
        lists.cell(row=idx, column=2, value=code)

    from openpyxl.worksheet.datavalidation import DataValidation
    dv_item = DataValidation(
        type="list",
        formula1=f"=lists!$A$1:$A${len(item_names)}",
        allow_blank=False,
    )
    dv_condition = DataValidation(
        type="list",
        formula1=f"=lists!$B$1:$B${len(SerializedItem.CONDITION_CHOICES)}",
        allow_blank=True,
    )
    ws.add_data_validation(dv_item)
    ws.add_data_validation(dv_condition)
    dv_item.add("A2:A1048576")
    dv_condition.add("F2:F1048576")

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="bulk_upload_template.xlsx"'
    wb.save(response)
    return response


@login_required
def bulk_upload(request):
    """
    Handle Excel bulk upload of SerializedItem records.

    Expects columns: Item Name, IMEI, Brand, Date Added, Price, Condition.
    """
    if request.method == "POST":
        excel_file = request.FILES.get("excel_file")
        if not excel_file:
            messages.error(request, "Please upload an Excel file.")
            return render(request, "inventory/bulk_upload_form.html")

        from openpyxl import load_workbook

        try:
            wb = load_workbook(excel_file)
            ws = wb.active
        except Exception as exc:
            messages.error(request, f"Could not read Excel file: {exc}")
            return render(request, "inventory/bulk_upload_form.html")

        created_count = 0
        errors = []

        # Skip header row (assume first row is header)
        for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            item_name, imei, brand, date_added, price, condition = row[:6]

            if not item_name or not imei:
                errors.append(f"Row {idx}: Item Name and IMEI are required.")
                continue

            try:
                item = InventoryItem.objects.get(name=item_name)
            except InventoryItem.DoesNotExist:
                errors.append(f"Row {idx}: Item '{item_name}' does not exist.")
                continue

            try:
                # Parse optional date
                if date_added:
                    if isinstance(date_added, str):
                        try:
                            parsed_date = datetime.strptime(date_added, "%Y-%m-%d")
                            aware_date = timezone.make_aware(parsed_date)
                        except Exception:
                            errors.append(f"Row {idx}: Invalid date format (use YYYY-MM-DD).")
                            continue
                    else:
                        aware_date = timezone.make_aware(date_added) if timezone.is_naive(date_added) else date_added
                else:
                    aware_date = timezone.now()

                si = SerializedItem.objects.create(
                    inventory_item=item,
                    imei=str(imei),
                    brand=brand or None,
                    date_added=aware_date,
                    price=price or None,
                    condition=condition or "New",
                    status="Available",
                    created_by=request.user,
                )
                # also create a matching stock‑in transaction so the dashboard
                # and reports will pick up the receipt immediately
                InventoryTransaction.objects.create(
                    item=item,
                    serialized_item=si,
                    transaction_type='IN',
                    quantity=1,
                    date_taken=aware_date,
                    issued_by=request.user,
                )
                created_count += 1
            except Exception as exc:
                errors.append(f"Row {idx}: {exc}")

        if created_count:
            messages.success(request, f"Successfully created {created_count} item(s).")
        if errors:
            messages.error(request, "Some rows could not be imported:\n" + "\n".join(errors))

        return render(request, "inventory/bulk_upload_form.html")

    # GET request
    return render(request, "inventory/bulk_upload_form.html")


@login_required
def inventory_item_detail(request, item_id):
    """
    Detail view for a single InventoryItem, including serialized items.
    """
    item = get_object_or_404(InventoryItem, id=item_id)
    serialized_items = item.serialized_items.all().order_by("-date_added")
    return render(
        request,
        "inventory/inventory_item_detail.html",
        {
            "item": item,
            "serialized_items": serialized_items,
            "available_qty": getattr(item, "available_quantity", lambda: item.quantity)(),
        },
    )