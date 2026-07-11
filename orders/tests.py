import io
import tempfile
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from orders.models import (
    CustomerGroup, Product, ProductPricing, Tanker, Compartment,
    Order, Payment, Driver, DispatchTrip, DispatchOrder, AuditLog,
    Conversation, Message
)
from orders.services.order_service import create_order
from orders.services.payment_service import upload_payment, approve_payment, reject_payment
from orders.services.dispatch_service import create_trip, complete_trip

User = get_user_model()


def fake_image(name='test.png'):
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class EndToEndWorkflowTest(TestCase):
    """Full end-to-end workflow covering every role and transition."""

    @classmethod
    def setUpTestData(cls):
        # ── 1. ADMIN SETUP ──────────────────────────────────
        cls.superadmin = User.objects.create_superuser(
            username='admin', password='adminpass', role='superadmin'
        )

        cls.group = CustomerGroup.objects.create(name='Wholesale', description='Wholesale buyers')

        cls.customer = User.objects.create_user(
            username='test_customer', password='custpass',
            role='customer', business_name='Test Corp',
            customer_group=cls.group, phone='09170000001',
            address='123 Main St, Manila'
        )

        cls.cashier = User.objects.create_user(
            username='cashier1', password='cashpass', role='cashier'
        )

        cls.hauling_user = User.objects.create_user(
            username='hauler1', password='haulpass', role='hauling'
        )

        cls.driver_user = User.objects.create_user(
            username='driver1', password='driverpass', role='driver'
        )
        cls.driver = Driver.objects.create(
            user=cls.driver_user, phone='09170000002',
            license_number='DL-001', license_expiry='2027-12-31'
        )

        # ── 2. PRODUCT + PRICING ────────────────────────────
        cls.product = Product.objects.create(
            shortcut='ADO', name='Automotive Diesel Oil',
            order_multiple=500, is_active=True
        )

        ProductPricing.objects.create(
            product=cls.product, customer_group=cls.group,
            price_per_liter=54.50, is_active=True
        )

        # ── 3. TANKER + COMPARTMENTS ────────────────────────
        cls.tanker = Tanker.objects.create(code='TNK-001', plate_number='ABC-1234')
        Compartment.objects.create(tanker=cls.tanker, number=1, capacity=5000)
        Compartment.objects.create(tanker=cls.tanker, number=2, capacity=3000)

    def setUp(self):
        self.client = Client()

    # ══════════════════════════════════════════════════════════
    # STEP 1: CUSTOMER WORKFLOW (Signup → Browse → Order → Pay)
    # ══════════════════════════════════════════════════════════

    def test_01_customer_registration(self):
        """Customer can sign up via the register page."""
        resp = self.client.post(reverse('accounts:register'), {
            'username': 'new_customer',
            'email': 'new@test.com',
            'password1': 'NewCust123!',
            'password2': 'NewCust123!',
            'phone': '09171234567',
            'address': '456 New St, Manila',
            'business_name': 'New Corp Inc.',
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        created = User.objects.get(username='new_customer')
        self.assertEqual(created.role, 'customer')
        self.assertEqual(created.business_name, 'New Corp Inc.')

    def test_02_customer_creates_order(self):
        """Customer can create an order with proper pricing."""
        self.client.login(username='test_customer', password='custpass')
        resp = self.client.post(reverse('orders:create_order'), {
            'product': self.product.id,
            'quantity_liters': 1000,
            'delivery_address': '123 Main St, Manila',
            'notes': 'Please deliver ASAP',
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('PO-', data['po_number'])
        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.product.pk, self.product.pk)
        self.assertEqual(order.quantity_liters, 1000)
        self.assertEqual(float(order.price_per_liter), 54.50)
        self.assertEqual(float(order.total_amount), 54500.0)
        self.assertEqual(order.status, 'draft')
        self.assertEqual(order.notes, 'Please deliver ASAP')

    def test_03_customer_views_order_detail(self):
        """Customer can view their order details."""
        self.client.login(username='test_customer', password='custpass')
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'test notes')
        resp = self.client.get(reverse('orders:order_detail', args=[order.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.po_number)
        self.assertContains(resp, '54.50')
        self.assertContains(resp, '1000')  # template uses {{ order.quantity_liters }} without formatting

    def test_04_customer_uploads_payment(self):
        """Customer can upload a payment proof image."""
        self.client.login(username='test_customer', password='custpass')
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'test notes')
        img = fake_image()
        resp = self.client.post(
            reverse('orders:upload_payment', args=[order.pk]),
            {'payment_file': img}
        )
        self.assertRedirects(resp, reverse('orders:my_orders'))
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, 'uploaded')
        self.assertIsNotNone(payment.file)

    def test_05_quantity_validation(self):
        """Order quantity must be a multiple of product.order_multiple."""
        self.client.login(username='test_customer', password='custpass')
        with self.assertRaises(ValueError):
            create_order(self.customer, self.product, 700, '123 Main St')

    # ══════════════════════════════════════════════════════════
    # STEP 2: CASHIER WORKFLOW (Review → Approve payment)
    # ══════════════════════════════════════════════════════════

    def test_06_cashier_approves_payment(self):
        """Cashier approves payment → order becomes ready_for_dispatch, AR# generated."""
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'pay notes')
        payment = upload_payment(order, fake_image())

        self.client.login(username='cashier1', password='cashpass')
        resp = self.client.post(
            reverse('orders:verify_payment', args=[payment.pk]),
            {'action': 'approve'}
        )
        self.assertRedirects(resp, reverse('orders:cashier_payments'))

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'approved')
        self.assertEqual(payment.approved_by, self.cashier)
        self.assertIsNotNone(payment.processed_at)
        self.assertIsNotNone(payment.acknowledgement_receipt)
        self.assertTrue(payment.acknowledgement_receipt.startswith('AR-'))
        self.assertEqual(order.status, 'ready_for_dispatch')

    def test_07_cashier_rejects_payment(self):
        """Cashier rejects payment → status stays draft, customer can re-upload."""
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'bad pay')
        payment = upload_payment(order, fake_image())

        self.client.login(username='cashier1', password='cashpass')
        resp = self.client.post(
            reverse('orders:verify_payment', args=[payment.pk]),
            {'action': 'reject', 'rejection_reason': 'Blurry image'}
        )
        self.assertRedirects(resp, reverse('orders:cashier_payments'))

        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'rejected')
        self.assertEqual(payment.rejection_reason, 'Blurry image')
        self.assertEqual(order.status, 'draft')

    # ══════════════════════════════════════════════════════════
    # STEP 3: HAULING WORKFLOW (Trip creation)
    # ══════════════════════════════════════════════════════════

    def test_08_hauling_creates_trip(self):
        """Hauling creates a dispatch trip → orders become dispatched, driver busy."""
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'trip test')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)
        order.refresh_from_db()
        self.assertEqual(order.status, 'ready_for_dispatch')

        self.client.login(username='hauler1', password='haulpass')
        resp = self.client.post(reverse('orders:create_trip'), {
            'tanker': self.tanker.id,
            'driver': self.driver.id,
            'orders': [order.id],
            'compartment': [self.tanker.compartments.first().id],
        })
        self.assertRedirects(resp, reverse('orders:hauling_trips'))

        order.refresh_from_db()
        self.assertEqual(order.status, 'dispatched')
        self.assertIsNotNone(order.dispatched_at)

        trip = DispatchTrip.objects.get(tanker=self.tanker)
        self.assertEqual(trip.driver, self.driver)
        self.assertEqual(trip.total_loaded_liters, 1000)
        self.assertEqual(trip.dispatch_orders.count(), 1)

        self.driver.refresh_from_db()
        self.assertFalse(self.driver.is_available)

    def test_09_trip_over_capacity_rejected(self):
        """Creating a trip exceeding tanker capacity raises ValueError."""
        # Tanker has 5000+3000=8000L total. Order for 9000L exceeds total capacity.
        order = create_order(self.customer, self.product, 9000, '123 Main St', 'over cap')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)

        comp = self.tanker.compartments.first()  # 5000L
        with self.assertRaises(ValueError):
            create_trip(
                self.tanker, self.driver,
                [{'order': order, 'compartment': comp}]
            )

    def test_10_trip_compartment_over_capacity_rejected(self):
        """Assigning too many liters to a compartment raises ValueError."""
        order1 = create_order(self.customer, self.product, 4000, 'Addr', 'comp overflow')
        order2 = create_order(self.customer, self.product, 2000, 'Addr', 'comp overflow 2')
        for o in [order1, order2]:
            upload_payment(o, fake_image())
            approve_payment(Payment.objects.get(order=o), self.cashier)

        comp = self.tanker.compartments.first()  # 5000L — but two orders total 6000L
        with self.assertRaises(ValueError):
            create_trip(
                self.tanker, self.driver,
                [
                    {'order': order1, 'compartment': comp},
                    {'order': order2, 'compartment': comp},
                ]
            )

    # ══════════════════════════════════════════════════════════
    # STEP 4: DRIVER WORKFLOW (In-transit → Deliver)
    # ══════════════════════════════════════════════════════════

    def test_11_driver_marks_in_transit(self):
        """Driver marks order as in-transit."""
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'transit test')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)

        comp = self.tanker.compartments.first()
        trip, _ = create_trip(
            self.tanker, self.driver,
            [{'order': order, 'compartment': comp}]
        )
        dispatch_order = trip.dispatch_orders.first()
        do_pk = dispatch_order.pk

        self.client.login(username='driver1', password='driverpass')
        resp = self.client.post(
            reverse('orders:mark_in_transit', args=[do_pk]),
            {'status': 'in_transit'}
        )
        self.assertRedirects(resp, reverse('orders:driver_trips'))

        order.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')

        self.assertTrue(AuditLog.objects.filter(
            action='Marked In Transit', object_id=do_pk
        ).exists())

    def test_12_driver_delivers_order(self):
        """Driver delivers order with proof → trip auto-completes."""
        order = create_order(self.customer, self.product, 1000, '123 Main St', 'delivery test')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)

        comp = self.tanker.compartments.first()
        trip, _ = create_trip(
            self.tanker, self.driver,
            [{'order': order, 'compartment': comp}]
        )
        dispatch_order = trip.dispatch_orders.first()
        dispatch_order.order.status = 'in_transit'
        dispatch_order.order.save()
        do_pk = dispatch_order.pk

        self.client.login(username='driver1', password='driverpass')
        proof_img = fake_image('delivery_proof.png')
        resp = self.client.post(
            reverse('orders:mark_delivered', args=[do_pk]),
            {'delivery_notes': 'Delivered successfully', 'delivery_proof': proof_img}
        )
        self.assertRedirects(resp, reverse('orders:driver_trips'))

        dispatch_order.refresh_from_db()
        order.refresh_from_db()
        trip.refresh_from_db()
        self.driver.refresh_from_db()

        self.assertEqual(order.status, 'delivered')
        self.assertIsNotNone(order.delivered_at)
        self.assertIsNotNone(dispatch_order.delivered_at)
        self.assertEqual(dispatch_order.delivery_notes, 'Delivered successfully')
        self.assertIsNotNone(dispatch_order.delivery_proof)

        # Trip auto-completes when all orders delivered
        self.assertIsNotNone(trip.completed_at)
        self.assertTrue(self.driver.is_available)

        self.assertTrue(AuditLog.objects.filter(
            action='Delivered', object_id=do_pk
        ).exists())

    # ══════════════════════════════════════════════════════════
    # STEP 5: REVENUE DASHBOARDS
    # ══════════════════════════════════════════════════════════

    def test_13_earned_revenue_dashboard(self):
        """Earned Revenue dashboard shows delivered order revenue."""
        order = create_order(self.customer, self.product, 1000, 'Addr', 'rev test')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)
        comp = self.tanker.compartments.first()
        trip, _ = create_trip(self.tanker, self.driver, [{'order': order, 'compartment': comp}])
        do = trip.dispatch_orders.first()
        do.order.status = 'in_transit'; do.order.save()
        do.delivered_at = __import__('django').utils.timezone.now()
        do.delivery_notes = 'done'; do.save()
        do.order.status = 'delivered'; do.order.delivered_at = __import__('django').utils.timezone.now()
        do.order.save()
        trip.completed_at = __import__('django').utils.timezone.now()
        trip.save()
        self.driver.is_available = True; self.driver.save()

        self.client.login(username='cashier1', password='cashpass')
        resp = self.client.get(reverse('orders:earned_revenue'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '₱54,500.00')
        # liters use {{ s.liters }}L — no comma formatting
        self.assertContains(resp, '1000L')

    def test_14_unearned_revenue_dashboard(self):
        """Unearned Revenue shows paid-but-undelivered orders."""
        order = create_order(self.customer, self.product, 1000, 'Addr', 'unearned')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)

        self.client.login(username='cashier1', password='cashpass')
        resp = self.client.get(reverse('orders:unearned_revenue'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.po_number)
        self.assertContains(resp, 'Test Corp')

    # ══════════════════════════════════════════════════════════
    # STEP 6: AUDIT LOG
    # ══════════════════════════════════════════════════════════

    def test_15_audit_logs_recorded(self):
        """All key actions generate audit log entries."""
        order = create_order(self.customer, self.product, 1000, 'Addr', 'audit test')
        upload_payment(order, fake_image())
        approve_payment(Payment.objects.get(order=order), self.cashier)
        comp = self.tanker.compartments.first()
        trip, _ = create_trip(self.tanker, self.driver, [{'order': order, 'compartment': comp}])
        do = trip.dispatch_orders.first()
        do.order.status = 'in_transit'; do.order.save()
        do.delivered_at = __import__('django').utils.timezone.now()
        do.delivery_notes = 'done'; do.save()
        do.order.status = 'delivered'; do.order.delivered_at = __import__('django').utils.timezone.now()
        do.order.save()
        trip.completed_at = __import__('django').utils.timezone.now()
        trip.save()

        logs = AuditLog.objects.filter(object_id=order.pk)
        actions = set(logs.values_list('action', flat=True))
        self.assertIn('ORDER_CREATED', actions)
        self.assertIn('PAYMENT_UPLOADED', actions)
        self.assertIn('PAYMENT_APPROVED', actions)
        self.assertIn('TRIP_CREATED', actions)

    # ══════════════════════════════════════════════════════════
    # STEP 7: CHAT OPS — CONVERSATIONS & MESSAGES
    # ══════════════════════════════════════════════════════════

    def test_16_customer_sends_message(self):
        """Customer can send a message and it appears in hauling ops."""
        self.client.login(username='test_customer', password='custpass')
        resp = self.client.post(reverse('orders:customer_messages'), {
            'content': 'Hello, I need 1000L ADO please.',
        })
        self.assertRedirects(resp, reverse('orders:customer_messages'))

        conv = Conversation.objects.get(customer=self.customer)
        self.assertEqual(conv.messages.count(), 1)
        msg = conv.messages.first()
        self.assertEqual(msg.content, 'Hello, I need 1000L ADO please.')
        self.assertEqual(msg.sender, self.customer)
        self.assertFalse(msg.is_system)

        # Hauling sees the message
        self.client.login(username='hauler1', password='haulpass')
        resp = self.client.get(reverse('orders:hauling_ops_chat'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Hello, I need 1000L ADO please.')

    def test_17_hualing_preview_order(self):
        """Hauling can preview and create an order from chat."""
        conv = Conversation.objects.create(customer=self.customer)

        self.client.login(username='hauler1', password='haulpass')
        chat_url = reverse('orders:hauling_ops_chat')
        resp = self.client.post(
            reverse('orders:hauling_preview_order', args=[conv.id]),
            {
                'product': self.product.id,
                'quantity': 2000,
                'price': 52.00,
                'po_number': 'PO-MANUAL-001',
                'notes': 'via chat',
            }
        )
        # Note: the form in the view uses 'quantity' and 'price' (not quantity_liters / price_per_liter)
        self.assertRedirects(resp, f'{chat_url}?with={conv.id}')

        order = Order.objects.get(po_number='PO-MANUAL-001')
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.quantity_liters, 2000)
        self.assertEqual(float(order.price_per_liter), 52.00)

    # ══════════════════════════════════════════════════════════
    # STEP 8: IN-CHAT PAYMENT UPLOAD
    # ══════════════════════════════════════════════════════════

    def test_18_customer_attaches_payment_in_chat(self):
        """Uploading a file in chat attaches it to the active order."""
        order = create_order(self.customer, self.product, 1000, 'Addr', 'chat pay')
        Conversation.objects.create(customer=self.customer)

        self.client.login(username='test_customer', password='custpass')
        img = fake_image('chat_payment.png')
        resp = self.client.post(reverse('orders:customer_messages'), {
            'payment_file': img,
        })
        self.assertRedirects(resp, reverse('orders:customer_messages'))

        # Payment should be created for the order
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, 'uploaded')

        # System message should mention the payment
        conv = Conversation.objects.get(customer=self.customer)
        sys_msg = conv.messages.filter(is_system=True).first()
        self.assertIsNotNone(sys_msg)
        self.assertIn(order.po_number, sys_msg.content)
        self.assertIn('uploaded', sys_msg.content)

    # ══════════════════════════════════════════════════════════
    # STEP 9: COMPLETE END-TO-END (single test, full chain)
    # ══════════════════════════════════════════════════════════

    def test_99_full_e2e_chain(self):
        """Complete end-to-end: order → pay → approve → dispatch → deliver → revenue."""
        # ── 1. Customer creates order ──
        self.client.login(username='test_customer', password='custpass')
        self.client.post(reverse('orders:create_order'), {
            'product': self.product.id,
            'quantity_liters': 2000,
            'delivery_address': 'E2E Test Address',
            'notes': 'End-to-end test',
        })
        order = Order.objects.get(customer=self.customer)
        self.assertEqual(order.status, 'draft')

        # ── 2. Customer uploads payment ──
        self.client.post(
            reverse('orders:upload_payment', args=[order.pk]),
            {'payment_file': fake_image('e2e_pay.png')}
        )
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, 'uploaded')

        # ── 3. Cashier approves payment ──
        self.client.login(username='cashier1', password='cashpass')
        self.client.post(
            reverse('orders:verify_payment', args=[payment.pk]),
            {'action': 'approve'}
        )
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'approved')
        self.assertIsNotNone(payment.acknowledgement_receipt)
        self.assertEqual(order.status, 'ready_for_dispatch')

        # ── 4. Hauling dispatches ──
        self.client.login(username='hauler1', password='haulpass')
        self.client.post(reverse('orders:create_trip'), {
            'tanker': self.tanker.id,
            'driver': self.driver.id,
            'orders': [order.id],
            'compartment': [self.tanker.compartments.first().id],
        })
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispatched')
        trip = DispatchTrip.objects.get(tanker=self.tanker)

        # ── 5. Driver marks in-transit ──
        do = trip.dispatch_orders.first()
        self.client.login(username='driver1', password='driverpass')
        self.client.post(
            reverse('orders:mark_in_transit', args=[do.pk]),
            {'status': 'in_transit'}
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')

        # ── 6. Driver delivers ──
        self.client.post(
            reverse('orders:mark_delivered', args=[do.pk]),
            {'delivery_notes': 'E2E delivered', 'delivery_proof': fake_image('e2e_delivery.png')}
        )
        order.refresh_from_db()
        do.refresh_from_db()
        trip.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertIsNotNone(order.delivered_at)
        self.assertIsNotNone(do.delivered_at)
        self.assertIsNotNone(do.delivery_proof)
        self.assertIsNotNone(trip.completed_at)
        self.assertTrue(self.driver.is_available)

        # ── 7. Revenue dashboards reflect the delivery ──
        self.client.login(username='cashier1', password='cashpass')
        resp = self.client.get(reverse('orders:earned_revenue'))
        self.assertContains(resp, order.po_number)
        self.assertContains(resp, '2000L')

        # ── 8. Audit logs present ──
        self.assertTrue(AuditLog.objects.filter(action='ORDER_CREATED', object_id=order.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='PAYMENT_UPLOADED', object_id=payment.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='PAYMENT_APPROVED', object_id=payment.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='TRIP_CREATED').exists())
        self.assertTrue(AuditLog.objects.filter(action='Marked In Transit').exists())
        self.assertTrue(AuditLog.objects.filter(action='Delivered').exists())

    # ══════════════════════════════════════════════════════════
    # STEP 10: SUPERADMIN GOD MODE (Option A)
    # ══════════════════════════════════════════════════════════

    def test_superadmin_god_mode_covers_all_roles(self):
        """Superadmin can act as cashier → hauling → driver across the full chain."""
        # ── Prerequisite: customer creates order + uploads payment ──
        self.client.login(username='test_customer', password='custpass')
        self.client.post(reverse('orders:create_order'), {
            'product': self.product.id,
            'quantity_liters': 1500,
            'delivery_address': 'God Mode Address',
            'notes': 'god mode test',
        })
        order = Order.objects.get(customer=self.customer)
        self.client.post(
            reverse('orders:upload_payment', args=[order.pk]),
            {'payment_file': fake_image('god_pay.png')}
        )
        payment = Payment.objects.get(order=order)

        # ── 1. Superadmin as CASHIER: browse payments, approve ──
        self.client.login(username='admin', password='adminpass')

        resp = self.client.get(reverse('orders:cashier_payments'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.po_number)

        resp = self.client.post(
            reverse('orders:verify_payment', args=[payment.pk]),
            {'action': 'approve'}
        )
        self.assertRedirects(resp, reverse('orders:cashier_payments'))
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, 'approved')
        self.assertEqual(order.status, 'ready_for_dispatch')

        # ── 2. Superadmin as HAULING: orders page, create trip ──
        resp = self.client.get(reverse('orders:hauling_orders'))
        self.assertEqual(resp.status_code, 200)

        resp = self.client.post(reverse('orders:create_trip'), {
            'tanker': self.tanker.id,
            'driver': self.driver.id,
            'orders': [order.id],
            'compartment': [self.tanker.compartments.first().id],
        })
        self.assertRedirects(resp, reverse('orders:hauling_trips'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'dispatched')
        trip = DispatchTrip.objects.get(tanker=self.tanker)

        # ── 3. Superadmin as DRIVER: mark in-transit, deliver ──
        do = trip.dispatch_orders.first()

        resp = self.client.post(
            reverse('orders:mark_in_transit', args=[do.pk]),
            {'status': 'in_transit'}
        )
        self.assertRedirects(resp, reverse('orders:driver_trips'))
        order.refresh_from_db()
        self.assertEqual(order.status, 'in_transit')

        resp = self.client.post(
            reverse('orders:mark_delivered', args=[do.pk]),
            {'delivery_notes': 'Superadmin delivered', 'delivery_proof': fake_image('god_delivery.png')}
        )
        self.assertRedirects(resp, reverse('orders:driver_trips'))
        order.refresh_from_db()
        do.refresh_from_db()
        trip.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(order.status, 'delivered')
        self.assertIsNotNone(do.delivery_proof)
        self.assertIsNotNone(trip.completed_at)
        self.assertTrue(self.driver.is_available)

        # ── 4. Superadmin checks revenue dashboards ──
        resp = self.client.get(reverse('orders:earned_revenue'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, order.po_number)

        resp = self.client.get(reverse('orders:unearned_revenue'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, order.po_number)  # already delivered

        # ── 5. Superadmin checks audit logs ──
        resp = self.client.get(reverse('orders:audit_logs'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(AuditLog.objects.filter(action='ORDER_CREATED', object_id=order.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='PAYMENT_APPROVED', object_id=payment.pk).exists())
        self.assertTrue(AuditLog.objects.filter(action='TRIP_CREATED').exists())

        # ── 6. Superadmin accesses inbox ──
        resp = self.client.get(reverse('orders:hauling_ops_chat'))
        self.assertEqual(resp.status_code, 200)

        # ── 7. Superadmin can also reject a payment (cashier duty) ──
        self.client.login(username='test_customer', password='custpass')
        self.client.post(reverse('orders:create_order'), {
            'product': self.product.id,
            'quantity_liters': 500,
            'delivery_address': 'Reject Test',
            'notes': 'reject me',
        })
        order2 = Order.objects.exclude(pk=order.pk).get(customer=self.customer)
        self.client.post(
            reverse('orders:upload_payment', args=[order2.pk]),
            {'payment_file': fake_image('reject_pay.png')}
        )
        payment2 = Payment.objects.get(order=order2)

        self.client.login(username='admin', password='adminpass')
        resp = self.client.post(
            reverse('orders:verify_payment', args=[payment2.pk]),
            {'action': 'reject', 'rejection_reason': 'Proof not clear enough'}
        )
        self.assertRedirects(resp, reverse('orders:cashier_payments'))
        payment2.refresh_from_db()
        order2.refresh_from_db()
        self.assertEqual(payment2.status, 'rejected')
        self.assertEqual(payment2.rejection_reason, 'Proof not clear enough')
        self.assertEqual(order2.status, 'draft')
