# Ordering System Specification

## Project Overview
- **Project Name**: Fuel Ordering Portal
- **Type**: Full-stack Django web application
- **Core Functionality**: Digitize fuel ordering operations with customer portals, payment verification, dispatch management, and delivery tracking
- **Target Users**: 200+ customers, cashiers, hauling/dispatchers, drivers, superadmins

## Technology Stack
- Backend: Django 5.x
- Frontend: HTMX + Tailwind CSS
- Database: SQLite3 (development)
- Authentication: Django built-in auth with custom User model

## User Roles & Permissions

### 1. Customer (Public Portal)
- Register/Login
- View products (Premium, Regular, Diesel)
- Place orders with quantity (multiple of 500L)
- Upload payment proof photo
- View order history and status
- Can submit order as "pending" if not paying immediately

### 2. Cashier (Admin Portal)
- View all pending/paid orders
- Verify payment proof (visual verification)
- Mark order as "paid" with acknowledgment number
- View payment proof images

### 3. Hauling/Dispatcher (Admin Portal)
- View all "paid" orders ready for dispatch
- Assign orders to tanker trucks
- Assign drivers to dispatched orders
- Manage tanker trucks (CRUD)
- Manage compartments per truck

### 4. Driver (Restricted Portal)
- View assigned orders
- View delivery locations/addresses
- Mark orders as "delivered"
- Update delivery status

### 5. Superadmin
- Full system access
- Manage all users and roles
- Dashboard overview

## Product Catalog
| Product Name | Type |
|-------------|------|
| Premium | Fuel |
| Regular | Fuel |
| Diesel | Fuel |

## Order Status Flow
```
PENDING (order placed, no payment) → PAID (cashier verified) → DISPATCHED (hauling assigned truck/driver) → DELIVERED (driver marked)
```

## Order Fields
- `po_number`: Auto-generated (PO-YYYYMMDD-XXXXX)
- `ack_number`: Generated upon payment verification (ACK-XXXXX)
- `customer`: FK to User
- `product`: FK to Product
- `quantity_liters`: Integer (must be multiple of 500)
- `delivery_address`: Text
- `status`: PENDING → PAID → DISPATCHED → DELIVERED
- `payment_proof`: Image upload
- `payment_proof_uploaded_at`: DateTime (nullable)
- `paid_at`: DateTime (nullable)
- `acknowledgment_number`: String (nullable)
- `created_at`: DateTime
- `updated_at`: DateTime

## Truck Management
- `truck_number`: Unique identifier (e.g., TK-001)
- `plate_number`: Vehicle plate
- `total_capacity_liters`: Total capacity
- `compartments_count`: 6, 8, 10, 15, etc.
- `is_active`: Boolean

## Compartment Management
- `truck`: FK to Truck
- `compartment_number`: 1, 2, 3...
- `capacity_liters`: 1000, 2000, 4000, etc.
- `assigned_order`: FK to Order (nullable, when dispatched)

## Dispatch Assignment
- `order`: FK to Order
- `truck`: FK to Truck
- `compartment`: FK to Compartment
- `driver`: FK to User (driver role)
- `dispatched_at`: DateTime

## UI/UX Specification

### Customer Portal
- **Header**: Logo, nav (Home, My Orders, Logout), user name
- **Hero**: Welcome message, quick order button
- **Product Cards**: 3 cards (Premium, Regular, Diesel) with product info
- **Order Form**: Modal with product select, quantity input (500L step), address textarea
- **Orders Table**: Po#, product, quantity, status, date, action (upload proof/submit)
- **Color Palette**:
  - Primary: `#1E40AF` (blue-800)
  - Secondary: `#F59E0B` (amber-500)
  - Success: `#10B981` (emerald-500)
  - Warning: `#F59E0B` (amber-500)
  - Error: `#EF4444` (red-500)
  - Background: `#F3F4F6` (gray-100)
  - Card BG: `#FFFFFF`
- **Typography**: Inter font family

### Admin Portal
- **Sidebar**: Dashboard, Orders, Trucks, Drivers, Profile
- **Dashboard**: Stats cards (total orders, pending, paid, dispatched, delivered)
- **Order List**: Filterable table with status tabs
- **Order Detail**: Full order info + payment proof viewer

### Driver Portal
- **Simple Layout**: List of assigned orders with deliver button
- **Map-friendly**: Address display

## Acceptance Criteria

### Customer
- [ ] Can register and login
- [ ] Can view products
- [ ] Can place order with quantity multiple of 500L (validation)
- [ ] Can upload payment proof photo
- [ ] Can submit order (status becomes PENDING)
- [ ] Can view order history

### Cashier
- [ ] Can view PENDING and PAID orders
- [ ] Can verify payment proof and mark as PAID
- [ ] Generates acknowledgment number on verify

### Hauling
- [ ] Can view PAID orders
- [ ] Can create/edit trucks and compartments
- [ ] Can assign order to truck/compartment/driver
- [ ] Changes status to DISPATCHED

### Driver
- [ ] Can view assigned DISPATCHED orders
- [ ] Can mark order as DELIVERED

### General
- [ ] All status transitions logged
- [ ] Responsive design works on mobile
- [ ] HTMX for smooth partial page updates