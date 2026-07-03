from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout


class SeparateAdminUserSessionMiddleware:
    """
    Route guard only. It does NOT prevent dual-login by itself -- that is
    handled at login time (login_view / admin_login / adapter.py). This
    middleware's job is:
      1. Keep an admin session out of user-only areas and vice versa.
      2. Self-heal if login_type is ever missing/stale (defense in depth),
         instead of silently trusting request.user alone.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        ignore_paths = ["/static/", "/media/", "/favicon.ico"]
        if any(path.startswith(p) for p in ignore_paths):
            return self.get_response(request)

        if not request.user.is_authenticated:
            return self.get_response(request)

        admin_url = path.startswith("/adminpanel/")
        admin_login_url = path.startswith("/adminpanel/admin-login/")
        admin_logout_url = path.startswith("/adminpanel/admin-logout/")
        user_auth_url = (
            path.startswith("/login/")
            or path.startswith("/signup/")
            or path.startswith("/accounts/")
        )

        is_admin_account = request.user.is_staff or request.user.is_superuser
        login_type = request.session.get("login_type")

        # --- Self-heal: login_type missing or contradicts the account.
        # This is what silently let OAuth admins slip through before,
        # since Google logins never used to set login_type at all.
        if login_type is None:
            login_type = "admin" if is_admin_account else "user"
            request.session["login_type"] = login_type
        elif (login_type == "admin") != is_admin_account:
            # Session says one thing, account says another -- untrusted
            # state. Force logout rather than guess.
            logout(request)
            messages.error(request, "Session state was invalid. Please log in again.")
            return redirect("admin_login" if admin_url else "login")

        # --- Admin session trying to leave the admin area.
        if login_type == "admin" and not admin_url:
            return redirect("admin_dashboard")

        # --- User session trying to enter the admin area (except the
        # admin login page itself, which has its own guard, and logout).
        if login_type == "user" and admin_url and not admin_login_url and not admin_logout_url:
            messages.error(request, "You must log out before accessing the admin area.")
            return redirect("landing_page")

        # --- Admin account hitting user-side login/signup/oauth entry
        # points directly by URL (bypassing the buttons).
        if login_type == "admin" and user_auth_url:
            return redirect("admin_dashboard")

        return self.get_response(request)