from ..models import Order, AuditLog
from .pricing_service import get_best_price


def create_order(customer, product, quantity_liters, delivery_address, notes='', request=None):
    """Create an order with proper validation and pricing."""
    if quantity_liters <= 0 or quantity_liters % product.order_multiple != 0:
        raise ValueError(f"Quantity must be a multiple of {product.order_multiple}L for {product.shortcut}")

    price = get_best_price(customer, product)

    order = Order.objects.create(
        customer=customer,
        product=product,
        quantity_liters=quantity_liters,
        delivery_address=delivery_address,
        notes=notes,
        price_per_liter=price,
        status='draft',
    )

    _log('ORDER_CREATED', 'Order', order.pk,
         f"Created order {order.po_number}: {product.shortcut} {quantity_liters}L", request)
    return order


def _log(action, model_name, object_id, details, request):
    AuditLog.objects.create(
        user=request.user if request and hasattr(request, 'user') else None,
        action=action,
        model_name=model_name,
        object_id=object_id,
        details=details,
        ip_address=request.META.get('REMOTE_ADDR', '') if request else '',
    )
