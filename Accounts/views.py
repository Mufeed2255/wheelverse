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
from django.db.models import Count, Q, Min, Sum
from adminpanel.models import Product, Category, ProductVariant
from .models import Cart
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal

#GATEWAYS & PROFILE VIEWS 

def landing_page(request):
    return render(request, 'accounts/landing_page.html')



def signup_view(request):
    if request.user.is_authenticated:
        return redirect('landing_page')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip().lower()
        phone = request.POST.get('phone', '').strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')

      
      # USERNAME VALIDATIONS

        if not username:
            messages.error(request, "Username cannot be empty.")
            return render(request, 'accounts/signup.html')

        if len(username) < 5 or len(username) > 20:
            messages.error(request, "Username must be between 5 and 20 characters.")
            return render(request, 'accounts/signup.html')

        if not username.isalnum():
            messages.error(request, "Username must contain only letters and numbers.")
            return render(request, 'accounts/signup.html')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, 'accounts/signup.html')


        # EMAIL VALIDATIONS

        if not email:
            messages.error(request, "Email cannot be empty.")
            return render(request, 'accounts/signup.html')

        email_pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        if not re.match(email_pattern, email):
            messages.error(request, "Enter a valid email address.")
            return render(request, 'accounts/signup.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already exists.")
            return render(request, 'accounts/signup.html')

        # PASSWORD COMPLEXITY VALIDATIONS

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters.")
            return render(request, 'accounts/signup.html')

        if not re.search(r"[A-Z]", password):
            messages.error(request, "Password must contain one uppercase letter.")
            return render(request, 'accounts/signup.html')

        if not re.search(r"[a-z]", password):
            messages.error(request, "Password must contain one lowercase letter.")
            return render(request, 'accounts/signup.html')

        if not re.search(r"[0-9]", password):
            messages.error(request, "Password must contain one number.")
            return render(request, 'accounts/signup.html')

        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            messages.error(request, "Password must contain one special character.")
            return render(request, 'accounts/signup.html')

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/signup.html')

        # OTP GENERATION & SESSION STORAGE
        otp = str(random.randint(100000, 999999))

        request.session['signup_data'] = {
            'username': username,
            'email': email,
            'phone': phone,
            'password': password,
            'otp': otp,
            'issued_at': time.time()  # ⏳ ടൈം ഔട്ട് നോക്കാൻ സമയം ഇവിടെ സേവ് ചെയ്യുന്നു
        }

        try:
            subject = "WheelVerse Account Verification OTP"
            message = f"Your WheelVerse signup OTP is: {otp}"
            
            send_mail(
                subject,
                message,
                settings.EMAIL_HOST_USER,
                [email],
                fail_silently=False,
            )

            messages.success(request, "OTP sent to your email.")
            return redirect('signup_verify')

        except Exception as e:
            print("EMAIL ERROR:", e)
            
            if 'signup_data' in request.session:
                del request.session['signup_data']
            messages.error(request, "OTP email failed. Check Gmail app password/settings.")
            return render(request, 'accounts/signup.html')

    return render(request, 'accounts/signup.html')

def signup_verify_view(request):
    import time
    if request.method == 'POST':
        user_otp = request.POST.get('otp', '').strip()
        session_data = request.session.get('signup_data')

        if not session_data:
            messages.error(request, "Verification session timed out. Restart registration.")
            return redirect('signup')

        issued_at = session_data.get('issued_at', 0)
        if time.time() - issued_at > 60:
            
            session_data['otp'] = None 
            request.session.modified = True
            messages.error(request, "Your OTP has expired. Please click Resend OTP.")
            return render(request, 'accounts/signup_verify.html')

        if user_otp == session_data['otp']:
            try:
                user = User(
                    username=session_data['username'],
                    email=session_data['email']
                )
                user.set_password(session_data['password'])
                user.phone = session_data['phone']
                
                user.save()
                

                del request.session['signup_data']
                user.backend = 'django.contrib.auth.backends.ModelBackend' 
                login(request, user)
                messages.success(request, "Collector engine unlocked! Welcome to WheelVerse.")
                return redirect('landing_page')
                
            except Exception as e:
                print("DEBUG ERROR:", e)
                messages.error(request, "Database error: " + str(e))
                return redirect('signup')
            
        else:
            messages.error(request, "Invalid security code. Re-verify values.")
            return render(request, 'accounts/signup_verify.html')

    return render(request, 'accounts/signup_verify.html')


def resend_signup_otp_view(request):
    import time
    # സെഷനിൽ നിന്ന് പഴയ ഡാറ്റ എടുക്കുന്നു
    signup_data = request.session.get('signup_data')
    
    if not signup_data:
        messages.error(request, "Registration session expired. Please signup again.")
        return redirect('signup')
        
    try:
        # പുതിയ OTP ജനറേറ്റ് ചെയ്യുന്നു
        new_otp = str(random.randint(100000, 999999))
        
        # സെഷനിലെ OTP യും സമയവും അപ്ഡേറ്റ് ചെയ്യുന്നു
        signup_data['otp'] = new_otp
        signup_data['issued_at'] = time.time()
        request.session['signup_data'] = signup_data
        request.session.modified = True 
        
        # പുതിയ OTP ഇമെയിലിലേക്ക് അയക്കുന്നു
        subject = "New OTP — WheelVerse Signup Verification"
        message = f"Your new WheelVerse signup OTP is: {new_otp}"
        
        send_mail(
            subject,
            message,
            settings.EMAIL_HOST_USER,
            [signup_data['email']],
            fail_silently=False,
        )
        
        messages.success(request, "A new OTP has been sent to your email.")
        return redirect('signup_verify')
        
    except Exception as e:
        print("RESEND SIGNUP OTP ERROR:", e)
        messages.error(request, "Failed to resend OTP. Please try again.")
        return redirect('signup_verify')


# AUTH SESSION CONTROL 

def login_view(request):
    
    if request.user.is_authenticated:
        return redirect('landing_page')

    if request.method == 'POST':
        email_or_username = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()


     # SIMPLE IF-CONDITION VALIDATIONS
        
        if not email_or_username:
            messages.error(request, "Please enter your email or username.")
            return render(request, 'accounts/login.html')

        if not password:
            messages.error(request, "Please enter your password.")
            return render(request, 'accounts/login.html')

        user_obj = User.objects.filter(email=email_or_username).first()

        if not user_obj:
            user_obj = User.objects.filter(username=email_or_username).first()

        if not user_obj:
            messages.error(request, "Wrong username, email, or password.")
            return render(request, 'accounts/login.html')

    # PASSWORD CHECK AND LOGIN
        
        user = authenticate(request, username=user_obj.username, password=password)
        
        if user is None:
            messages.error(request, "Wrong username, email, or password.")
            return render(request, 'accounts/login.html')

        login(request, user)

        next_url = request.GET.get('next')
        if next_url:
            return redirect(next_url)

        messages.success(request, f"Welcome back, {user.username}!")
        return redirect('landing_page')

    return render(request, 'accounts/login.html')


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

            subject = 'Reset Your WheelVerse Account Security Key'
            message = f"Security update alert. Use this custom session matrix code to reset parameters: {reset_otp}"
            
            send_mail(subject, message, settings.EMAIL_HOST_USER, [email], fail_silently=False)
            
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
        send_mail(subject, message, settings.EMAIL_HOST_USER, [user.email], fail_silently=False)
        
        messages.success(request, "A new token verification key has been routed to your mailbox.")
        return redirect('verify_otp')
        
    except Exception as system_err:
        print("--- SMTP RESEND EXCEPTION HANDLER ---", str(system_err))
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
    """
    STEP 1: User enters new email address.
    Validates the new email, sends OTP to CURRENT email, then redirects to OTP verification page.
    """
    import time
    current_user = request.user

    if request.method == 'POST':
        new_email = request.POST.get('new_email', '').strip().lower()

        # Validation: must not be empty
        if not new_email:
            messages.error(request, "Please enter a valid email address.")
            return render(request, 'accounts/change_email.html')

        # Validation: must differ from current email
        if new_email == current_user.email.lower():
            messages.error(request, "This is already your current registered email.")
            return render(request, 'accounts/change_email.html')

        # Validation: new email must not already be registered
        if User.objects.filter(email__iexact=new_email).exists():
            messages.error(request, "This email is already registered.")
            return render(request, 'accounts/change_email.html')

        # Generate OTP and store in session
        otp_code = f"{random.randint(100000, 999999)}"
        issued_at = time.time()  # Unix timestamp

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
            # OTP is always sent to the CURRENT (old) email for security
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [current_user.email],
                fail_silently=False,
            )
            messages.success(
                request,
                f"Verification code sent to your current email address. Please check your inbox."
            )
            return redirect('change_email_otp')

        except Exception as e:
            # Clean up session on mail failure
            request.session.pop('pending_new_email', None)
            request.session.pop('email_change_otp', None)
            request.session.pop('email_otp_issued_at', None)
            messages.error(request, "Failed to send verification email. Please try again.")
            return render(request, 'accounts/change_email.html')

    # GET request — show the Enter New Email form
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
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [current_user.email],
            fail_silently=False,
        )
        messages.success(request, "A new verification code has been sent to your current email address.")
    except Exception as e:
        messages.error(request, "Failed to resend verification code. Please try again.")

    return redirect('change_email_otp')

