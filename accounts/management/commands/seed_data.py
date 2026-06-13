from django.core.management.base import BaseCommand
from accounts.models import User
from orders.models import Product, CustomerGroup, ProductPricing


class Command(BaseCommand):
    help = 'Seeds the database with initial data'

    def handle(self, *args, **options):
        # ── Products ──
        products_data = [
            {'shortcut': 'XCS', 'name': 'Premium', 'description': 'High-quality premium fuel for superior engine performance', 'order_multiple': 500},
            {'shortcut': 'REG', 'name': 'Regular', 'description': 'Standard regular fuel for everyday use', 'order_multiple': 500},
            {'shortcut': 'ADO', 'name': 'Diesel', 'description': 'Diesel fuel for diesel engines', 'order_multiple': 1000},
        ]
        for p in products_data:
            prod, created = Product.objects.get_or_create(
                shortcut=p['shortcut'],
                defaults={'name': p['name'], 'description': p['description'], 'order_multiple': p['order_multiple']}
            )
            if not created:
                prod.name = p['name']
                prod.description = p['description']
                prod.order_multiple = p['order_multiple']
                prod.save()

        # ── Customer Group ──
        group, _ = CustomerGroup.objects.get_or_create(name='Default', defaults={'description': 'Default customer group'})

        # ── Default Pricing ──
        for product in Product.objects.all():
            ProductPricing.objects.get_or_create(
                product=product, customer_group=group, is_active=True,
                defaults={'price_per_liter': 54.00}
            )

        # ── Test Users ──
        users = [
            {'username': 'admin',     'password': 'admin123',     'role': 'superadmin', 'is_superuser': True,  'is_staff': True},
            {'username': 'cashier1',  'password': 'cashier123',   'role': 'cashier'},
            {'username': 'hauling1',  'password': 'hauling123',   'role': 'hauling'},
            {'username': 'driver1',   'password': 'driver123',    'role': 'driver'},
            {'username': 'customer1', 'password': 'customer123',  'role': 'customer',   'business_name': "Juan's Trading",       'customer_group': group},
            {'username': 'customer2', 'password': 'customer123',  'role': 'customer',   'business_name': "Maria's Gasoline Shop", 'customer_group': group},
        ]
        for u in users:
            user = User.objects.filter(username=u['username']).first()
            if user:
                changed = False
                for attr in ('role', 'business_name', 'address', 'phone'):
                    val = u.get(attr)
                    if val and getattr(user, attr) != val:
                        setattr(user, attr, val)
                        changed = True
                if u.get('is_superuser') and (not user.is_superuser or not user.is_staff):
                    user.is_superuser = True
                    user.is_staff = True
                    changed = True
                if u.get('customer_group') and user.customer_group != u['customer_group']:
                    user.customer_group = u['customer_group']
                    changed = True
                if changed:
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f"Updated user '{u['username']}' ({u['role']})"))
            else:
                user = User.objects.create_user(
                    username=u['username'],
                    password=u['password'],
                    role=u['role'],
                    business_name=u.get('business_name', ''),
                    address='123 Sample Street, City' if u['role'] == 'customer' else '',
                    phone='09171234567',
                )
                if u.get('is_superuser'):
                    user.is_superuser = True
                    user.is_staff = True
                    user.save()
                if u.get('customer_group'):
                    user.customer_group = u['customer_group']
                    user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user '{u['username']}' ({u['role']})"))

        self.stdout.write(self.style.SUCCESS('Seeding complete!'))