# Fuel Portal — Ordering & Delivery Management

A web-based fuel ordering and delivery management system built with Django. Covers the complete workflow: customer ordering → payment verification → dispatch management → delivery tracking.

## Quick Start (Local)

### Prerequisites
- Python 3.10+
- Git

### Setup

```bash
# 1. Clone
git clone https://github.com/WinefredoSailes/ordering-web-django.git
cd ordering-web

# 2. Virtual environment
python -m venv venv
.\venv\Scripts\activate     # Windows
source venv/bin/activate    # macOS/Linux

# 3. Install
pip install -r requirements.txt

# 4. Database
python manage.py migrate

# 5. Seed sample data
python manage.py seed_data

# 6. Run
python manage.py runserver
```

Open **http://127.0.0.1:8000**.

### Network Access (Office Staff)

```powershell
# Bind to all network interfaces
python manage.py runserver 0.0.0.0:8000
```

Staff access via `http://YOUR_IP:8000/` (run `ipconfig` to find your IP).

---

## Default Test Accounts

| Username | Password | Role |
|----------|----------|------|
| `admin` | `admin123` | Superadmin |
| `cashier1` | `cashier123` | Cashier |
| `hauling1` | `hauling123` | Hauling |
| `driver1` | `driver123` | Driver |
| `customer1` | `customer123` | Customer |

---

## User Guide

### Customer (⛽ Fuel Portal)

**Pages**: Products, My Orders, Messages (💬), Dashboard, My Docs, Profile

| Step | What to do |
|------|-----------|
| **1. Browse Products** | Go to **Products** page. See available fuel types (ADO Diesel, REG Regular, XCS Premium) with prices. |
| **2. Place Order** | Click a product card or **Place Order**. Select product, enter quantity (must be multiple of 500L), delivery address. Submit → order created with PO#. |
| **3. Upload Payment** | Go to **My Orders** → click **View** → upload payment proof photo. Or send it via **Messages** (💬) using the 📎 attachment button — it auto-links to your pending order. |
| **4. Track Status** | **My Orders** table shows: *Awaiting Payment Upload → Ready for Dispatch → Dispatched → In Transit → Delivered*. |
| **5. Chat with Dispatch** | Use **Messages** for inquiries, modifications, or rescheduling. Your conversation is visible to the hauling team. |

### Cashier (💳 Payments)

**Pages**: Dashboard, Payments, Earned Revenue, Unearned Revenue, Profile

| Step | What to do |
|------|-----------|
| **1. Review Payments** | **Payments** page shows uploaded proofs. Filter by status (Uploaded/Approved/Rejected). |
| **2. Verify** | Click **Verify** on a payment. View the uploaded image to confirm it matches the order. |
| **3. Approve** | Click **Approve** → order becomes *Ready for Dispatch*, a unique AR# (Acknowledgement Receipt) is auto-generated. |
| **4. Reject** | Click **Reject** + provide a reason → order reverts to *Awaiting Payment Upload*, customer can re-upload. |
| **5. Revenue Reports** | **Earned Revenue** = delivered orders. **Unearned Revenue** = paid but not yet delivered. Both have date filters. |

### Hauling/Dispatcher (💬 Inbox)

**Pages**: Dashboard, Inbox, Orders, Dispatch, Trips, Tankers, Profile

| Step | What to do |
|------|-----------|
| **1. Inbox (Chat-Ops)** | The **Inbox** is your command center. Conversations from customers appear here. Sort by Unread/Recent/A-Z. |
| **2. Process Requests** | For each message, use action chips: **📦 Order** (create new order with custom pricing), **📋 Modify** (change quantity), **📅 Reschedule** (change delivery date), **💬 Reply** (free-text reply). |
| **3. Orders Page** | Browse all orders. Filter by status (All/Draft/Ready/Dispatched/In Transit/Delivered). Date filter available. |
| **4. Dispatch** | Go to **Dispatch** page. Select a tanker + driver. Pick orders (they must be *Ready for Dispatch*). Assign each order to a compartment. Submit → orders become *Dispatched*, driver marked busy. |
| **5. Trips** | View active/completed trips. See details: tanker, driver, compartment assignments. |
| **6. Tankers** | Manage tanker trucks and compartments (capacities in liters). |