# user Profile
@login_required
def profile_view(request):
    return render(request, 'accounts/profile_view.html')



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

    # 1. Name Validation (Cannot be empty or just numbers/symbols)
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
            # Render the form back with entered details so user doesn't lose data
            return render(
                request,
                "address/address_form.html",
                {
                    "posted_data": request.POST,  # Pass back the input data to show in inputs
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
                "is_default": address.is_default,  # keep database state original status display
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

def user_collections(request):
    search_query = request.GET.get('search', '').strip()
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    sort_by = request.GET.get('sort_by', '')
    rarity = request.GET.get('rarity', '').strip()
    

    try:
        price_min = int(request.GET.get('price_min', 0))
    except (ValueError, TypeError):
        price_min = 0

    try:
        price_max = int(request.GET.get('price_max', 150000))
    except (ValueError, TypeError):
        price_max = 150000


    products_queryset = Product.objects.filter(is_deleted=False, is_active=True)
    

    categories = Category.objects.filter(is_active=True).annotate(
        total_items=Count('products', filter=Q(products__is_deleted=False, products__is_active=True))
    )


    if search_query:
        products_queryset = products_queryset.filter(name__icontains=search_query)
        

    if category_id:
        products_queryset = products_queryset.filter(category_id=category_id)


    if rarity:
        products_queryset = products_queryset.filter(rarity__iexact=rarity)


    

    products_queryset = products_queryset.annotate(min_price=Min('variants__price'))

    if price_min:
        products_queryset = products_queryset.filter(min_price__gte=price_min)
    if price_max:
        products_queryset = products_queryset.filter(min_price__lte=price_max)

    if sort_by == 'a-z':
        products_queryset = products_queryset.order_by('name')
    elif sort_by == 'z-a':
        products_queryset = products_queryset.order_by('-name')
    elif sort_by == 'price-low': 
        products_queryset = products_queryset.order_by('min_price')
    elif sort_by == 'price-high': 
        products_queryset = products_queryset.order_by('-min_price')
    elif sort_by == 'oldest': 
        products_queryset = products_queryset.order_by('id')
    else:
        products_queryset = products_queryset.order_by('-id')

    products_list = list(products_queryset)

    if status == 'in_stock':
        products_list = [p for p in products_list if p.total_stock > 10]
    elif status == 'limited':
        products_list = [p for p in products_list if 0 < p.total_stock <= 10]
    elif status == 'out_of_stock':
        products_list = [p for p in products_list if p.total_stock == 0]

    paginator = Paginator(products_list, 6) 
    page = request.GET.get('page', 1)
    
    try:
        paginated_products = paginator.page(page)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)

    context = {
        'products': paginated_products,  
        'categories': categories,
        'total_products_count': len(products_list),
        'current_search': search_query,
        'current_category': category_id,
        'current_status': status,
        'current_sort': sort_by,
        'current_rarity': rarity,  
        'price_min': price_min,
        'price_max': price_max,
        'rarity_choices': [('', 'All Rarities')] + Product.RARITY_CHOICES,
}
    return render(request, 'products/collections.html', context)


def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.filter(is_deleted=False, is_active=True).annotate(
            variant_stock=Sum("variants__stock"),
            min_variant_price=Min("variants__price")
        ),
        id=product_id
    )

    variants = product.variants.all()
    first_variant = variants.first()

    stock_count = product.variant_stock or 0

    return render(request, "products/product_detail.html", {
        "product": product,
        "variants": variants,
        "first_variant": first_variant,
        "stock_count": stock_count,
    })
    
    



