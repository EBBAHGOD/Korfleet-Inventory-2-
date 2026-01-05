# Korfleet Inventory Management System

A comprehensive Python-based inventory management web application built with Django for Korfleet company.

## Features

### 1. Authentication System
- **Login**: Secure session-based authentication
- **Logout**: User logout functionality
- **Forgot Password**: Password reset request page (email simulation)

### 2. Inventory Management
- **Fixed Categories**:
  - Video Devices (MDVRs)
  - Fuel Level Sensors
  - SIM Cards
  - Cameras
  - Accessories
  - Flow Meters

- **Item Properties**:
  - Name (required)
  - Category (required)
  - Price
  - Brand
  - IMEI
  - Condition (New, Used, Faulty)
  - Quantity (default: 1)
  - Date added (auto-generated)

- **CRUD Operations**: Create, Read, Update, Delete inventory items
- **Search & Filter**: Search by name, brand, IMEI, or category

### 3. Stock-Out Tracking
- Record transactions when items are issued
- Track:
  - Item name and category
  - Quantity taken
  - Date taken
  - Purpose/reason (optional)
  - User who issued the item
- Automatic quantity reduction
- Prevention of issuing more than available stock

### 4. Interactive Dashboard
- **Statistics**:
  - Total items in inventory
  - Total items issued
  - Number of categories
- **Charts**:
  - Inventory distribution by category (Doughnut chart)
  - Items used per category (Bar chart)
- **Recent Activity**:
  - Recently added items
  - Recently issued items

### 5. Reporting System
- **Report Features**:
  - Monthly period reports
  - Custom date range reports
  - Items added during period
  - Items taken out during period
  - Quantity used per item
  - Total number of items used
  - Usage summary by category
- **Export Options**: CSV export

## Tech Stack

- **Backend**: Python 3.x, Django 5.2.7
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Styling**: Custom CSS with Korfleet brand colors (Orange, White, Black)
- **Charts**: Chart.js
- **Authentication**: Django session-based authentication with hashed passwords

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)

### Step 1: Clone/Navigate to Project Directory
```bash
cd korfleet_inventory
```

### Step 2: Install Dependencies
```bash
pip install django
```

### Step 3: Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Step 4: Create Superuser (Admin Account)
```bash
python manage.py createsuperuser
```
Follow the prompts to create an admin account.

### Step 5: Collect Static Files
```bash
python manage.py collectstatic
```

### Step 6: Run Development Server
```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## Usage

### Accessing the Application

1. **Login**: Navigate to `http://127.0.0.1:8000/login/`
   - Use the superuser credentials created during setup

2. **Dashboard**: After login, you'll be redirected to the dashboard showing:
   - Inventory statistics
   - Charts and visualizations
   - Recent activity

3. **Inventory Management**:
   - View all items: Click "Inventory" in navigation
   - Add new item: Click "Add New Item" button
   - Edit item: Click "Edit" button next to any item
   - Delete item: Click "Delete" button (with confirmation)
   - Issue stock: Click "Issue" button to record stock-out

4. **Transactions**: View all inventory transactions (stock-in/stock-out)

5. **Reports**: 
   - Select date range
   - Click "Generate Report"
   - Export to CSV using "Export CSV" button

### Admin Panel

Access Django admin panel at `http://127.0.0.1:8000/admin/` for advanced management.

## Project Structure

```
korfleet_inventory/
├── inventory/              # Main app
│   ├── models.py          # Database models
│   ├── views.py           # View functions
│   ├── urls.py            # URL routing
│   ├── admin.py           # Admin configuration
│   └── migrations/        # Database migrations
├── korfleet_inventory/    # Project settings
│   ├── settings.py        # Django settings
│   ├── urls.py            # Main URL configuration
│   └── wsgi.py            # WSGI configuration
├── templates/             # HTML templates
│   └── inventory/
│       ├── base.html
│       ├── login.html
│       ├── dashboard.html
│       ├── inventory_list.html
│       ├── inventory_form.html
│       ├── transactions.html
│       ├── reports.html
│       └── ...
├── static/                # Static files
│   ├── css/
│   │   └── style.css     # Main stylesheet
│   └── js/
├── db.sqlite3             # SQLite database
├── manage.py              # Django management script
└── README.md              # This file
```

## Database Models

### InventoryItem
- Stores inventory items with all properties
- Tracks creation date and creator

### InventoryTransaction
- Records all stock movements (in/out)
- Links to items and users
- Tracks purpose and timestamps

## Validation Rules

- **Name** and **Category** are required fields for inventory items
- Cannot issue more items than available quantity
- All quantities must be non-negative integers

## Brand Colors

- **Primary Orange**: #FF6B35
- **White**: #FFFFFF
- **Black**: #000000

## Security Features

- Session-based authentication
- Password hashing (Django's default PBKDF2)
- CSRF protection
- SQL injection protection (Django ORM)
- XSS protection (Django template auto-escaping)

## Future Enhancements (Optional)

- Role-based access control (Admin vs Staff)
- Low-stock alerts
- Audit log for inventory changes
- Email notifications
- PDF report generation
- Barcode scanning
- Multi-warehouse support

## Troubleshooting

### Common Issues

1. **Migration Errors**: 
   ```bash
   python manage.py migrate --run-syncdb
   ```

2. **Static Files Not Loading**:
   ```bash
   python manage.py collectstatic --noinput
   ```

3. **Permission Errors**: Ensure you have write permissions in the project directory

## Support

For issues or questions, please contact your system administrator.

## License

Internal use only - Korfleet Company

---

**Version**: 1.0.0  
**Last Updated**: December 2025