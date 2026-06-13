from django.utils import timezone
from django.db.models import Max
from ..models import Payment, Order, AuditLog


def upload_payment(order, file, request=None):
    """Upload a new payment proof for an order."""
    payment = Payment.objects.create(
        order=order,
        file=file,
        status='uploaded',
    )
    _log('PAYMENT_UPLOADED', 'Payment', payment.pk,
         f"Payment uploaded for {order.po_number}", request)
    return payment


def approve_payment(payment, approver, request=None):
    """Approve a payment - enables the order for dispatch."""
    payment.status = 'approved'
    payment.approved_by = approver
    payment.processed_at = timezone.now()

    if not payment.acknowledgement_receipt:
        today = timezone.now().strftime('%Y%m%d')
        last = Payment.objects.filter(
            acknowledgement_receipt__startswith=f'AR-{today}-'
        ).aggregate(Max('acknowledgement_receipt'))
        last_num = last['acknowledgement_receipt__max']
        seq = (int(last_num.split('-')[-1]) + 1) if last_num else 1
        payment.acknowledgement_receipt = f'AR-{today}-{seq:05d}'

    payment.save()

    order = payment.order
    order.status = 'ready_for_dispatch'
    order.save()

    _log('PAYMENT_APPROVED', 'Payment', payment.pk,
         f"Payment approved by {approver.username} for {order.po_number}", request)


def reject_payment(payment, reason, request=None):
    """Reject a payment - customer can re-upload."""
    payment.status = 'rejected'
    payment.rejection_reason = reason
    payment.processed_at = timezone.now()
    payment.save()

    _log('PAYMENT_REJECTED', 'Payment', payment.pk,
         f"Payment rejected: {reason[:100]}", request)


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
