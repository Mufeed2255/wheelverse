import random
import re

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives
from django.http import JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string

from decimal import Decimal
from django.db.models import F

from Wallet.models import Wallet, WalletTransaction

# this is shere to Accounts / Orders / Products)
def is_ajax_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def generate_otp():
    return str(random.randint(100000, 999999))


def normalize_indian_phone(phone):
    phone = re.sub(r"[\s-]", "", phone or "")
    if phone.startswith("+91"):
        phone = phone[3:]
    elif phone.startswith("91") and len(phone) == 12:
        phone = phone[2:]
    return phone


# Email
def send_wheelverse_otp_email(to_email, username, otp, purpose, expiry=5):
    html_content = render_to_string(
        "emails/otp_email.html",
        {
            "username": username,
            "otp": otp,
            "purpose": purpose,
            "expiry": expiry,
        },
    )

    text_content = f"""
Hello {username},

We received a request for {purpose}.

Your verification code is:

{otp}

This OTP will expire in {expiry} minutes.

Do not share this code with anyone.

If you did not request this action, ignore this email.

WheelVerse Team
Enter the Universe of Wheels
"""

    email = EmailMultiAlternatives(
        subject=f"WheelVerse | {purpose.title()} Verification",
        body=text_content,
        from_email=settings.EMAIL_HOST_USER,
        to=[to_email],
    )
    email.attach_alternative(html_content, "text/html")
    email.send()


# Signup helpers
def signup_error_response(request, field, message, referral_code="", status=400):

    if is_ajax_request(request):
        return JsonResponse(
            {"success": False, "field": field, "message": message},
            status=status,
        )

    messages.error(request, message)
    return render(
        request,
        "accounts/signup.html",
        {"referral_code": referral_code, "posted_data": request.POST},
        status=status,
    )


def credit_referral_reward(new_user):
    if not new_user.referred_by:
        return False

    referrer = new_user.referred_by
    reward_amount = Decimal("50.00")
    reference = f"REFERRAL_REWARD_{new_user.id}"

    if WalletTransaction.objects.filter(reference=reference).exists():
        return False

    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=referrer)
    wallet.balance += reward_amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        transaction_type="CREDIT",
        purpose="REFERRAL_REWARD",
        payment_method="WALLET",
        amount=reward_amount,
        status="COMPLETED",
        description=f"Referral reward for inviting {new_user.username}",
        reference=reference,
    )
    return True


from .models import Address 

ALLOWED_ADDRESS_TYPES = {
    Address.AddressType.HOME,
    Address.AddressType.GARAGE,
    Address.AddressType.WORK,
    Address.AddressType.OTHER,
}

NAME_RE = r"[A-Za-z][A-Za-z\s.'-]*"
LINE_RE = r"[A-Za-z0-9\s,./#()&'-]+"


def validate_address_data(data, *, allow_garage=True):

    cleaned_data = {
        "name": data.get("name", "").strip(),
        "phone_number": data.get("phone_number", "").strip(),
        "address_line_1": data.get("address_line_1", "").strip(),
        "address_line_2": data.get("address_line_2", "").strip(),
        "city": data.get("city", "").strip(),
        "state": data.get("state", "").strip(),
        "pincode": data.get("pincode", "").strip(),
        "country": "INDIA",
        "address_type": data.get("address_type", Address.AddressType.HOME).strip().upper(),
        "is_default": data.get("is_default") == "on",
    }

    name = cleaned_data["name"]
    phone_number = cleaned_data["phone_number"]
    address_line_1 = cleaned_data["address_line_1"]
    address_line_2 = cleaned_data["address_line_2"]
    city = cleaned_data["city"]
    state = cleaned_data["state"]
    pincode = cleaned_data["pincode"]
    address_type = cleaned_data["address_type"]

    def fail(field, message):
        return False, cleaned_data, field, message

    # Full name
    if not name:
        return fail("name", "Full name is required.")
    if len(name) < 2 or len(name) > 60:
        return fail("name", "Full name must be between 2 and 60 characters.")
    if not re.fullmatch(NAME_RE, name):
        return fail("name", "Full name can contain only letters, spaces, dots, apostrophes and hyphens.")
    if "  " in name:
        return fail("name", "Full name cannot contain multiple consecutive spaces.")

    # Phone
    if not phone_number:
        return fail("phone_number", "Phone number is required.")
    normalized_phone = normalize_indian_phone(phone_number)
    if not normalized_phone.isdigit():
        return fail("phone_number", "Phone number must contain only digits.")
    if not re.fullmatch(r"[6-9]\d{9}", normalized_phone):
        return fail("phone_number", "Enter a valid 10-digit Indian mobile number starting with 6, 7, 8 or 9.")
    if len(set(normalized_phone)) == 1:
        return fail("phone_number", "Enter a valid phone number.")
    cleaned_data["phone_number"] = normalized_phone

    # Address line 1
    if not address_line_1:
        return fail("address_line_1", "Address Line 1 is required.")
    if len(address_line_1) < 5 or len(address_line_1) > 150:
        return fail("address_line_1", "Address Line 1 must be between 5 and 150 characters.")
    if not re.search(r"[A-Za-z]", address_line_1):
        return fail("address_line_1", "Address Line 1 must contain letters.")
    if not re.fullmatch(LINE_RE, address_line_1):
        return fail("address_line_1", "Address Line 1 contains invalid characters.")

    # Address line 2
    if address_line_2:
        if len(address_line_2) > 150:
            return fail("address_line_2", "Address Line 2 cannot exceed 150 characters.")
        if not re.fullmatch(LINE_RE, address_line_2):
            return fail("address_line_2", "Address Line 2 contains invalid characters.")

    # City
    if not city:
        return fail("city", "City is required.")
    if len(city) < 2 or len(city) > 50:
        return fail("city", "City must be between 2 and 50 characters.")
    if not re.fullmatch(NAME_RE, city):
        return fail("city", "City can contain only letters, spaces, dots, apostrophes and hyphens.")
    if "  " in city:
        return fail("city", "City cannot contain multiple consecutive spaces.")

    # State
    if not state:
        return fail("state", "State is required.")
    if len(state) < 2 or len(state) > 50:
        return fail("state", "State must be between 2 and 50 characters.")
    if not re.fullmatch(NAME_RE, state):
        return fail("state", "State can contain only letters, spaces, dots, apostrophes and hyphens.")
    if "  " in state:
        return fail("state", "State cannot contain multiple consecutive spaces.")

    # Pincode
    if not pincode:
        return fail("pincode", "Pincode is required.")
    if not pincode.isdigit():
        return fail("pincode", "Pincode must contain only digits.")
    if not re.fullmatch(r"[1-9]\d{5}", pincode):
        return fail("pincode", "Enter a valid 6-digit Indian pincode.")

    # Address type
    allowed_types = ALLOWED_ADDRESS_TYPES if allow_garage else {
        Address.AddressType.HOME,
        Address.AddressType.WORK,
        Address.AddressType.OTHER,
    }
    if address_type not in allowed_types:
        return fail("address_type", "Select a valid address type.")

    return True, cleaned_data, None, None