### Driver (🗺️ My Trips)

**Pages**: My Trips, Dashboard, Profile

| Step | What to do |
|------|-----------|
| **1. View Assignments** | **My Trips** shows active trips assigned to you. |
| **2. Mark In Transit** | When you pick up the load, click **Mark In Transit** to notify the customer. |
| **3. Mark Delivered** | After delivery, upload a **delivery proof photo** + notes. Click **Mark Delivered** → order completed, trip auto-completes if all orders delivered, you become available for new trips. |

### Superadmin (Full Control)

**Pages**: Dashboard, Orders, Groups, Pricing, Products, Tankers, Drivers, Users, Logs, Earned Revenue, Unearned Revenue, Profile

| Section | What you can do |
|---------|----------------|
| **Dashboard** | Overview KPIs: total orders, by status, recent activity. |
| **Orders** | View all orders across all customers and statuses. |
| **Groups** | Customer groups for pricing tiers (e.g., Wholesale, Retail). |
| **Pricing** | Set product prices per group or per specific customer. Supports search + product/target/status filters. |
| **Products** | Manage fuel types: shortcut code (ADO/REG/XCS), name, order multiple (500L default). |
| **Tankers** | CRUD for tanker trucks. Each tanker has compartments with individual capacities. |
| **Drivers** | Manage driver profiles: license info, availability. |
| **Users** | Create/edit/delete users for all roles. Assign groups to customers. |
| **Logs** | Full audit trail filtered by action, model, user, and date range. |
| **Revenue** | **Earned Revenue** (delivered, recognized) and **Unearned Revenue** (paid, not delivered) dashboards. |

---

## Workflow Diagram

```
Customer              Cashier              Hauling              Driver
   │                    │                    │                    │
   ├─ Place Order ─────▶│                    │                    │
   │                    │                    │                    │
   ├─ Upload Payment ──▶│                    │                    │
   │                    ├─ Approve ─────────▶│                    │
   │                    │  (AR# generated)   │                    │
   │                    │                    ├─ Dispatch ────────▶│
   │                    │                    │  (trip created)    │
   │                    │                    │                    ├─ In Transit ──┐
   │                    │                    │                    │              │
   │                    │                    │                    ├─ Delivered ──┤
   │                    │                    │                    │  (proof photo)│
   │◀───────────────────┼────────────────────┼────────────────────┘              │
   │                    │                    │                    Trip auto-     │
   │                    │                    │                    completes      │
   │                    │                    │                    Driver freed   │
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Django 5.0, SQLite (dev) / PostgreSQL (prod) |
| Frontend | Tailwind CSS (CDN), HTMX, Alpine.js |
| Auth | Django auth with custom User model (role-based) |
| Media | Pillow for image uploads |

## Project Structure

```
ordering-web/
├── accounts/              # User auth, profiles, management
│   ├── models.py          # Custom User model (roles, groups)
│   └── views.py           # Login, register, profile, user CRUD
├── orders/                # Core application
│   ├── models.py          # Order, Payment, DispatchTrip, Tanker, etc.
│   ├── views.py           # All view functions (60+ endpoints)
│   ├── services/          # Business logic
│   │   ├── order_service.py     # Order creation + pricing
│   │   ├── payment_service.py   # Upload, approve, reject payments
│   │   ├── dispatch_service.py  # Trip creation with capacity validation
│   │   └── pricing_service.py   # Best-price resolution
│   └── decorators/        # Role-based access control
├── templates/             # 60+ HTML templates
│   ├── base.html          # Shared layout (sidebar, nav, theme)
│   ├── accounts/          # Login, register, profile, user mgmt
│   ├── orders/            # All role-specific pages
│   │   ├── customer/      # Customer-facing templates
│   │   ├── cashier/       # Cashier templates
│   │   ├── hauling/       # Hauling/dispatch templates
│   │   ├── driver/        # Driver templates
│   │   ├── admin/         # Superadmin templates
│   │   └── partials/      # Reusable table partials
├── ordering_system/       # Django project settings
├── static/                # Static assets
└── media/                 # User uploads
```
