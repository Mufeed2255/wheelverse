import re
from datetime import datetime
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.shortcuts import redirect, render
import random
import time
User = get_user_model()
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .models import Address
from django.shortcuts import render, get_object_or_404
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from decimal import Decimal
from django.db import transaction
from Wallet.models import Wallet, WalletTransaction
from django.db.models import Count, Min, Max, Prefetch, Q
from adminpanel.models import Category, Product, ProductVariant
from Products.models import Cart, Wishlist


def send_wheelverse_otp_email(to_email, username, otp, purpose, expiry=5):

    html_content = render_to_string(
        "emails/otp_email.html",
        {
            "username": username,
            "otp": otp,
            "purpose": purpose,
            "expiry": expiry,
        }
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

    email.attach_alternative(
        html_content,
        "text/html"
    )

    email.send()




def landing_page(request):
    active_variants = (
        ProductVariant.objects
        .filter(is_active=True, is_deleted=False)
        .prefetch_related("images")
        .order_by("id")
    )

    base_products = (
        Product.objects
        .filter(
            is_active=True,
            is_deleted=False,
            category__is_active=True,
        )
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=active_variants,
                to_attr="active_variants",
            )
        )
        .annotate(
            min_price=Min(
                "variants__price",
                filter=Q(
                    variants__is_active=True,
                    variants__is_deleted=False,
                ),
            ),
            max_price=Max(
                "variants__price",
                filter=Q(
                    variants__is_active=True,
                    variants__is_deleted=False,
                ),
            ),
        )
        .filter(min_price__isnull=False)
    )

    latest_products = list(
        base_products.order_by("-created_at", "-id")[:8]
    )

    expensive_products = list(
        base_products.order_by("-max_price", "-created_at")[:6]
    )

    categories = list(
        Category.objects
        .filter(
            is_active=True,
            products__is_active=True,
            products__is_deleted=False,
        )
        .annotate(
            product_count=Count(
                "products",
                filter=Q(
                    products__is_active=True,
                    products__is_deleted=False,
                ),
                distinct=True,
            )
        )
        .prefetch_related(
            Prefetch(
                "products",
                queryset=base_products.order_by("-created_at"),
                to_attr="landing_products",
            )
        )
        .distinct()
        .order_by("name")[:8]
    )

    all_products = latest_products + expensive_products

    for product in all_products:
        product.first_active_variant = (
            product.active_variants[0]
            if product.active_variants
            else None
        )
        product.landing_image_url = ""

        if product.first_active_variant:
            first_image = product.first_active_variant.images.first()

            if first_image and first_image.image:
                product.landing_image_url = first_image.image.url
            elif product.first_active_variant.image:
                product.landing_image_url = (
                    product.first_active_variant.image.url
                )

    for category in categories:
        category.landing_image_url = ""
        category.featured_product = None

        for product in getattr(category, "landing_products", []):
            variants = getattr(product, "active_variants", [])

            if not variants:
                continue

            category.featured_product = product
            first_variant = variants[0]
            first_image = first_variant.images.first()

            if first_image and first_image.image:
                category.landing_image_url = first_image.image.url
            elif first_variant.image:
                category.landing_image_url = first_variant.image.url

            if category.landing_image_url:
                break

    hero_product = (
        expensive_products[0]
        if expensive_products
        else (latest_products[0] if latest_products else None)
    )

    cart_count = 0
    wishlist_count = 0

    if request.user.is_authenticated:
        cart_count = Cart.objects.filter(
            user=request.user,
            variant__is_active=True,
            variant__is_deleted=False,
        ).count()

        wishlist_count = Wishlist.objects.filter(
            user=request.user,
            variant__is_active=True,
            variant__is_deleted=False,
        ).count()

    return render(
        request,
        "accounts/landing_page.html",
        {
            "hero_product": hero_product,
            "categories": categories,
            "latest_products": latest_products,
            "expensive_products": expensive_products,
            "cart_count": cart_count,
            "wishlist_count": wishlist_count,
        },
    )

