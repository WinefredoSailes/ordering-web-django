from datetime import datetime
from django.db import models
from django.db.models import Sum, Count, Avg, Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from .decorators.roles import role_required, cashier_required, hauling_required, superadmin_required
from .models import Product, ProductPricing, CustomerGroup, Tanker, Compartment, Order, Payment, Driver, DispatchTrip, DispatchOrder, CustomerDocument, AuditLog, Conversation, Message
from .services.pricing_service import get_best_price
from .services.order_service import create_order
from .services.payment_service import upload_payment, approve_payment, reject_payment
from .services.dispatch_service import create_trip, complete_trip

User = get_user_model()


# ─── Home ────────────────────────────────────────────────────────────

def home(request):
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    redirect_map = {
        'customer': 'orders:products',
        'cashier': 'orders:cashier_dashboard',
        'hauling': 'orders:hauling_dashboard',
        'driver': 'orders:driver_dashboard',
        'superadmin': 'orders:superadmin_dashboard',
    }
    return redirect(redirect_map.get(request.user.role, 'orders:superadmin_dashboard'))


# ─── Customer Views ─────────────────────────────────────────────────

@login_required
@role_required('customer')
def products(request):
    products = Product.objects.filter(is_active=True)
    pricing = {}
    if request.user.customer_group_id:
        for p in ProductPricing.objects.filter(
            customer_group_id=request.user.customer_group_id, is_active=True
        ).select_related('product'):
            pricing[p.product_id] = str(p.price_per_liter)
    return render(request, 'orders/products.html', {'products': products, 'pricing': pricing})


@login_required
@role_required('customer')
def create_order_view(request):
    if request.method == 'POST':
        product_id = request.POST.get('product')
        quantity = request.POST.get('quantity_liters')
        address = request.POST.get('delivery_address')
        notes = request.POST.get('notes', '')

        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid quantity'}, status=400)

        product = get_object_or_404(Product, id=product_id)
        if quantity <= 0 or quantity % product.order_multiple != 0:
            return JsonResponse({'error': f'Must be multiple of {product.order_multiple}L for {product.shortcut}'}, status=400)

        order = create_order(request.user, product, quantity, address, notes, request)
        return JsonResponse({
            'success': True,
            'message': f'Order {order.po_number} created! Upload payment proof to proceed.',
            'order_id': order.pk,
            'po_number': order.po_number,
        })

    products = Product.objects.filter(is_active=True)
    pricing = {}
    if request.user.customer_group_id:
        for p in ProductPricing.objects.filter(
            customer_group_id=request.user.customer_group_id, is_active=True
        ).select_related('product'):
            pricing[p.product_id] = str(p.price_per_liter)
    preselected = request.GET.get('product')
    return render(request, 'orders/create_order.html', {
        'products': products, 'pricing': pricing, 'preselected': preselected,
    })


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if order.customer != request.user and not request.user.role in ('hauling', 'cashier', 'superadmin', 'driver'):
        return render(request, '403.html', status=403)

    payments = order.payments.all()
    latest = payments.first()
    dispatch_orders = order.dispatch_orders.select_related('trip', 'trip__tanker', 'trip__driver', 'compartment').all()

    return render(request, 'orders/order_detail.html', {
        'order': order,
        'payments': payments,
        'latest_payment': latest,
        'dispatch_orders': dispatch_orders,
    })


@login_required
@role_required('customer')
def my_orders(request):
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            orders = orders.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            orders = orders.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass
    return render(request, 'orders/my_orders.html', {'orders': orders, 'filters': request.GET})


@login_required
@role_required('customer')
def upload_payment_view(request, pk):
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    if request.method == 'POST' and request.FILES.get('payment_file'):
        upload_payment(order, request.FILES['payment_file'], request)
        messages.success(request, 'Payment proof uploaded! Waiting for cashier verification.')
    return redirect('orders:my_orders')


@login_required
@role_required('customer')
def customer_dashboard(request):
    orders = Order.objects.filter(customer=request.user)
    payments = Payment.objects.filter(order__customer=request.user)
    stats = {
        'draft': orders.filter(status='draft').count(),
        'ready': orders.filter(status='ready_for_dispatch').count(),
        'dispatched': orders.filter(status='dispatched').count(),
        'in_transit': orders.filter(status='in_transit').count(),
        'delivered': orders.filter(status='delivered').count(),
        'pending_payments': payments.filter(status='uploaded').count(),
        'approved_payments': payments.filter(status='approved').count(),
        'rejected_payments': payments.filter(status='rejected').count(),
    }
    recent = orders.order_by('-created_at')[:10]
    return render(request, 'orders/dashboard_customer.html', {'stats': stats, 'orders': recent})


