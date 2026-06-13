from django.utils import timezone
from django.db import transaction
from ..models import DispatchTrip, DispatchOrder, Order, AuditLog
import random


def create_trip(tanker, driver, order_assignments, scheduled_date=None, notes='', created_by=None, request=None):
    """
    Create a dispatch trip with multiple order-compartment assignments.

    order_assignments: list of dicts [{'order': order_obj, 'compartment': compartment_obj}, ...]

    Returns: (trip, errors)
    errors: list of warning strings (non-blocking)
    Raises ValueError on hard validation errors.
    """
    warnings = []
    total_liters = sum(a['order'].quantity_liters for a in order_assignments)

    # Validate total capacity
    if total_liters > tanker.total_capacity:
        raise ValueError(
            f"Total orders ({total_liters}L) exceeds tanker capacity ({tanker.total_capacity}L) by {total_liters - tanker.total_capacity}L"
        )

    # Validate individual compartment fit and cumulative usage
    comp_usage = {}
    hard_errors = []
    for assignment in order_assignments:
        comp = assignment['compartment']
        order = assignment['order']
        if comp.capacity < order.quantity_liters:
            hard_errors.append(
                f"Compartment C{comp.number} ({comp.capacity}L) is too small for {order.short_notation()} ({order.quantity_liters}L)"
            )
        used = comp_usage.get(comp.id, 0) + order.quantity_liters
        if used > comp.capacity:
            hard_errors.append(
                f"Compartment C{comp.number} ({comp.capacity}L) over capacity: {used}L assigned "
                f"({comp_usage.get(comp.id, 0)}L + {order.quantity_liters}L from {order.short_notation()})"
            )
        comp_usage[comp.id] = used

    if hard_errors:
        raise ValueError('; '.join(hard_errors))

    # Underload warning
    utilization = total_liters / tanker.total_capacity * 100
    if utilization < 50:
        warnings.append(f"Tanker at {utilization:.0f}% utilization ({total_liters}L / {tanker.total_capacity}L)")

    with transaction.atomic():
        trip = DispatchTrip.objects.create(
            trip_number=f"TRIP-{timezone.now().strftime('%Y%m%d')}-{random.randint(100, 999)}",
            tanker=tanker,
            driver=driver,
            total_loaded_liters=total_liters,
            scheduled_date=scheduled_date or timezone.now(),
            dispatched_at=timezone.now(),
            notes=notes,
            created_by=created_by,
        )

        for assignment in order_assignments:
            order = assignment['order']
            compartment = assignment['compartment']
            DispatchOrder.objects.create(
                trip=trip,
                order=order,
                compartment=compartment,
                liters_loaded=order.quantity_liters,
            )
            order.status = 'dispatched'
            order.dispatched_at = timezone.now()
            order.save()

    driver.is_available = False
    driver.save()

    _log('TRIP_CREATED', 'DispatchTrip', trip.pk,
         f"Trip {trip.trip_number}: {len(order_assignments)} orders, {total_liters}L on {tanker.code}",
         request)

    return trip, warnings


def complete_trip(trip, request=None):
    """Mark all orders in a trip as delivered."""
    with transaction.atomic():
        for do in trip.dispatch_orders.filter(delivered_at__isnull=True):
            do.delivered_at = timezone.now()
            do.save()
            do.order.status = 'delivered'
            do.order.delivered_at = timezone.now()
            do.order.save()

        trip.completed_at = timezone.now()
        trip.save()

        trip.driver.is_available = True
        trip.driver.save()

    _log('TRIP_COMPLETED', 'DispatchTrip', trip.pk,
         f"Trip {trip.trip_number} completed", request)


def _log(action, model_name, object_id, details, request):
    from ..models import AuditLog
    AuditLog.objects.create(
        user=request.user if request and hasattr(request, 'user') else None,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details,
        ip_address=request.META.get('REMOTE_ADDR', '') if request else '',
    )
