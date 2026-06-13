"""
Seed script: creates initial products, admin user, and sample data.
Run: py manage.py shell < seed.py
"""
import os
import django
os.environ['DJANGO_SETTINGS_MODULE'] = 'ordering_system.settings'
django.setup()

from django.contrib.auth import get_user_model
from orders.models import Product, CustomerGroup, ProductPricing, Tanker, Compartment, Driver

User = get_user_model()

# ── Create superadmin ──
if not User.objects.filter(username='admin').exists():
    admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin123', role='superadmin')
    admin.phone = '09170000000'
    admin.save()
    print('Created superadmin: admin / admin123')

# ── Create sample users for each role ──
users_data = [
    ('cashier1', 'password123', 'cashier'),
    ('hauling1', 'password123', 'hauling'),
    ('driver1', 'password123', 'driver'),
    ('customer1', 'password123', 'customer'),
]
for uname, pwd, role in users_data:
    if not User.objects.filter(username=uname).exists():
        user = User.objects.create_user(uname, f'{uname}@example.com', pwd, role=role)
        user.phone = f'0917000000{role[0]}'
        user.save()
        print(f'Created {role}: {uname} / {pwd}')

# ── Create Products ──
products_data = [
    ('ADO', 'Diesel', 500),
    ('REG', 'Regular', 500),
    ('XCS', 'Premium', 1000),
]
for sc, name, mult in products_data:
    Product.objects.get_or_create(shortcut=sc, defaults={'name': name, 'order_multiple': mult})
    print(f'Product: {sc} - {name} ({mult}L increments)')

# ── Customer Groups ──
groups_data = ['Urban Area A', 'Urban Area B', 'Provincial Zone 1', 'Provincial Zone 2']
for g in groups_data:
    CustomerGroup.objects.get_or_create(name=g)
    print(f'Group: {g}')

# ── Tankers with compartments ──
tanker_data = [
    ('TNK-001', 'ABC-1234', [(1, 1000), (2, 1000), (3, 1000), (4, 1000), (5, 1000), (6, 1000)]),
    ('TNK-002', 'XYZ-5678', [(1, 1500), (2, 1500), (3, 1500), (4, 1500)]),
    ('TNK-003', 'DEF-9012', [(1, 2000), (2, 2000), (3, 2000)]),
]
for code, plate, comps in tanker_data:
    tanker, created = Tanker.objects.get_or_create(code=code, defaults={'plate_number': plate})
    if created:
        for num, cap in comps:
            Compartment.objects.create(tanker=tanker, number=num, capacity=cap)
        print(f'Tanker: {code} ({plate}) - {tanker.total_capacity}L total')

# ── Drivers ──
driver_user = User.objects.filter(role='driver').first()
if driver_user and not Driver.objects.filter(user=driver_user).exists():
    Driver.objects.create(user=driver_user, is_available=True, phone='09171111111', license_number='L-001-2024')
    print(f'Driver profile created for {driver_user.username}')

print('\nSeed complete!')