@login_required
@role_required('customer')
def customer_documents(request):
    docs = CustomerDocument.objects.filter(user=request.user)
    if request.method == 'POST':
        doc_type = request.POST.get('document_type')
        doc_file = request.FILES.get('file')
        notes = request.POST.get('notes', '')
        if doc_type and doc_file:
            if not doc_file.name.lower().endswith('.pdf'):
                messages.error(request, 'Only PDF files are allowed.')
                return redirect('orders:customer_documents')
            CustomerDocument.objects.create(
                user=request.user,
                document_type=doc_type,
                file=doc_file,
                notes=notes,
            )
            messages.success(request, 'Document uploaded!')
        else:
            messages.error(request, 'Please select a document type and file.')
        return redirect('orders:customer_documents')
    return render(request, 'orders/customer/documents.html', {'docs': docs})


@login_required
@role_required('customer')
def customer_document_delete(request, pk):
    doc = get_object_or_404(CustomerDocument, pk=pk, user=request.user)
    doc.delete()
    messages.success(request, 'Document deleted.')
    return redirect('orders:customer_documents')


# ─── Cashier Views ──────────────────────────────────────────────────

@login_required
@cashier_required
def cashier_dashboard(request):
    stats = {
        'pending': Payment.objects.filter(status='uploaded').count(),
        'approved_today': Payment.objects.filter(status='approved', processed_at__date=timezone.now().date()).count(),
        'rejected': Payment.objects.filter(status='rejected').count(),
    }
    pending_payments = Payment.objects.filter(status='uploaded').select_related('order__customer', 'order__product')[:10]
    return render(request, 'orders/dashboard_cashier.html', {'stats': stats, 'pending_payments': pending_payments})


