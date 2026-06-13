from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from orders.models import CustomerGroup, Driver

User = get_user_model()


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('orders:home')
        messages.error(request, 'Invalid username or password.')
    return render(request, 'accounts/login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        phone = request.POST.get('phone', '')
        address = request.POST.get('address', '')

        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'accounts/register.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'accounts/register.html')

        user = User.objects.create_user(username=username, email=email, password=password1, phone=phone, address=address, business_name=request.POST.get('business_name', ''))
        user.role = 'customer'
        user.save()
        login(request, user)
        messages.success(request, 'Account created! Welcome!')
        return redirect('orders:home')

    return render(request, 'accounts/register.html')


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        request.user.phone = request.POST.get('phone', '')
        request.user.address = request.POST.get('address', '')
        request.user.business_name = request.POST.get('business_name', '')
        request.user.save()

        if request.user.role == 'driver':
            driver = getattr(request.user, 'driver_profile', None)
            if driver:
                driver.phone = request.POST.get('phone', '')
                driver.license_number = request.POST.get('license_number', '')
                driver.license_expiry = request.POST.get('license_expiry') or None
                driver.save()

        messages.success(request, 'Profile updated!')
        return redirect('accounts:profile')

    driver = None
    if request.user.role == 'driver':
        driver = getattr(request.user, 'driver_profile', None)

    return render(request, 'accounts/profile.html', {'driver_profile': driver})


@login_required
def user_list(request):
    if not (request.user.role == 'superadmin' or request.user.is_superuser):
        return render(request, '403.html', status=403)

    role_filter = request.GET.get('role', '')
    group_filter = request.GET.get('group', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    users = User.objects.all().order_by('-date_joined')
    if role_filter:
        users = users.filter(role=role_filter)
    if group_filter:
        users = users.filter(customer_group_id=group_filter)
    if date_from:
        try:
            users = users.filter(date_joined__gte=datetime.strptime(date_from, '%Y-%m-%d'))
        except (ValueError, TypeError):
            pass
    if date_to:
        try:
            users = users.filter(date_joined__lte=datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59))
        except (ValueError, TypeError):
            pass

    groups = CustomerGroup.objects.all()
    return render(request, 'accounts/user_list.html', {
        'users': users,
        'groups': groups,
        'filters': request.GET,
    })


@login_required
def user_create(request):
    if not (request.user.role == 'superadmin' or request.user.is_superuser):
        return render(request, '403.html', status=403)

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        role = request.POST.get('role')

        user = User.objects.create_user(username=username, password=password, role=role)
        group_id = request.POST.get('customer_group')
        if group_id:
            user.customer_group_id = group_id
        user.phone = request.POST.get('phone', '')
        user.address = request.POST.get('address', '')
        user.business_name = request.POST.get('business_name', '')
        user.save()
        messages.success(request, f'User {username} created!')
        return redirect('accounts:user_list')

    groups = CustomerGroup.objects.all()
    return render(request, 'accounts/user_form.html', {'groups': groups})


@login_required
def user_edit(request, pk):
    if not (request.user.role == 'superadmin' or request.user.is_superuser):
        return render(request, '403.html', status=403)

    user = get_object_or_404(User, pk=pk)

    if request.method == 'POST':
        user.username = request.POST.get('username')
        user.role = request.POST.get('role')
        user.phone = request.POST.get('phone', '')
        user.address = request.POST.get('address', '')
        user.business_name = request.POST.get('business_name', '')
        group_id = request.POST.get('customer_group')
        user.customer_group_id = group_id if group_id else None

        password = request.POST.get('password')
        if password:
            user.set_password(password)

        user.save()
        messages.success(request, 'User updated!')
        return redirect('accounts:user_list')

    groups = CustomerGroup.objects.all()
    return render(request, 'accounts/user_form.html', {'edit_user': user, 'groups': groups})


@login_required
def user_delete(request, pk):
    if not (request.user.role == 'superadmin' or request.user.is_superuser):
        return render(request, '403.html', status=403)

    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted!')
        return redirect('accounts:user_list')
    return render(request, 'accounts/user_confirm_delete.html', {'delete_user': user})
