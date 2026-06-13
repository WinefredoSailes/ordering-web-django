from django.urls import path, include
from . import views

app_name = 'orders'

urlpatterns = [
    path('', views.home, name='home'),

    # ── Customer ──
    path('products/', views.products, name='products'),
    path('order/create/', views.create_order_view, name='create_order'),
    path('order/<int:pk>/', views.order_detail, name='order_detail'),
    path('order/<int:pk>/upload-payment/', views.upload_payment_view, name='upload_payment'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('dashboard/customer/', views.customer_dashboard, name='customer_dashboard'),
    path('documents/', views.customer_documents, name='customer_documents'),
    path('documents/<int:pk>/delete/', views.customer_document_delete, name='customer_document_delete'),

    # ── Cashier ──
    path('cashier/dashboard/', views.cashier_dashboard, name='cashier_dashboard'),
    path('cashier/payments/', views.cashier_payments, name='cashier_payments'),
    path('cashier/payment/<int:pk>/verify/', views.verify_payment_view, name='verify_payment'),

    # ── Hauling ──
    path('hauling/dashboard/', views.hauling_dashboard, name='hauling_dashboard'),
    path('hauling/orders/', views.hauling_orders, name='hauling_orders'),
    path('hauling/trips/create/', views.create_trip_view, name='create_trip'),
    path('hauling/trips/', views.hauling_trips, name='hauling_trips'),
    path('hauling/trip/<int:pk>/', views.trip_detail, name='trip_detail'),
    path('hauling/tankers/', views.tanker_list, name='tanker_list'),
    path('hauling/tanker/create/', views.tanker_create, name='tanker_create'),
    path('hauling/tanker/<int:pk>/', views.tanker_detail, name='tanker_detail'),
    path('hauling/tanker/<int:pk>/edit/', views.tanker_edit, name='tanker_edit'),
    path('hauling/tanker/<int:pk>/delete/', views.tanker_delete, name='tanker_delete'),
    path('hauling/tanker/<int:pk>/compartment/add/', views.compartment_add, name='compartment_add'),
    path('hauling/tanker/<int:pk>/compartment/<int:comp_id>/delete/', views.compartment_delete, name='compartment_delete'),

    # ── Driver ──
    path('driver/dashboard/', views.driver_dashboard, name='driver_dashboard'),
    path('driver/trips/', views.driver_trips, name='driver_trips'),
    path('driver/order/<int:pk>/in-transit/', views.mark_in_transit, name='mark_in_transit'),
    path('driver/order/<int:pk>/deliver/', views.mark_delivered, name='mark_delivered'),

    # ── Superadmin ──
    path('admin/dashboard/', views.superadmin_dashboard, name='superadmin_dashboard'),
    path('admin/orders/', views.admin_orders, name='admin_orders'),
    path('admin/groups/', views.group_list, name='group_list'),
    path('admin/group/create/', views.group_create, name='group_create'),
    path('admin/group/<int:pk>/edit/', views.group_edit, name='group_edit'),
    path('admin/group/<int:pk>/delete/', views.group_delete, name='group_delete'),
    path('admin/pricing/', views.pricing_list, name='pricing_list'),
    path('admin/pricing/create/', views.pricing_create, name='pricing_create'),
    path('admin/pricing/<int:pk>/edit/', views.pricing_edit, name='pricing_edit'),
    path('admin/pricing/<int:pk>/delete/', views.pricing_delete, name='pricing_delete'),
    path('admin/products/', views.product_list, name='product_list'),
    path('admin/product/create/', views.product_create, name='product_create'),
    path('admin/product/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('admin/drivers/', views.driver_list, name='driver_list'),
    path('admin/driver/create/', views.driver_create, name='driver_create'),
    path('admin/driver/<int:pk>/edit/', views.driver_edit, name='driver_edit'),
    path('admin/customer/<int:user_id>/documents/', views.admin_customer_documents, name='admin_customer_documents'),
    path('admin/document/<int:pk>/verify/', views.admin_verify_document, name='admin_verify_document'),
    path('admin/audit-logs/', views.audit_logs, name='audit_logs'),
    path('admin/sales-report/', views.sales_report, name='sales_report'),
    path('admin/earned-revenue/', views.earned_revenue_dashboard, name='earned_revenue'),
    path('admin/unearned-revenue/', views.unearned_revenue_dashboard, name='unearned_revenue'),

    # ── Dashboard fallback ──
    path('dashboard/', views.home, name='dashboard'),
]