@login_required
@cashier_required
def cashier_payments(request):
    status_filter = request.GET.get('status', 'uploaded')
    payments = Payment.objects.filter(status=status_filter).select_related('order__customer', 'order__product').order_by('-uploaded_at')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            payments = payments.filter(uploaded_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            payments = payments.filter(uploaded_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass
    return render(request, 'orders/cashier/payments.html', {'payments': payments, 'current_status': status_filter, 'filters': request.GET})


@login_required
@cashier_required
def verify_payment_view(request, pk):
    payment = get_object_or_404(Payment, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'approve':
            approve_payment(payment, request.user, request)
            messages.success(request, f'Payment approved! Order {payment.order.po_number} is ready for dispatch.')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', 'Payment proof unclear. Please upload a clearer image.')
            reject_payment(payment, reason, request)
            messages.warning(request, 'Payment rejected. Customer will be notified.')
        return redirect('orders:cashier_payments')

    return render(request, 'orders/cashier/verify_payment.html', {'payment': payment})


# ─── Hauling Views ──────────────────────────────────────────────────

@login_required
@hauling_required
def hauling_dashboard(request):
    stats = {
        'ready': Order.objects.filter(status='ready_for_dispatch').count(),
        'dispatched': Order.objects.filter(status='dispatched').count(),
        'in_transit': Order.objects.filter(status='in_transit').count(),
        'delivered': Order.objects.filter(status='delivered').count(),
        'tankers': Tanker.objects.filter(is_active=True).count(),
        'available_drivers': Driver.objects.filter(is_available=True).count(),
    }
    orders = Order.objects.filter(status='ready_for_dispatch').select_related('customer', 'product')[:10]
    return render(request, 'orders/dashboard_hauling.html', {'stats': stats, 'orders': orders})


@login_required
@hauling_required
def hauling_orders(request):
    status_filter = request.GET.get('status', '')
    orders = Order.objects.select_related('customer', 'product')
    if status_filter:
        orders = orders.filter(status=status_filter)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            orders = orders.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            orders = orders.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass
    return render(request, 'orders/hauling/orders.html', {'orders': orders, 'current_status': status_filter, 'filters': request.GET})


@login_required
@hauling_required
def create_trip_view(request):
    if request.method == 'POST':
        tanker_id = request.POST.get('tanker')
        driver_id = request.POST.get('driver')
        order_ids = request.POST.getlist('orders')
        compartment_ids = request.POST.getlist('compartment')

        tanker = get_object_or_404(Tanker, id=tanker_id, is_active=True)
        driver = get_object_or_404(Driver, id=driver_id, is_available=True)

        if not driver.is_available:
            messages.error(request, 'Selected driver is not available.')
            return redirect('orders:create_trip')

        assignments = []
        for oid, cid in zip(order_ids, compartment_ids):
            order = get_object_or_404(Order, id=oid, status='ready_for_dispatch')
            compartment = get_object_or_404(Compartment, id=cid, tanker=tanker)
            assignments.append({'order': order, 'compartment': compartment})

        try:
            trip, warnings = create_trip(tanker, driver, assignments, created_by=request.user, request=request)
            for w in warnings:
                messages.warning(request, w)
            messages.success(request, f'Trip {trip.trip_number} created! {trip.total_loaded_liters}L loaded.')
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('orders:create_trip')

        return redirect('orders:hauling_trips')

    tankers = Tanker.objects.filter(is_active=True).prefetch_related('compartments')
    drivers = Driver.objects.filter(is_available=True).select_related('user')
    orders = Order.objects.filter(status='ready_for_dispatch').select_related('customer', 'product')
    return render(request, 'orders/hauling/create_trip.html', {
        'tankers': tankers,
        'drivers': drivers,
        'orders': orders,
    })


@login_required
@hauling_required
def hauling_trips(request):
    trips = DispatchTrip.objects.select_related('tanker', 'driver__user').prefetch_related(
        'dispatch_orders__order__product', 'dispatch_orders__compartment'
    ).order_by('-created_at')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            trips = trips.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            trips = trips.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass
    return render(request, 'orders/hauling/trips.html', {'trips': trips, 'filters': request.GET})


@login_required
@hauling_required
def trip_detail(request, pk):
    trip = get_object_or_404(DispatchTrip, pk=pk)
    return render(request, 'orders/hauling/trip_detail.html', {'trip': trip})


# ─── Tanker Management ──────────────────────────────────────────────

@login_required
@hauling_required
def tanker_list(request):
    tankers = Tanker.objects.prefetch_related('compartments').order_by('-created_at')
    return render(request, 'orders/hauling/tankers.html', {'tankers': tankers})


@login_required
@hauling_required
def tanker_create(request):
    if request.method == 'POST':
        tanker = Tanker.objects.create(
            code=request.POST.get('code'),
            plate_number=request.POST.get('plate_number'),
        )
        messages.success(request, f'Tanker {tanker.code} created! Add compartments now.')
        return redirect('orders:tanker_detail', pk=tanker.pk)
    return render(request, 'orders/hauling/tanker_form.html')


@login_required
@hauling_required
def tanker_detail(request, pk):
    tanker = get_object_or_404(Tanker, pk=pk)
    return render(request, 'orders/hauling/tanker_detail.html', {'tanker': tanker})


@login_required
@hauling_required
def tanker_edit(request, pk):
    tanker = get_object_or_404(Tanker, pk=pk)
    if request.method == 'POST':
        tanker.code = request.POST.get('code')
        tanker.plate_number = request.POST.get('plate_number')
        tanker.is_active = request.POST.get('is_active') == 'on'
        tanker.save()
        messages.success(request, 'Tanker updated!')
        return redirect('orders:tanker_list')
    return render(request, 'orders/hauling/tanker_form.html', {'tanker': tanker})


@login_required
@hauling_required
def tanker_delete(request, pk):
    tanker = get_object_or_404(Tanker, pk=pk)
    tanker.delete()
    messages.success(request, 'Tanker deleted!')
    return redirect('orders:tanker_list')


@login_required
@hauling_required
def compartment_add(request, pk):
    tanker = get_object_or_404(Tanker, pk=pk)
    if request.method == 'POST':
        num = int(request.POST.get('number'))
        if tanker.compartments.filter(number=num).exists():
            messages.error(request, f'Compartment {num} already exists!')
        else:
            Compartment.objects.create(
                tanker=tanker,
                number=num,
                capacity=request.POST.get('capacity', 2000),
            )
            messages.success(request, 'Compartment added!')
        return redirect('orders:tanker_detail', pk=pk)
    return render(request, 'orders/hauling/compartment_form.html', {'tanker': tanker})


@login_required
@hauling_required
def compartment_delete(request, pk, comp_id):
    compartment = get_object_or_404(Compartment, pk=comp_id, tanker_id=pk)
    compartment.delete()
    messages.success(request, 'Compartment deleted!')
    return redirect('orders:tanker_detail', pk=pk)


# ─── Driver Views ───────────────────────────────────────────────────

@login_required
@role_required('driver')
def driver_dashboard(request):
    driver_filter = {} if request.user.is_superuser else {'driver__user': request.user}
    active = DispatchTrip.objects.filter(completed_at__isnull=True, **driver_filter).count()
    pending = DispatchOrder.objects.filter(delivered_at__isnull=True, trip__driver__user__isnull=False).count()
    if not request.user.is_superuser:
        pending = DispatchOrder.objects.filter(trip__driver__user=request.user, delivered_at__isnull=True).count()
    completed = 0  # simpler to skip
    stats = {'active_trips': active, 'pending': pending, 'completed': completed}
    trips = DispatchTrip.objects.filter(**driver_filter).select_related('tanker').order_by('-created_at')[:5]
    return render(request, 'orders/dashboard_driver.html', {'stats': stats, 'trips': trips})


@login_required
@role_required('driver')
def driver_trips(request):
    driver_filter = {} if request.user.is_superuser else {'driver__user': request.user}
    trips = DispatchTrip.objects.filter(
        completed_at__isnull=True, **driver_filter
    ).select_related('tanker').prefetch_related(
        'dispatch_orders__order__product', 'dispatch_orders__compartment'
    ).order_by('-created_at')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            trips = trips.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            trips = trips.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass
    return render(request, 'orders/driver/trips.html', {'trips': trips, 'filters': request.GET})


@login_required
@role_required('driver')
def mark_in_transit(request, pk):
    qs = DispatchOrder.objects.filter(pk=pk)
    if not request.user.is_superuser:
        qs = qs.filter(trip__driver__user=request.user)
    do = get_object_or_404(qs)
    if request.method == 'POST':
        do.order.status = 'in_transit'
        do.order.save()
        AuditLog.objects.create(
            user=request.user, action='Marked In Transit',
            model_name='DispatchOrder', object_id=do.pk,
            details=f"Order {do.order.po_number} marked in transit",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Order {do.order.po_number} marked in transit.')
        return redirect('orders:driver_trips')
    return render(request, 'orders/driver/mark_in_transit.html', {'dispatch_order': do})


@login_required
@role_required('driver')
def mark_delivered(request, pk):
    qs = DispatchOrder.objects.filter(pk=pk)
    if not request.user.is_superuser:
        qs = qs.filter(trip__driver__user=request.user)
    do = get_object_or_404(qs)
    if request.method == 'POST':
        do.delivered_at = timezone.now()
        do.delivery_notes = request.POST.get('delivery_notes', '')
        if request.FILES.get('delivery_proof'):
            do.delivery_proof = request.FILES['delivery_proof']
        elif not do.delivery_proof:
            messages.error(request, 'Please upload a delivery proof photo.')
            return render(request, 'orders/driver/mark_delivered.html', {'dispatch_order': do})
        do.save()
        do.order.status = 'delivered'
        do.order.delivered_at = timezone.now()
        do.order.save()
        trip = do.trip
        driver = trip.driver
        driver.is_available = True
        driver.save()
        if not trip.dispatch_orders.exclude(order__status__in=('delivered', 'cancelled')).exists():
            trip.completed_at = timezone.now()
            trip.save()
        AuditLog.objects.create(
            user=request.user, action='Delivered',
            model_name='DispatchOrder', object_id=do.pk,
            details=f"Order {do.order.po_number} delivered. Proof: {do.delivery_proof.name if do.delivery_proof else 'N/A'}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Order {do.order.po_number} delivered!')
        return redirect('orders:driver_trips')
    return render(request, 'orders/driver/mark_delivered.html', {'dispatch_order': do})


# ─── Superadmin Views ───────────────────────────────────────────────

@login_required
@superadmin_required
def superadmin_dashboard(request):
    stats = {
        'total_orders': Order.objects.count(),
        'draft': Order.objects.filter(status='draft').count(),
        'ready': Order.objects.filter(status='ready_for_dispatch').count(),
        'dispatched': Order.objects.filter(status='dispatched').count(),
        'delivered': Order.objects.filter(status='delivered').count(),
        'customers': User.objects.filter(role='customer').count(),
        'drivers': Driver.objects.count(),
        'tankers': Tanker.objects.filter(is_active=True).count(),
    }
    recent = Order.objects.select_related('customer', 'product')[:10]
    return render(request, 'orders/dashboard_superadmin.html', {'stats': stats, 'recent_orders': recent})


@login_required
@superadmin_required
def admin_customer_documents(request, user_id):
    customer = get_object_or_404(User, id=user_id, role='customer')
    docs = CustomerDocument.objects.filter(user=customer)
    return render(request, 'orders/admin/customer_documents.html', {'customer': customer, 'docs': docs})


@login_required
@superadmin_required
def admin_verify_document(request, pk):
    doc = get_object_or_404(CustomerDocument, pk=pk)
    doc.is_verified = not doc.is_verified
    doc.save()
    msg = 'verified' if doc.is_verified else 'unverified'
    messages.success(request, f'{doc.get_document_type_display()} {msg}.')
    return redirect('orders:admin_customer_documents', user_id=doc.user_id)


@login_required
@superadmin_required
def group_list(request):
    groups = CustomerGroup.objects.all()
    return render(request, 'orders/admin/groups.html', {'groups': groups})


@login_required
@superadmin_required
def group_create(request):
    if request.method == 'POST':
        CustomerGroup.objects.create(name=request.POST.get('name'), description=request.POST.get('description', ''))
        messages.success(request, 'Group created!')
        return redirect('orders:group_list')
    return render(request, 'orders/admin/group_form.html')


@login_required
@superadmin_required
def group_edit(request, pk):
    group = get_object_or_404(CustomerGroup, pk=pk)
    if request.method == 'POST':
        group.name = request.POST.get('name')
        group.description = request.POST.get('description', '')
        group.save()
        messages.success(request, 'Group updated!')
        return redirect('orders:group_list')
    return render(request, 'orders/admin/group_form.html', {'group': group})


@login_required
@superadmin_required
def group_delete(request, pk):
    group = get_object_or_404(CustomerGroup, pk=pk)
    group.delete()
    messages.success(request, 'Group deleted!')
    return redirect('orders:group_list')


@login_required
@superadmin_required
def pricing_list(request):
    pricings = ProductPricing.objects.select_related('product', 'customer_group', 'customer').order_by('product__shortcut')

    search = request.GET.get('search', '')
    product_filter = request.GET.get('product', '')
    target_filter = request.GET.get('target', '')
    status_filter = request.GET.get('status', '')

    if search:
        pricings = pricings.filter(
            models.Q(product__shortcut__icontains=search) |
            models.Q(product__name__icontains=search) |
            models.Q(customer__username__icontains=search) |
            models.Q(customer_group__name__icontains=search)
        )
    if product_filter:
        pricings = pricings.filter(product_id=product_filter)
    if target_filter == 'customer':
        pricings = pricings.filter(customer__isnull=False)
    elif target_filter == 'group':
        pricings = pricings.filter(customer_group__isnull=False, customer__isnull=True)
    elif target_filter == 'default':
        pricings = pricings.filter(customer_group__isnull=True, customer__isnull=True)
    if status_filter:
        pricings = pricings.filter(is_active=(status_filter == 'active'))

    products = Product.objects.filter(is_active=True).order_by('shortcut')
    return render(request, 'orders/admin/pricing_list.html', {
        'pricings': pricings,
        'products': products,
        'filters': request.GET,
    })


@login_required
@superadmin_required
def pricing_create(request):
    if request.method == 'POST':
        ProductPricing.objects.create(
            product_id=request.POST.get('product'),
            customer_group_id=request.POST.get('customer_group') or None,
            customer_id=request.POST.get('customer') or None,
            price_per_liter=request.POST.get('price_per_liter'),
        )
        messages.success(request, 'Pricing created!')
        return redirect('orders:pricing_list')
    products = Product.objects.filter(is_active=True)
    groups = CustomerGroup.objects.all()
    customers = User.objects.filter(role='customer')
    return render(request, 'orders/admin/pricing_form.html', {'products': products, 'groups': groups, 'customers': customers})


@login_required
@superadmin_required
def pricing_edit(request, pk):
    pricing = get_object_or_404(ProductPricing, pk=pk)
    if request.method == 'POST':
        pricing.product_id = request.POST.get('product')
        pricing.customer_group_id = request.POST.get('customer_group') or None
        pricing.customer_id = request.POST.get('customer') or None
        pricing.price_per_liter = request.POST.get('price_per_liter')
        pricing.is_active = request.POST.get('is_active') == 'on'
        pricing.save()
        messages.success(request, 'Pricing updated!')
        return redirect('orders:pricing_list')
    products = Product.objects.filter(is_active=True)
    groups = CustomerGroup.objects.all()
    customers = User.objects.filter(role='customer')
    return render(request, 'orders/admin/pricing_form.html', {'products': products, 'groups': groups, 'customers': customers, 'pricing': pricing})


@login_required
@superadmin_required
def pricing_delete(request, pk):
    pricing = get_object_or_404(ProductPricing, pk=pk)
    pricing.delete()
    messages.success(request, 'Pricing deleted!')
    return redirect('orders:pricing_list')


@login_required
@superadmin_required
def admin_orders(request):
    status_filter = request.GET.get('status', '')
    orders = Order.objects.select_related('customer', 'product').order_by('-created_at')
    if status_filter:
        orders = orders.filter(status=status_filter)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            orders = orders.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            orders = orders.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass
    return render(request, 'orders/admin/all_orders.html', {'orders': orders, 'current_status': status_filter, 'filters': request.GET})


@login_required
@superadmin_required
def product_list(request):
    products = Product.objects.all()
    return render(request, 'orders/admin/products.html', {'products': products})


@login_required
@superadmin_required
def product_create(request):
    if request.method == 'POST':
        Product.objects.create(
            shortcut=request.POST.get('shortcut'),
            name=request.POST.get('name'),
            description=request.POST.get('description', ''),
            order_multiple=request.POST.get('order_multiple', 500),
        )
        messages.success(request, 'Product created!')
        return redirect('orders:product_list')
    return render(request, 'orders/admin/product_form.html')


@login_required
@superadmin_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.shortcut = request.POST.get('shortcut')
        product.name = request.POST.get('name')
        product.description = request.POST.get('description', '')
        product.order_multiple = request.POST.get('order_multiple', 500)
        product.is_active = request.POST.get('is_active') == 'on'
        product.save()
        messages.success(request, 'Product updated!')
        return redirect('orders:product_list')
    return render(request, 'orders/admin/product_form.html', {'product': product})


@login_required
@superadmin_required
def audit_logs(request):
    qs = AuditLog.objects.select_related('user')

    action = request.GET.get('action')
    model_name = request.GET.get('model')
    user_id = request.GET.get('user')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if action:
        qs = qs.filter(action=action)
    if model_name:
        qs = qs.filter(model_name=model_name)
    if user_id:
        qs = qs.filter(user_id=user_id)
    if date_from:
        try:
            qs = qs.filter(created_at__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            qs = qs.filter(created_at__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass

    logs = qs.order_by('-created_at')[:200]

    actions = AuditLog.objects.values_list('action', flat=True).distinct().order_by('action')
    models = AuditLog.objects.values_list('model_name', flat=True).distinct().order_by('model_name')
    users = User.objects.filter(is_active=True).order_by('username')

    return render(request, 'orders/admin/audit_logs.html', {
        'logs': logs,
        'actions': actions,
        'models': models,
        'users': users,
        'filters': request.GET,
    })


@login_required
def sales_report(request):
    if request.user.role not in ('cashier', 'superadmin') and not request.user.is_superuser:
        return render(request, '403.html', status=403)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    search = request.GET.get('search', '').strip()
    product_id = request.GET.get('product', '').strip()
    status = request.GET.get('status', '').strip()

    orders = Order.objects.all()
    payments = Payment.objects.all()

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            orders = orders.filter(created_at__gte=df)
            payments = payments.filter(processed_at__gte=df)
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            orders = orders.filter(created_at__lte=dt)
            payments = payments.filter(processed_at__lte=dt)
        except (ValueError, TypeError):
            pass
    if search:
        orders = orders.filter(
            Q(po_number__icontains=search) | Q(customer__username__icontains=search) | Q(customer__business_name__icontains=search)
        )
    if product_id:
        orders = orders.filter(product_id=product_id)
    if status:
        orders = orders.filter(status=status)

    approved_payments = payments.filter(status='approved')
    total_revenue = approved_payments.aggregate(s=Sum('order__total_amount'))['s'] or 0

    pending_revenue = orders.filter(
        status='delivered'
    ).exclude(
        payments__status='approved'
    ).aggregate(s=Sum('total_amount'))['s'] or 0

    total_orders = orders.count()
    delivered_count = orders.filter(status='delivered').count()
    avg_order = orders.filter(total_amount__isnull=False).aggregate(a=Avg('total_amount'))['a'] or 0

    sales_by_product = (
        orders.filter(status='delivered')
        .values('product__shortcut')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')
    )

    sales_by_customer = (
        orders.filter(status='delivered')
        .values('customer__username', 'customer__business_name')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')[:10]
    )

    recent_payments = (
        approved_payments
        .select_related('order__customer', 'order__product')
        .order_by('-processed_at')[:20]
    )

    products = Product.objects.filter(is_active=True)

    return render(request, 'orders/admin/sales_report.html', {
        'total_revenue': total_revenue,
        'pending_revenue': pending_revenue,
        'total_orders': total_orders,
        'delivered_count': delivered_count,
        'avg_order': avg_order,
        'sales_by_product': sales_by_product,
        'sales_by_customer': sales_by_customer,
        'recent_payments': recent_payments,
        'products': products,
        'filters': request.GET,
    })


@login_required
def earned_revenue_dashboard(request):
    if request.user.role not in ('cashier', 'superadmin') and not request.user.is_superuser:
        return render(request, '403.html', status=403)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    delivered = Order.objects.filter(status='delivered').select_related('product', 'customer')
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            delivered = delivered.filter(delivered_at__gte=df)
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            delivered = delivered.filter(delivered_at__lte=dt)
        except (ValueError, TypeError):
            pass

    total_earned = delivered.aggregate(s=Sum('total_amount'))['s'] or 0
    order_count = delivered.count()

    by_product = (
        delivered.values('product__shortcut')
        .annotate(total=Sum('total_amount'), liters=Sum('quantity_liters'), count=Count('id'))
        .order_by('-total')
    )
    by_customer = (
        delivered.values('customer__username', 'customer__business_name')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')[:10]
    )
    recent = delivered.prefetch_related(
        'dispatch_orders__trip__tanker'
    ).order_by('-delivered_at')[:20]

    return render(request, 'orders/admin/earned_revenue.html', {
        'total_earned': total_earned,
        'order_count': order_count,
        'by_product': by_product,
        'by_customer': by_customer,
        'recent': recent,
        'filters': request.GET,
    })


@login_required
def unearned_revenue_dashboard(request):
    if request.user.role not in ('cashier', 'superadmin') and not request.user.is_superuser:
        return render(request, '403.html', status=403)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    unearned = Order.objects.filter(
        payments__status='approved'
    ).exclude(
        status__in=('delivered', 'cancelled')
    ).select_related('product', 'customer').distinct()
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d')
            unearned = unearned.filter(created_at__gte=df)
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            unearned = unearned.filter(created_at__lte=dt)
        except (ValueError, TypeError):
            pass

    total_unearned = unearned.aggregate(s=Sum('total_amount'))['s'] or 0
    order_count = unearned.count()

    by_product = (
        unearned.values('product__shortcut')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')
    )
    by_customer = (
        unearned.values('customer__username', 'customer__business_name')
        .annotate(total=Sum('total_amount'), count=Count('id'))
        .order_by('-total')[:10]
    )
    recent = unearned.order_by('-created_at')[:20]

    return render(request, 'orders/admin/unearned_revenue.html', {
        'total_unearned': total_unearned,
        'order_count': order_count,
        'by_product': by_product,
        'by_customer': by_customer,
        'recent': recent,
        'filters': request.GET,
    })


@login_required
@superadmin_required
def driver_list(request):
    drivers = Driver.objects.select_related('user').all()
    return render(request, 'orders/admin/drivers.html', {'drivers': drivers})


@login_required
@superadmin_required
def driver_create(request):
    if request.method == 'POST':
        user_id = request.POST.get('user')
        user = get_object_or_404(User, id=user_id, role='driver')
        expiry = request.POST.get('license_expiry') or None
        driver = Driver.objects.create(
            user=user,
            phone=request.POST.get('phone', ''),
            license_number=request.POST.get('license_number', ''),
            license_expiry=expiry,
        )
        AuditLog.objects.create(
            user=request.user, action='Created',
            model_name='Driver', object_id=driver.pk,
            details=f"Created driver profile for {user.username}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Driver {user.username} created!')
        return redirect('orders:driver_list')
    users = User.objects.filter(role='driver', driver_profile__isnull=True)
    return render(request, 'orders/admin/driver_form.html', {'users': users})


@login_required
@superadmin_required
def driver_edit(request, pk):
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == 'POST':
        old_data = f"phone={driver.phone}, lic={driver.license_number}, expiry={driver.license_expiry}, avail={driver.is_available}"
        driver.phone = request.POST.get('phone', '')
        driver.license_number = request.POST.get('license_number', '')
        driver.license_expiry = request.POST.get('license_expiry') or None
        driver.is_available = request.POST.get('is_available') == 'on'
        driver.save()
        AuditLog.objects.create(
            user=request.user, action='Updated',
            model_name='Driver', object_id=driver.pk,
            details=f"Updated driver {driver.user.username}: {old_data}",
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, 'Driver updated!')
        return redirect('orders:driver_list')
    return render(request, 'orders/admin/driver_form.html', {'driver': driver, 'users': []})


# ─── Chat / Operations Views ─────────────────────────────────────

@login_required
@hauling_required
def hauling_ops_chat(request):
    sort = request.GET.get('sort', 'recent')
    conversations = Conversation.objects.select_related('customer').all()
    if sort == 'unread':
        conversations = sorted(conversations, key=lambda c: c.unread_count, reverse=True)
    elif sort == 'alpha':
        conversations = sorted(conversations, key=lambda c: c.customer.username.lower())
    else:
        conversations = conversations.order_by('-updated_at')

    active_conversation = None
    messages_qs = []
    selected = request.GET.get('with') or request.POST.get('conversation_id')

    if request.method == 'POST' and request.POST.get('action') == 'send':
        content = request.POST.get('content', '').strip()
        if content:
            conv = get_object_or_404(Conversation, id=selected)
            Message.objects.create(
                conversation=conv, sender=request.user,
                content=content, is_system=False,
            )
            conv.updated_at = timezone.now()
            conv.save(update_fields=['updated_at'])
        return redirect(f'{request.path}?with={selected}')

    if selected:
        active_conversation = get_object_or_404(Conversation, id=selected)
        active_conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
        messages_qs = active_conversation.messages.select_related('sender').all()

    return render(request, 'orders/hauling/ops_chat.html', {
        'conversations': conversations,
        'active_conversation': active_conversation,
        'messages': messages_qs,
        'hide_messages': True,
    })


@login_required
def customer_messages(request):
    if request.user.role != 'customer':
        return render(request, '403.html', status=403)

    conv, _ = Conversation.objects.get_or_create(customer=request.user)

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        uploaded_file = request.FILES.get('payment_file')

        if uploaded_file:
            pending = Order.objects.filter(customer=request.user, status__in=('draft', 'ready_for_dispatch')).first()
            if pending:
                from .services.payment_service import upload_payment
                payment = upload_payment(pending, uploaded_file, request)
                link = request.build_absolute_uri(f'/order/{pending.pk}/')
                msg = (
                    f"📎 Payment uploaded for {pending.po_number}\n"
                    f"Status: {payment.get_status_display()}\n"
                    f"View details: {link}"
                )
                Message.objects.create(
                    conversation=conv, sender=request.user,
                    content=msg, is_system=True, related_order=pending,
                )
                conv.updated_at = timezone.now()
                conv.save(update_fields=['updated_at'])
            else:
                msg_text = content or "📎 Payment file uploaded (no active order found)"
                Message.objects.create(
                    conversation=conv, sender=request.user,
                    content=msg_text, is_system=False, file=uploaded_file,
                )
                conv.updated_at = timezone.now()
                conv.save(update_fields=['updated_at'])
        elif content:
            Message.objects.create(
                conversation=conv, sender=request.user,
                content=content, is_system=False,
            )
            conv.updated_at = timezone.now()
            conv.save(update_fields=['updated_at'])
        return redirect('orders:customer_messages')

    conv.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)
    msgs = conv.messages.select_related('sender').all()
    return render(request, 'orders/customer/messages.html', {
        'conversation': conv, 'messages': msgs, 'hide_messages': True,
    })


@login_required
@hauling_required
def hauling_preview_order(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    products = Product.objects.filter(is_active=True)
    chat_url = reverse('orders:hauling_ops_chat')

    if request.method == 'POST':
        product_id = request.POST.get('product')
        qty = request.POST.get('quantity')
        price = request.POST.get('price')
        po_override = request.POST.get('po_number', '').strip()
        notes = request.POST.get('notes', '')

        try:
            qty = int(qty)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid quantity')
            return redirect(f'{chat_url}?with={conversation_id}')

        product = get_object_or_404(Product, id=product_id)
        if qty <= 0 or qty % product.order_multiple != 0:
            messages.error(request, f'Must be multiple of {product.order_multiple}L')
            return redirect(f'{chat_url}?with={conversation_id}')

        from .services.order_service import create_order
        try:
            price_val = float(price) if price else None
        except (ValueError, TypeError):
            price_val = None

        order = create_order(conv.customer, product, qty, conv.customer.address or '', notes, request)
        if price_val:
            order.price_per_liter = price_val
            order.total_amount = price_val * qty
        if po_override:
            order.po_number = po_override
        order.save()

        total = order.total_amount or (order.price_per_liter * qty if order.price_per_liter else 0)
        msg = (
            f"✅ Created PO-{order.po_number} for {qty}L {product.shortcut}.\n"
            f"Price: ₱{order.price_per_liter:.2f}/L | Total: ₱{total:,.2f}\n"
            f"📎 Upload payment here → {request.build_absolute_uri('/order/' + str(order.pk) + '/')}"
        )
        Message.objects.create(conversation=conv, sender=request.user, content=msg, is_system=True, related_order=order)
        Message.objects.create(conversation=conv, sender=request.user,
            content=f"📦 Created PO-{order.po_number} for {conv.customer.username}: {qty}L {product.shortcut}",
            is_system=True, related_order=order)
        conv.updated_at = timezone.now()
        conv.save(update_fields=['updated_at'])
        messages.success(request, f'Order {order.po_number} created!')
        return redirect(f'{chat_url}?with={conversation_id}')

    default_price = None
    if conv.customer.customer_group_id:
        pricing = ProductPricing.objects.filter(
            customer_group_id=conv.customer.customer_group_id, is_active=True
        ).first()
        if pricing:
            default_price = pricing.price_per_liter
    return render(request, 'orders/hauling/preview_order.html', {
        'conv': conv, 'products': products, 'default_price': default_price,
    })


@login_required
@hauling_required
def hauling_preview_modify(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    orders = Order.objects.filter(customer=conv.customer).exclude(status__in=('delivered', 'cancelled'))
    chat_url = reverse('orders:hauling_ops_chat')

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        new_qty = request.POST.get('quantity')
        order = get_object_or_404(Order, id=order_id, customer=conv.customer)
        try:
            new_qty = int(new_qty)
        except (ValueError, TypeError):
            messages.error(request, 'Invalid quantity')
            return redirect(f'{chat_url}?with={conversation_id}')
        old_qty = order.quantity_liters
        order.quantity_liters = new_qty
        if order.price_per_liter:
            order.total_amount = order.price_per_liter * new_qty
        order.save()

        msg = f"📋 PO-{order.po_number} modified: {old_qty}L → {new_qty}L"
        Message.objects.create(conversation=conv, sender=request.user, content=msg, is_system=True, related_order=order)
        conv.updated_at = timezone.now()
        conv.save(update_fields=['updated_at'])
        messages.success(request, msg)
        return redirect(f'{chat_url}?with={conversation_id}')

    return render(request, 'orders/hauling/preview_modify.html', {
        'conv': conv, 'orders': orders,
    })


@login_required
@hauling_required
def hauling_preview_reschedule(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    orders = Order.objects.filter(customer=conv.customer).exclude(status__in=('delivered', 'cancelled'))
    chat_url = reverse('orders:hauling_ops_chat')

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        new_date = request.POST.get('new_date')
        order = get_object_or_404(Order, id=order_id, customer=conv.customer)
        from django.utils.dateparse import parse_date
        parsed = parse_date(new_date) if new_date else None
        if parsed:
            if order.status in ('dispatched', 'in_transit'):
                messages.warning(request, f'⚠️ {order.po_number} is already {order.status}. Rescheduling may affect trips.')
            order.notes = (order.notes + f'\nRescheduled to {new_date}').strip()
            order.save()
            msg = f"📅 PO-{order.po_number} rescheduled to {new_date}"
            Message.objects.create(conversation=conv, sender=request.user, content=msg, is_system=True, related_order=order)
            conv.updated_at = timezone.now()
            conv.save(update_fields=['updated_at'])
            messages.success(request, msg)
        else:
            messages.error(request, 'Invalid date')
        return redirect(f'{chat_url}?with={conversation_id}')

    return render(request, 'orders/hauling/preview_reschedule.html', {
        'conv': conv, 'orders': orders,
    })


@login_required
@hauling_required
def hauling_preview_custom(request, conversation_id):
    conv = get_object_or_404(Conversation, id=conversation_id)
    chat_url = reverse('orders:hauling_ops_chat')

    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            Message.objects.create(
                conversation=conv, sender=request.user,
                content=content, is_system=False,
            )
            conv.updated_at = timezone.now()
            conv.save(update_fields=['updated_at'])
        return redirect(f'{chat_url}?with={conversation_id}')

    return render(request, 'orders/hauling/preview_custom.html', {'conv': conv})