@login_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.filter(is_deleted=False, is_active=True).annotate(
            variant_stock=Sum("variants__stock"),
            min_variant_price=Min("variants__price")
        ),
        id=product_id
    )

    variants = product.variants.all()
    first_variant = variants.first()
    cart_count = Cart.objects.filter(user=request.user).count()

    return render(request, "products/product_detail.html", {
        "product": product,
        "variants": variants,
        "first_variant": first_variant,
        "cart_count": cart_count,
    })


@login_required
def add_to_cart(request):
    if request.method == "POST":
        variant_id = request.POST.get("variant_id")
        quantity = int(request.POST.get("quantity", 1))

        variant = get_object_or_404(ProductVariant, id=variant_id)
        product = variant.product

        if quantity > variant.stock:
            messages.error(request, "Stock unavailable.")
            return redirect("product_detail", product_id=product.id)

        if Cart.objects.filter(user=request.user, variant=variant).exists():
            messages.error(request, "This product is already added to cart.")
            return redirect("product_detail", product_id=product.id)

        Cart.objects.create(
            user=request.user,
            variant=variant,
            quantity=quantity
        )

        messages.success(request, "Product added to cart successfully.")
        return redirect("cart")

    return redirect("collections")


@login_required
def cart_view(request):
    cart_items = Cart.objects.filter(user=request.user).select_related(
        "variant",
        "variant__product",
        "variant__product__category"
    )

    subtotal = sum(item.subtotal() for item in cart_items)
    discount = Decimal("0.00")
    shipping = Decimal("0.00")

    if subtotal > 0:
        shipping = Decimal("80.00")

    grand_total = subtotal - discount + shipping
    cart_count = cart_items.count()

    return render(request, "products/cart.html", {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "grand_total": grand_total,
        "cart_count": cart_count,
    })


@login_required
def increase_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)

    if cart_item.quantity >= cart_item.variant.stock:
        messages.error(request, "Stock unavailable.")
    else:
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, "Cart updated successfully.")

    return redirect("cart")


@login_required
def decrease_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
        messages.success(request, "Cart updated successfully.")

    return redirect("cart")


@login_required
def remove_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
    cart_item.delete()

    messages.success(request, "Product removed from cart.")
    return redirect("cart")