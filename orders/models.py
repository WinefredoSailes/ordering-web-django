from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class CustomerGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    SHORTCUT_CHOICES = [
        ('ADO', 'ADO - Diesel'),
        ('REG', 'REG - Regular'),
        ('XCS', 'XCS - Premium'),
    ]

    shortcut = models.CharField(max_length=10, unique=True, choices=SHORTCUT_CHOICES)
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    order_multiple = models.IntegerField(default=500, help_text="Order increment in liters")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['shortcut']

    def __str__(self):
        return f"{self.shortcut} - {self.name}"


class ProductPricing(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='pricings')
    customer_group = models.ForeignKey(CustomerGroup, on_delete=models.CASCADE, null=True, blank=True, related_name='pricings')
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name='custom_pricings',
        limit_choices_to={'role': 'customer'}
    )
    price_per_liter = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Product Pricings'

    def __str__(self):
        target = self.customer.username if self.customer else (self.customer_group.name if self.customer_group else 'Default')
        return f"{self.product.shortcut} @ ₱{self.price_per_liter}/L ({target})"


class Tanker(models.Model):
    code = models.CharField(max_length=20, unique=True, verbose_name="Tanker Code")
    plate_number = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} ({self.plate_number})"

    @property
    def total_capacity(self):
        return self.compartments.aggregate(total=models.Sum('capacity'))['total'] or 0

    @property
    def compartments_count(self):
        return self.compartments.count()


class Compartment(models.Model):
    tanker = models.ForeignKey(Tanker, on_delete=models.CASCADE, related_name='compartments')
    number = models.IntegerField(verbose_name="Compartment Number")
    capacity = models.IntegerField(verbose_name="Capacity (Liters)", default=2000)

    class Meta:
        unique_together = ['tanker', 'number']
        ordering = ['tanker', 'number']

    def __str__(self):
        return f"{self.tanker.code} - C{self.number} ({self.capacity}L)"


class Order(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Awaiting Payment Upload'),
        ('ready_for_dispatch', 'Ready for Dispatch'),
        ('dispatched', 'Dispatched'),
        ('in_transit', 'In Transit'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    po_number = models.CharField(max_length=30, unique=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders'
    )
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='orders')
    quantity_liters = models.IntegerField()
    delivery_address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    price_per_liter = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    dispatched_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.po_number} - {self.customer.username}"

    def short_notation(self):
        unit = 1000
        qty = self.quantity_liters / unit
        code = self.product.shortcut[0]
        return f"{qty}{code}"

    @property
    def latest_payment(self):
        return self.payments.order_by('-uploaded_at').first()

    def save(self, *args, **kwargs):
        if not self.po_number:
            last = Order.objects.order_by('-id').first()
            seq = 1 if not last else int(last.po_number.split('-')[-1]) + 1
            from django.utils import timezone
            self.po_number = f"PO-{timezone.now().strftime('%Y%m%d')}-{seq:05d}"
        if self.price_per_liter and self.quantity_liters:
            self.total_amount = self.price_per_liter * self.quantity_liters
        super().save(*args, **kwargs)


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('uploaded', 'Uploaded'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    file = models.ImageField(upload_to='payments/%Y/%m/%d/')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploaded')
    rejection_reason = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='approved_payments'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    acknowledgement_receipt = models.CharField(max_length=30, unique=True, null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Payment #{self.id} - {self.order.po_number} ({self.status})"


class Driver(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='driver_profile', limit_choices_to={'role': 'driver'}
    )
    is_available = models.BooleanField(default=True)
    phone = models.CharField(max_length=20, blank=True)
    license_number = models.CharField(max_length=50, blank=True)
    license_expiry = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({'Available' if self.is_available else 'Busy'})"


class DispatchTrip(models.Model):
    trip_number = models.CharField(max_length=30, unique=True)
    tanker = models.ForeignKey(Tanker, on_delete=models.CASCADE, related_name='trips')
    driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='trips')
    total_loaded_liters = models.IntegerField(default=0)
    scheduled_date = models.DateTimeField(blank=True, null=True)
    dispatched_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='created_trips'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Trip {self.trip_number} - {self.tanker.code}"

    def remaining_capacity(self):
        return self.tanker.total_capacity - self.total_loaded_liters


class DispatchOrder(models.Model):
    trip = models.ForeignKey(DispatchTrip, on_delete=models.CASCADE, related_name='dispatch_orders')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='dispatch_orders')
    compartment = models.ForeignKey(Compartment, on_delete=models.CASCADE, related_name='dispatch_orders')
    liters_loaded = models.IntegerField(default=0)
    delivered_at = models.DateTimeField(blank=True, null=True)
    delivery_notes = models.TextField(blank=True)
    delivery_proof = models.ImageField(upload_to='delivery_proofs/', blank=True, null=True)

    class Meta:
        ordering = ['trip', 'compartment__number']

    def __str__(self):
        return f"{self.trip.trip_number} - {self.order.po_number}"


class CustomerDocument(models.Model):
    DOCUMENT_TYPES = [
        ('coc', 'Certificate of Compliance (COC)'),
        ('cnc', 'Certificate of Non-Coverage (CNC)'),
        ('bfp', 'BFP Certificate'),
        ('business_permit', 'Business Permit'),
        ('dti', 'DTI Permit'),
        ('plate_number', 'Plate Number'),
        ('cr', 'Certificate of Registration (CR)'),
        ('or', 'Official Receipt (OR)'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='customer_documents', limit_choices_to={'role': 'customer'}
    )
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='customer_docs/%Y/%m/%d/')
    notes = models.TextField(blank=True)
    is_verified = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.user.username} - {self.get_document_type_display()}"


class Conversation(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='conversations', limit_choices_to={'role': 'customer'}
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='assigned_conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation with {self.customer.username}"

    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()

    @property
    def unread_count(self):
        return self.messages.filter(is_read=False).exclude(sender=self.assigned_to).count()


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_system = models.BooleanField(default=False, help_text="Auto-generated reply")
    related_order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to='chat_attachments/%Y/%m/%d/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.conversation.customer.username}] {self.content[:60]}"


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=100)
    model_name = models.CharField(max_length=50)
    object_id = models.IntegerField(blank=True, null=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name}"
