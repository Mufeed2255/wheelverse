from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required

User = get_user_model()


def admin_login(request):
   
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        return redirect('admin_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()

        if not username or not password:
            messages.error(request, 'Both username and password fields are required.')
            return render(request, 'adminpanel/admin_login/admin_login.html')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, 'This admin account has been deactivated.')
                return render(request, 'adminpanel/admin_login/admin_login.html')

            if user.is_staff or user.is_superuser:
                login(request, user)
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Access Denied. You do not have administrative privileges.')
        else:
            messages.error(request, 'Invalid username or password. Please try again.')

    return render(request, 'adminpanel/admin_login/admin_login.html')


@login_required(login_url='admin_login')
def admin_dashboard(request):
   
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'Access Denied. You do not have administrative privileges.')
        logout(request)
        return redirect('admin_login')

    customer_qs = User.objects.filter(is_staff=False, is_superuser=False)

    total_users = customer_qs.count()
    active_users = customer_qs.filter(is_active=True).count()
    inactive_users = customer_qs.filter(is_active=False).count()

    
    recent_signups = customer_qs.order_by('-date_joined')[:5]

    context = {
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': inactive_users,
        'recent_signups': recent_signups,
    }

    return render(request, 'adminpanel/admin_login/admin_dashboard.html', context)


def admin_logout_view(request):
    logout(request)
    messages.success(request, "You have been successfully logged out of the Control Center.")
    return redirect('admin_login')