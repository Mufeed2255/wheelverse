"""
Accounts/adapter.py

Enforces flow separation for Google OAuth login.

WHY THIS FILE, NOT MIDDLEWARE:
Middleware only runs for requests that hit your own URLconf. The allauth
OAuth dance (redirect to Google -> Google redirects back to allauth's own
callback view -> allauth calls django.contrib.auth.login() internally)
completes and logs the user in *before* your middleware gets a chance to
inspect anything meaningful on a subsequent request. By the time your
middleware sees the next request, the wrong account is already logged in.

pre_social_login() is an allauth hook that fires BEFORE the login is
finalized, so it's the only place that can reject a mismatched account
before a session is ever created for it.
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.contrib import messages
from django.shortcuts import redirect


class WheelVerseSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Called after Google auth succeeds, before the session is created.

        request.session['oauth_flow'] tells us which login page the user
        started from ('user' or 'admin'). It's set by the two trigger
        views (google_login_user / google_login_admin), right before
        redirecting to Google.
        """
        intended_flow = request.session.get('oauth_flow', 'user')

        user = sociallogin.user
        is_admin_account = bool(getattr(user, 'is_staff', False) or
                                 getattr(user, 'is_superuser', False))

        # Case 1: admin account used on the USER google button -> block.
        if intended_flow == 'user' and is_admin_account:
            messages.error(
                request,
                "This Google account belongs to an admin. "
                "Please use the admin login page."
            )
            raise ImmediateHttpResponse(redirect('login'))

        # Case 2: non-admin account used on the ADMIN google button -> block.
        if intended_flow == 'admin' and not is_admin_account:
            messages.error(
                request,
                "This Google account is not authorized for admin access."
            )
            raise ImmediateHttpResponse(redirect('admin_login'))

        # Case 3: an existing session already carries a DIFFERENT login
        # type. Defense in depth in case someone reuses a tab mid-OAuth.
        current_login_type = request.session.get('login_type')
        if current_login_type and current_login_type != intended_flow:
            messages.error(
                request,
                "You already have an active session of a different type. "
                "Please log out first."
            )
            fallback = 'admin_dashboard' if current_login_type == 'admin' else 'landing_page'
            raise ImmediateHttpResponse(redirect(fallback))


class WheelVerseAccountAdapter(DefaultAccountAdapter):
    """
    Stamps request.session['login_type'] the moment ANY allauth login
    completes (Google or allauth's own account login), so downstream
    middleware always has a reliable flag to check -- closing the gap
    that caused Bug 1 (Google logins never set login_type before).
    """

    def login(self, request, user):
        super().login(request, user)
        is_admin_account = bool(getattr(user, 'is_staff', False) or
                                 getattr(user, 'is_superuser', False))
        request.session['login_type'] = 'admin' if is_admin_account else 'user'