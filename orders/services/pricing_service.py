from ..models import ProductPricing


def get_best_price(customer, product):
    """Resolve price: customer-specific > group > None"""
    if not customer or not product:
        return None

    # 1. Customer-specific pricing
    cust_price = ProductPricing.objects.filter(
        customer=customer,
        product=product,
        is_active=True
    ).first()
    if cust_price:
        return cust_price.price_per_liter

    # 2. Group pricing
    if customer.customer_group:
        group_price = ProductPricing.objects.filter(
            customer_group=customer.customer_group,
            product=product,
            is_active=True
        ).first()
        if group_price:
            return group_price.price_per_liter

    return None
