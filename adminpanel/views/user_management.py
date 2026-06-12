# adminpanel/views/user_management.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib import messages
from django.db.models import Q

User = get_user_model()


def is_admin(user):

    return user.is_authenticated and (user.is_staff or user.is_superuser)

@login_required
@user_passes_test(is_admin, login_url='admin_login')
def admin_users(request):
   
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', 'all')
    sort = request.GET.get('sort', 'newest')
    page_number = request.GET.get('page')

    users_list = User.objects.filter(
        is_staff=False,
        is_superuser=False
    )

    if search:
        q_filter = (
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(phone__icontains=search)
        )
        
        try:
            user_id = int(search)
            q_filter |= Q(id=user_id)
        except ValueError:
            pass

        users_list = users_list.filter(q_filter)

    if status == 'active':
        users_list = users_list.filter(is_active=True)
    elif status == 'inactive':
        users_list = users_list.filter(is_active=False)

    if sort == 'a-z':
        users_list = users_list.order_by('username')
    elif sort == 'oldest':
        users_list = users_list.order_by('date_joined')
    else:  # default: newest
        users_list = users_list.order_by('-date_joined')

    total_count = users_list.count()

    paginator = Paginator(users_list, 10)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'search': search,
        'status': status,
        'sort': sort,
        'total_count': total_count,
    }

    return render(request, "adminpanel/admin_login/admin_user.html", context)


@staff_member_required(login_url="admin_login")
def view_user(request, user_id):
 
    user_obj = get_object_or_404(
        User,
        id=user_id,
        is_staff=False,
        is_superuser=False
    )

    default_address = user_obj.addresses.filter(is_default=True).first()

    context = {
        "user_obj": user_obj,
        "default_address": default_address,
    }

    return render(request, "adminpanel/admin_login/view_user.html", context)


@staff_member_required(login_url="admin_login")
def toggle_user_status(request, user_id):
    
    
    if request.method != "POST":
        messages.error(request, "Invalid request method. Status changes require a POST request.")
        return redirect("admin_users")

    user_obj = get_object_or_404(
        User,
        id=user_id,
        is_staff=False,
        is_superuser=False
    )

    if user_obj.id == request.user.id:
        messages.error(request, "Access Denied: You cannot deactivate your own admin account.")
        return redirect("view_user", user_id=user_obj.id)

    # Toggle the status
    user_obj.is_active = not user_obj.is_active
    user_obj.save()

    action_type = 'ACTIVATE_USER' if user_obj.is_active else 'DEACTIVATE_USER'
    action_desc = (
        f"Admin '{request.user.username}' {'activated' if user_obj.is_active else 'deactivated'} "
        f"user '{user_obj.username}' (ID: {user_obj.id})."
    )

    from adminpanel.models import AdminActivityLog
    AdminActivityLog.objects.create(
        admin=request.user,
        action=action_type,
        description=action_desc,
        target_user=user_obj,
        ip_address=get_client_ip(request),
    )

    if user_obj.is_active:
        messages.success(request, f"✓ User '{user_obj.username}' has been Activated Successfully.")
    else:
        messages.success(request, f"⊘ User '{user_obj.username}' has been Deactivated Successfully.")

    return redirect("view_user", user_id=user_obj.id)