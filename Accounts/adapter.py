# Accounts/adapter.py
# Custom allauth adapter to handle Google OAuth with WheelVerse's CustomUser model.
# Primary job: auto-generate a unique username from Google profile data,
# since Google doesn't supply a username but Django's AbstractUser requires one.

import re
import random
import string

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model


User = get_user_model()


class WheelVerseSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for WheelVerse.
    Ensures every Google-authenticated user gets a valid, unique username
    auto-generated from their Google email or display name.
    """

    def populate_user(self, request, sociallogin, data):
        """
        Called by allauth to fill in user fields from the social provider's data.
        We call super() first (fills email, first_name, last_name, etc.),
        then guarantee a unique username is present.
        """
        user = super().populate_user(request, sociallogin, data)

        # Only auto-generate if username is missing or empty
        if not getattr(user, 'username', None):
            email = data.get('email', '') or ''
            name  = data.get('name', '')  or ''

            # Priority: use email prefix, then full name, then fallback
            if email:
                base = re.sub(r'[^a-zA-Z0-9]', '', email.split('@')[0])
            elif name:
                base = re.sub(r'[^a-zA-Z0-9]', '', name.replace(' ', ''))
            else:
                base = 'collector'

            # Enforce minimum length of 5 characters
            if len(base) < 5:
                base = base + ''.join(random.choices(string.digits, k=5 - len(base)))

            # Cap at 15 characters (leaves room for uniqueness suffix)
            base = base[:15].lower()

            # Guarantee uniqueness by appending a counter if needed
            username = base
            counter  = 1
            while User.objects.filter(username=username).exists():
                suffix   = str(counter)
                username = base[:15 - len(suffix)] + suffix
                counter += 1

            user.username = username

        return user

    def is_auto_signup_allowed(self, request, sociallogin):
        """Allow automatic signup without showing an intermediate form."""
        return True

    def get_connect_redirect_url(self, request, socialaccount):
        """After connecting a social account, redirect to the profile page."""
        return '/profile/'
