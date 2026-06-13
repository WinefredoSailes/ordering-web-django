from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('cashier', 'Cashier'),
        ('hauling', 'Hauling/Dispatcher'),
        ('driver', 'Driver'),
        ('superadmin', 'Superadmin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    customer_group = models.ForeignKey(
        'orders.CustomerGroup',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='customers'
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    business_name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
