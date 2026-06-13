from functools import wraps
from django.shortcuts import render


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.shortcuts import redirect
                return redirect('accounts:login')
            if request.user.role not in roles and not request.user.is_superuser:
                return render(request, '403.html', status=403)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def cashier_required(view_func):
    return role_required('cashier', 'superadmin')(view_func)


def hauling_required(view_func):
    return role_required('hauling', 'superadmin')(view_func)


def superadmin_required(view_func):
    return role_required('superadmin')(view_func)


def customer_required(view_func):
    return role_required('customer')(view_func)
