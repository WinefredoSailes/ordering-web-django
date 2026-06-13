# Fuel Ordering System

A web-based fuel ordering and delivery management system built with Django. Supports customer ordering, cashier payment verification, hauling dispatch, driver delivery tracking, and superadmin oversight.

## Roles

| Role | Description |
|------|-------------|
| **Customer** | Browse products, place orders, upload payment proofs |
| **Cashier** | Verify uploaded payments, approve/reject |
| **Hauling/Dispatcher** | Create dispatch trips, assign tankers and drivers |
| **Driver** | View assigned trips, mark orders in-transit/delivered |
| **Superadmin** | Full control: users, products, pricing, groups, trucks, audit logs |

## Quick Start

### Prerequisites
- Python 3.10+
- Git

### Setup

```bash
# 1. Clone the repo
git clone https://github.com/WinefredoSailes/ordering-web-django.git
cd ordering-web

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate     # Windows
source venv/bin/activate    # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations
python manage.py migrate

# 5. Seed initial data (optional)
python manage.py seed_data

# 6. Create a superadmin account
python manage.py createsuperuser

# 7. Start the dev server
python manage.py runserver
```

Open **http://127.0.0.1:8000** in your browser.

> **Note**: The `seed_data` command creates sample products, groups, and pricing. Run it once after `migrate`.

## Default Test Accounts (after seed_data)

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | superadmin |
| `cashier1` | `cashier123` | cashier |
| `hauling1` | `hauling123` | hauling |
| `driver1` | `driver123` | driver |
| `customer1` | `customer123` | customer |

## User Guide

### Customer Flow
1. **Browse Products** — View available fuel products and pricing
2. **Place Order** — Select product, quantity, and delivery address
3. **Upload Payment** — Upload a proof of payment (image)
4. **Track Order** — Monitor order status (pending → approved → dispatched → in-transit → delivered)

### Cashier Flow
1. **Dashboard** — View pending payment verifications
2. **Verify Payment** — Review uploaded payment proof
3. **Approve/Reject** — Approve generates an Acknowledgement Receipt (AR) number automatically
4. **Track** — Approved orders move to "Ready for Dispatch"

### Hauling/Dispatcher Flow
1. **Dashboard** — View orders ready for dispatch, active tankers, available drivers
2. **Create Trip** — Select tanker, driver, and assign compartment allocations
3. **Manage Trips** — View active and completed trips

### Driver Flow
1. **My Trips** — View assigned dispatch orders
2. **Mark In Transit** — Confirm pickup
3. **Mark Delivered** — Upload delivery proof photo and confirm delivery

### Superadmin Flow
1. **Dashboard** — Overview of all orders by status
2. **Manage** — Users, products, pricing rules, customer groups, trucks/tankers, drivers
3. **Audit Logs** — View all system actions

## Tech Stack

- **Backend**: Django 5.0, SQLite (dev) / PostgreSQL (prod)
- **Frontend**: Tailwind CSS (CDN), HTMX
- **Media**: Pillow for image uploads

## Project Structure

```
ordering-web/
├── accounts/           # User auth, profiles, user management
├── orders/             # Core app: models, views, services
│   ├── decorators/     # Role-based access decorators
│   ├── services/       # Business logic (pricing, payments, dispatch)
│   └── templatetags/   # Custom template filters
├── ordering_system/    # Django project settings
├── templates/          # All HTML templates (responsive)
├── static/             # Static assets
└── media/              # User-uploaded files
```
