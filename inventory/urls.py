from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    # authentication and password helpers
    path('change-password/', views.change_password, name='change_password'),
    
    # Inventory Management
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('inventory/add/', views.inventory_add, name='inventory_add'),
    path('inventory/<int:item_id>/edit/', views.inventory_edit, name='inventory_edit'),
    path('inventory/<int:item_id>/delete/', views.inventory_delete, name='inventory_delete'),
    
    # Stock-out / Stock-in / Transactions
    path('stock-out/', views.stock_out, name='stock_out'),
    path('stock-in/', views.stock_in, name='stock_in'),
    path('bulk-upload/', views.bulk_upload, name='bulk_upload'),
    path('bulk-upload-template/', views.bulk_upload_template, name='bulk_upload_template'),
    path('item/<int:item_id>/', views.inventory_item_detail, name='inventory_item_detail'),
    path('transactions/', views.transactions, name='transactions'),
    
    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/export-csv/', views.export_report_csv, name='export_report_csv'),
    path('reports/export-excel/', views.export_report_excel, name='export_report_excel'),
]