def credit_referral_reward(new_user):
    if not new_user.referred_by:
        return False

    referrer = new_user.referred_by
    reward_amount = Decimal("50.00")
    reference = f"REFERRAL_REWARD_{new_user.id}"

    if WalletTransaction.objects.filter(reference=reference).exists():
        return False

    wallet, created = Wallet.objects.select_for_update().get_or_create(
        user=referrer
    )

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

def signup_view(request):
    if request.user.is_authenticated:
        return redirect("landing_page")

    referral_from_url = request.GET.get("ref", "").strip().upper()

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip().lower()
        phone = request.POST.get("phone", "").strip()
        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        referral_code = request.POST.get("referral_code", "").strip().upper()

        if not username:
            messages.error(request, "Username cannot be empty.")
            return render(request,"accounts/signup.html",{"referral_code": referral_code},)

        if len(username) < 5 or len(username) > 20:
            messages.error(request,"Username must be between 5 and 20 characters." )
            return render(request,"accounts/signup.html",{"referral_code": referral_code},)

        if not re.fullmatch(r"(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d]+", username):
            messages.error(request,"Username must contain both letters and numbers, without spaces or special characters.")
            return render(request,"accounts/signup.html",{"referral_code": referral_code},)

        if User.objects.filter(username__iexact=username).exists():
            messages.error(request, "Username already exists.")
            return render(request,"accounts/signup.html",{"referral_code": referral_code},)

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if not email:
            messages.error(request, "Email cannot be empty.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, email):
            messages.error(request, "Enter a valid email address.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if not re.search(r"[A-Z]", password):
            messages.error(request, "Password must contain one uppercase letter.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if not re.search(r"[a-z]", password):
            messages.error(request, "Password must contain one lowercase letter.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if not re.search(r"[0-9]", password):
            messages.error(request, "Password must contain one number.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            messages.error(request, "Password must contain one special character.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

        referrer_id = None

        if referral_code:
            referrer = User.objects.filter(referral_code__iexact=referral_code).first()

            if not referrer:
                messages.error(request, "Invalid referral code.")
                return render(request, "accounts/signup.html", {"referral_code": referral_code})

            if referrer.username == username:
                messages.error(request, "You cannot use your own referral code.")
                return render(request, "accounts/signup.html", {"referral_code": referral_code})

            referrer_id = referrer.id

        otp = str(random.randint(100000, 999999))

        request.session["signup_data"] = {
            "username": username,
            "email": email,
            "phone": phone,
            "password": password,
            "referrer_id": referrer_id,
            "referral_code": referral_code,
            "otp": otp,
            "issued_at": time.time(),
        }

        try:
            send_wheelverse_otp_email(
                to_email=email,
                username=username,
                otp=otp,
                purpose="Account Verification",
                expiry=5,
            )

            messages.success(request, "OTP sent to your email.")
            return redirect("signup_verify")

        except Exception as e:
            print("EMAIL ERROR:", e)
            request.session.pop("signup_data", None)
            messages.error(request, "OTP email failed. Check Gmail app password/settings.")
            return render(request, "accounts/signup.html", {"referral_code": referral_code})

    return render(request, "accounts/signup.html", {
        "referral_code": referral_from_url,
    })

def signup_verify_view(request):
    import time

    if request.method == "POST":
        user_otp = request.POST.get("otp", "").strip()
        session_data = request.session.get("signup_data")

        if not session_data:
            messages.error(request, "Verification session timed out. Restart registration.")
            return redirect("signup")

        issued_at = session_data.get("issued_at", 0)

        if time.time() - issued_at > 120:
            session_data["otp"] = None
            request.session.modified = True
            messages.error(request, "Your OTP has expired. Please click Resend OTP.")
            return render(request, "accounts/signup_verify.html")

        if user_otp != session_data["otp"]:
            messages.error(request, "Invalid security code. Re-verify values.")
            return render(request, "accounts/signup_verify.html")

        try:
            with transaction.atomic():
                referrer = None

                referrer_id = session_data.get("referrer_id")
                if referrer_id:
                    referrer = User.objects.select_for_update().filter(id=referrer_id).first()

                user = User(
                    username=session_data["username"],
                    email=session_data["email"],
                    phone=session_data["phone"],
                    referred_by=referrer,
                )
                user.set_password(session_data["password"])
                user.save()

                credit_referral_reward(user)

            request.session.pop("signup_data", None)

            user.backend = "django.contrib.auth.backends.ModelBackend"
            login(request, user)

            messages.success(request, "Collector engine unlocked! Welcome to WheelVerse.")
            return redirect("landing_page")

        except Exception as e:
            print("DEBUG ERROR:", e)
            messages.error(request, "Database error: " + str(e))
            return redirect("signup")

    return render(request, "accounts/signup_verify.html")


def resend_signup_otp_view(request):
    import time
    signup_data = request.session.get('signup_data')
    
    if not signup_data:
        messages.error(request, "Registration session expired. Please signup again.")
        return redirect('signup')
        
    try:
        new_otp = str(random.randint(100000, 999999))
        
        signup_data['otp'] = new_otp
        signup_data['issued_at'] = time.time()
        request.session['signup_data'] = signup_data
        request.session.modified = True 
        
        subject = "New OTP — WheelVerse Signup Verification"
        message = f"Your new WheelVerse signup OTP is: {new_otp}"
        
        send_wheelverse_otp_email(
            to_email=signup_data['email'],
            username=signup_data['username'],
            otp=new_otp,
            purpose="Account Verification",
            expiry=5
        )
        
        messages.success(request, "A new OTP has been sent to your email.")
        return redirect('signup_verify')
        
    except Exception as e:
        print("RESEND SIGNUP OTP ERROR:", e)
        messages.error(request, "Failed to resend OTP. Please try again.")
        return redirect('signup_verify')


def login_view(request):

    if request.user.is_authenticated:
        if request.session.get("login_type") == "admin":
            return redirect("admin_dashboard")
        return redirect("landing_page")

    if request.method == "POST":
        email_or_username = request.POST.get("email", "").strip()
        password = request.POST.get("password", "").strip()

        if not email_or_username:
            messages.error(request, "Please enter your email or username.")
            return render(request, "accounts/login.html")

        if not password:
            messages.error(request, "Please enter your password.")
            return render(request, "accounts/login.html")

        user_obj = User.objects.filter(email__iexact=email_or_username).first()

        if not user_obj:
            user_obj = User.objects.filter(username__iexact=email_or_username).first()

        if not user_obj:
            messages.error(request, "Wrong username, email, or password.")
            return render(request, "accounts/login.html")

        user = authenticate(request, username=user_obj.username, password=password)

        if user is None:
            messages.error(request, "Wrong username, email, or password.")
            return render(request, "accounts/login.html")

        if user.is_staff or user.is_superuser:
            messages.error(request, "Admin account cannot login from user login.")
            return redirect("admin_login")

        login(request, user)
        request.session["login_type"] = "user"

        messages.success(request, f"Welcome back, {user.username}!")
        return redirect("landing_page")

    return render(request, "accounts/login.html")


# --- Add these to Accounts/views.py ---
from django.urls import reverse
from urllib.parse import urlencode


def google_login_user(request):
    """
    Entry point for the Google button on the USER login page.
    Stamps intent, then hands off to allauth's provider login URL.
    """
    if request.session.get("login_type") == "admin":
        messages.error(request, "Log out of the admin session first.")
        return redirect("admin_dashboard")

    request.session["oauth_flow"] = "user"
    base = reverse("google_login")  # allauth's built-in provider login url name
    qs = urlencode({"process": "login"})
    return redirect(f"{base}?{qs}")


def google_login_admin(request):
    """
    Entry point for the Google button on the ADMIN login page.
    """
    if request.session.get("login_type") == "user":
        messages.error(request, "Log out of the user session first.")
        return redirect("landing_page")

    request.session["oauth_flow"] = "admin"
    base = reverse("google_login")
    qs = urlencode({"process": "login"})
    return redirect(f"{base}?{qs}")


def logout_view(request):
   
    logout(request)
    return redirect('landing_page')



def forgot_password_view(request):

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        try:
            user = User.objects.get(email=email)
            reset_otp = str(random.randint(100000, 999999))
            
            request.session['pass_reset_data'] = {
                'user_id': user.id,
                'otp': reset_otp,
                'verified': False
            }

            # subject = 'Reset Your WheelVerse Account Security Key'
            # message = f"Security update alert. Use this custom session matrix code to reset parameters: {reset_otp}"
            
            send_wheelverse_otp_email(
                to_email=email,
                username=user.username,
                otp=reset_otp,
                purpose="Password Reset",
                expiry=5
            )
            
            messages.success(request, "Recovery gate key routed into your secure mailbox.")
            return redirect('verify_otp')
            
        except User.DoesNotExist:
            messages.error(request, "No registered identity footprint linked to this email address.")
            return render(request, 'accounts/forgot_password.html')
        except Exception as system_err:
            print("--- SMTP RECOVERY LAYER SYSTEM EXCEPTION ---", str(system_err))
            messages.error(request, "Internal message router error during dispatch tracking loop.")
            return render(request, 'accounts/forgot_password.html')

    return render(request, 'accounts/forgot_password.html')


def resend_otp_view(request):
    reset_data = request.session.get('pass_reset_data')
    
    if not reset_data:
        messages.error(request, "Session expired. Please re-enter your identity parameters.")
        return redirect('forgot_password')
        
    try:
        user = User.objects.get(id=reset_data['user_id'])
        new_otp = str(random.randint(100000, 999999))
        
        reset_data['otp'] = new_otp
        request.session['pass_reset_data'] = reset_data
        request.session.modified = True 
        
        subject = 'New Security Token | WheelVerse Protocols'
        message = f"Your requested alternative verification token: {new_otp}"
        send_wheelverse_otp_email(
            to_email=user.email,
            username=user.username,
            otp=new_otp,
            purpose="Password Reset",
            expiry=5
        )
        
        messages.success(request, "A new token verification key has been routed to your mailbox.")
        return redirect('verify_otp')
        
    except Exception as system_err:
        messages.error(request, "Failed to route alternative payload code. Check router settings.")
        return redirect('verify_otp')


def verify_otp_view(request):
 
    if request.method == 'POST':
        user_otp = request.POST.get('otp', '').strip()
        reset_session = request.session.get('pass_reset_data')

        if not reset_session:
            messages.error(request, "Recovery session track trace expired. Re-trigger process.")
            return redirect('forgot_password')

        if user_otp == reset_session['otp']:
            # Overwriting authorization key state parameters to allow credential mutation
            reset_session['verified'] = True
            request.session.modified = True
            return redirect('reset_password')
        else:
            messages.error(request, "The entered token character allocation map is invalid.")
            return render(request, 'accounts/verify_otp.html')

    return render(request, 'accounts/verify_otp.html')


def reset_password_view(request):

    reset_session = request.session.get('pass_reset_data')

    if not reset_session or not reset_session.get('verified'):
        messages.error(request, "Unauthorized gate injection block trace. Secure your access path first.")
        return redirect('forgot_password')

    if request.method == 'POST':
        new_pass = request.POST.get('password')
        confirm_pass = request.POST.get('confirm_password')

        if not new_pass or not confirm_pass:
            messages.error(request, "Passwords cannot contain null string values.")
            return render(request, 'accounts/reset_password.html')

        if new_pass != confirm_pass:
            messages.error(request, "Input field encryption character mismatched strings.")
            return render(request, 'accounts/reset_password.html')

        try:
            user = User.objects.get(id=reset_session['user_id'])
            
            user.set_password(new_pass)
            user.save()

            del request.session['pass_reset_data']
            
            messages.success(request, "Account pass matrix securely rewritten. Proceed with standard login.")
            return redirect('login')
            
        except Exception as db_mutation_error:
            print("--- CRITICAL DATABASE PASSWORD WRITE OVERWRITE ERROR ---", str(db_mutation_error))
            messages.error(request, "Process halted due to cluster isolation bottleneck errors.")
            return redirect('forgot_password')

    return render(request, 'accounts/reset_password.html')



@login_required
def change_email_view(request):

    import time
    current_user = request.user

    if request.method == 'POST':
        new_email = request.POST.get('new_email', '').strip().lower()

        if not new_email:
            messages.error(request, "Please enter a valid email address.")
            return render(request, 'accounts/change_email.html')

        if new_email == current_user.email.lower():
            messages.error(request, "This is already your current registered email.")
            return render(request, 'accounts/change_email.html')

        if User.objects.filter(email__iexact=new_email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, 'accounts/change_email.html')

        otp_code = f"{random.randint(100000, 999999)}"
        issued_at = time.time()  

        request.session['pending_new_email'] = new_email
        request.session['email_change_otp'] = otp_code
        request.session['email_otp_issued_at'] = issued_at

        subject = "WheelVerse — Email Change Verification Code"
        body = (
            f"Hello {current_user.username},\n\n"
            f"A request was made to change your WheelVerse account email to: {new_email}\n\n"
            f"Your 6-digit verification code is: {otp_code}\n"
            f"This code is valid for 10 minutes only.\n\n"
            f"If you did not request this change, please secure your account immediately."
        )

        try:
            send_wheelverse_otp_email(
                to_email=current_user.email,
                username=current_user.username,
                otp=otp_code,
                purpose="Email Change Verification",
                expiry=10
            )
            messages.success(
                request,
                f"Verification code sent to your current email address. Please check your inbox."
            )
            return redirect('change_email_otp')

        except Exception as e:
            request.session.pop('pending_new_email', None)
            request.session.pop('email_change_otp', None)
            request.session.pop('email_otp_issued_at', None)
            messages.error(request, "Failed to send verification email. Please try again.")
            return render(request, 'accounts/change_email.html')

    return render(request, 'accounts/change_email.html')


@login_required
def change_email_otp_view(request):

    import time
    current_user = request.user

    pending_email = request.session.get('pending_new_email')
    session_otp = request.session.get('email_change_otp')
    issued_at = request.session.get('email_otp_issued_at')

    if not pending_email or not session_otp or issued_at is None:
        messages.error(request, "Session expired. Please start the email change process again.")
        return redirect('change_email')

    if request.method == 'POST':
        user_otp = request.POST.get('otp', '').strip()

        if time.time() - issued_at > 600:
            request.session.pop('email_change_otp', None)
            request.session.pop('pending_new_email', None)
            request.session.pop('email_otp_issued_at', None)
            messages.error(request, "OTP expired. Please request a new OTP.")
            return redirect('change_email')

        if user_otp != session_otp:
            messages.error(request, "Invalid OTP. Please try again.")
            return render(request, 'accounts/change_email_otp.html')

        if User.objects.filter(email__iexact=pending_email).exists():
            request.session.pop('email_change_otp', None)
            request.session.pop('pending_new_email', None)
            request.session.pop('email_otp_issued_at', None)
            messages.error(request, "This email is already registered.")
            return redirect('change_email')

        current_user.email = pending_email
        current_user.save()

        request.session.pop('email_change_otp', None)
        request.session.pop('pending_new_email', None)
        request.session.pop('email_otp_issued_at', None)

        messages.success(request, "Your email address has been successfully updated!")
        return redirect('profile_view')

    return render(request, 'accounts/change_email_otp.html')


@login_required
def resend_email_change_otp_view(request):
  
    import time
    current_user = request.user

    pending_email = request.session.get('pending_new_email')

    if not pending_email:
        messages.error(request, "Session expired. Please start the email change process again.")
        return redirect('change_email')

    new_otp = f"{random.randint(100000, 999999)}"
    issued_at = time.time()

    request.session['email_change_otp'] = new_otp
    request.session['email_otp_issued_at'] = issued_at
    request.session.modified = True

    subject = "WheelVerse — New Email Change Verification Code"
    body = (
        f"Hello {current_user.username},\n\n"
        f"You requested a new verification code to change your WheelVerse email to: {pending_email}\n\n"
        f"Your new 6-digit verification code is: {new_otp}\n"
        f"This code is valid for 10 minutes only.\n\n"
        f"If you did not request this change, please secure your account immediately."
    )

    try:
        send_wheelverse_otp_email(
            to_email=current_user.email,
            username=current_user.username,
            otp=new_otp,
            purpose="Email Change Verification",
            expiry=10
        )
        messages.success(request, "A new verification code has been sent to your current email address.")
    except Exception as e:
        messages.error(request, "Failed to resend verification code. Please try again.")

    return redirect('change_email_otp')

# user Profile
@login_required
def profile_view(request):
    referral_link = request.build_absolute_uri(
        f"/signup/?ref={request.user.referral_code}"
    )

    referral_count = request.user.referrals.count()

    return render(request, "accounts/profile_view.html", {
        "referral_link": referral_link,
        "referral_count": referral_count,
    })



@login_required
def edit_profile_view(request):
    user = request.user 

    if request.method == 'POST':
        user_name = request.POST.get('user_name', '').strip()
        mobile_number = request.POST.get('mobile_number', '').strip()
        
        if not user_name:
            messages.error(request, "Username field cannot be left blank.")
            return render(request, 'accounts/edit_profile.html')

        phone_regex = r'^\+?1?\d{10}$'
        if mobile_number and not re.match(phone_regex, mobile_number):
            messages.error(request, "Invalid phone number format. Use standard digits (e.g. +1234567890).")
            return render(request, 'accounts/edit_profile.html')

        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']

        user.username = user_name
        user.phone = mobile_number
        user.save()

        messages.success(request, 'Collector parameters successfully synchronized!')
        return redirect('profile_view')

    return render(request, 'accounts/edit_profile.html')


@login_required
def change_profile_password_view(request):
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if password != confirm_password:
            messages.error(request, "New password matching mismatch. Verification parameters must match.")
            return render(request, 'accounts/change_profile_pass.html')

        if not request.user.check_password(current_password):
            messages.error(request, "The current password credentials entered are invalid.")
            return render(request, 'accounts/change_profile_pass.html')

        if current_password == password:
            messages.error(request, "New password must differ from your current configuration key.")
            return render(request, 'accounts/change_profile_pass.html')

        try:
            request.user.set_password(password)
            request.user.save()
            
            update_session_auth_hash(request, request.user)
            
            messages.success(request, "Your account security key has been successfully updated.")
            return redirect('login') 

        except Exception as system_err:
            print("--- PROFILE PASSWORD UPDATE ERROR ---", str(system_err))
            messages.error(request, "Internal runtime fault processing memory commit updates.")
            return render(request, 'accounts/change_profile_pass.html')

    return render(request, 'accounts/change_profile_pass.html')


@login_required
def address_list(request):

    addresses = Address.objects.filter(user=request.user)
    return render(request, "address/address_list.html", {"addresses": addresses})


def validate_address_data(request, data):
    
    name = data.get("name", "").strip()
    phone_number = data.get("phone_number", "").strip()
    pincode = data.get("pincode", "").strip()

    '''naame Validation (Cannot be empty or just numbers/symbols)'''
    if not name or len(name) < 2 or len(name) > 20:
        messages.error(request, "Please enter a valid name (2 to 20 characters).")
        return False

    phone_regex = r"^\+?[\d\s-]{7,10}$"
    if not phone_number or not re.match(phone_regex, phone_number):
        messages.error(
            request,
            "Please enter a valid phone number (7 to 10 digits. Allowed characters: +, -, spaces).",
        )
        return False

    if not pincode or not re.match(r"^\d{6}$", pincode):
        messages.error(request, "Postal code / Pincode must be exactly 6 digits.")
        return False

    return True


@login_required
def add_address(request):
    if request.method == "POST":
        name = request.POST.get("name")
        phone_number = request.POST.get("phone_number")
        address_line_1 = request.POST.get("address_line_1")
        address_line_2 = request.POST.get("address_line_2")
        city = request.POST.get("city")
        state = request.POST.get("state")
        pincode = request.POST.get("pincode")
        country = request.POST.get("country", "UNITED STATES")
        address_type = request.POST.get("address_type", "HOME")
        is_default = request.POST.get("is_default") == "on"

        form_data = {"name": name, "phone_number": phone_number, "pincode": pincode}

        if not validate_address_data(request, form_data):
            return render(
                request,
                "address/address_form.html",
                {
                    "posted_data": request.POST, 
                },
            )

        if is_default:
            Address.objects.filter(user=request.user, is_default=True).update(
                is_default=False
            )

        if not Address.objects.filter(user=request.user).exists():
            is_default = True

        Address.objects.create(
            user=request.user,
            name=name,
            phone_number=phone_number,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            city=city,
            state=state,
            pincode=pincode,
            country=country,
            address_type=address_type,
            is_default=is_default,
        )

        messages.success(request, "New address successfully registered.")
        return redirect("address_list")

    return render(request, "address/address_form.html")


@login_required
def edit_address(request, id):
    address = get_object_or_404(Address, id=id, user=request.user)

    if request.method == "POST":
        name = request.POST.get("name")
        phone_number = request.POST.get("phone_number")
        address_line_1 = request.POST.get("address_line_1")
        address_line_2 = request.POST.get("address_line_2")
        city = request.POST.get("city")
        state = request.POST.get("state")
        pincode = request.POST.get("pincode")
        country = request.POST.get("country", "UNITED STATES")
        address_type = request.POST.get("address_type", "HOME")
        is_default = request.POST.get("is_default") == "on"

        form_data = {"name": name, "phone_number": phone_number, "pincode": pincode}

        if not validate_address_data(request, form_data):

            temp_address = {
                "id": id,
                "name": name,
                "phone_number": phone_number,
                "address_line_1": address_line_1,
                "address_line_2": address_line_2,
                "city": city,
                "state": state,
                "pincode": pincode,
                "country": country,
                "address_type": address_type,
                "is_default": address.is_default,  
            }
            return render(
                request,
                "address/address_form.html",
                {"address": temp_address},
            )

        address.name = name
        address.phone_number = phone_number
        address.address_line_1 = address_line_1
        address.address_line_2 = address_line_2
        address.city = city
        address.state = state
        address.pincode = pincode
        address.country = country
        address.address_type = address_type

        if is_default:
            if not address.is_default:
                Address.objects.filter(user=request.user, is_default=True).update(
                    is_default=False
                )
                address.is_default = True
        else:
            if address.is_default:
                other_address = (
                    Address.objects.filter(user=request.user).exclude(id=id).first()
                )
                if other_address:
                    address.is_default = False
                    other_address.is_default = True
                    other_address.save()
                else:
                    address.is_default = True

        address.save()
        messages.success(request, "Address modifications saved successfully.")
        return redirect("address_list")

    return render(request, "address/address_form.html", {"address": address})


@login_required
def delete_address(request, id):


    if request.method == "POST":
        address = get_object_or_404(Address, id=id, user=request.user)
        was_default = address.is_default
        address.delete()

        if was_default:
            fallback = Address.objects.filter(user=request.user).first()
            if fallback:
                fallback.is_default = True
                fallback.save()

        messages.warning(request, "Address node removed permanently.")
    return redirect("address_list")


@login_required
def set_default_address(request, id):

    if request.method == "POST":
        Address.objects.filter(user=request.user, is_default=True).update(is_default=False)
        address = get_object_or_404(Address, id=id, user=request.user)
        address.is_default = True
        address.save()
        messages.success(request, "Primary address changed successfully.")
    return redirect("address_list")