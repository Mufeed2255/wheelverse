from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages

User = get_user_model()


def admin_login(request):

    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect("admin_dashboard")
        logout(request)
        return redirect("admin_login")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            messages.error(request, "Username and Password are required.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        if not user.is_active:
            messages.error(request, "This account has been deactivated.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        if not (user.is_staff or user.is_superuser):
            messages.error(request, "Access denied. Admin login only.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        login(request, user)
        messages.success(request, "Welcome to the Admin Dashboard.")
        return redirect("admin_dashboard")

    return render(request, "adminpanel/admin_login/admin_login.html")


@login_required(login_url="admin_login")
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser):
        logout(request)
        messages.error(request, "You are not authorized to access the admin panel.")
        return redirect("admin_login")

    customers = User.objects.filter(
        is_staff=False,
        is_superuser=False
    )

    context = {
        "total_users": customers.count(),
        "active_users": customers.filter(is_active=True).count(),
        "inactive_users": customers.filter(is_active=False).count(),
        "recent_signups": customers.order_by("-date_joined")[:5],
    }

    return render(
        request,
        "adminpanel/admin_login/admin_dashboard.html",
        context,
    )


@login_required(login_url="admin_login")
def admin_logout_view(request):
    logout(request)
    messages.success(request, "Admin logged out successfully.")
    return redirect("admin_login")