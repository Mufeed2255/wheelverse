from django.shortcuts import redirect


class SeparateAdminUserSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        admin_paths = [
            "/adminpanel/",
        ]

        user_allowed_admin_paths = [
            "/adminpanel/admin-login/",
            "/adminpanel/admin-logout/",
        ]

        if request.user.is_authenticated:
            is_admin = request.user.is_staff or request.user.is_superuser

            is_admin_url = any(path.startswith(p) for p in admin_paths)
            is_allowed_admin_url = any(path.startswith(p) for p in user_allowed_admin_paths)

            # Normal user trying admin panel
            if is_admin_url and not is_allowed_admin_url and not is_admin:
                return redirect("landing_page")

            # Admin trying user side
            if not is_admin_url and is_admin:
                return redirect("admin_dashboard")

        return self.get_response(request)