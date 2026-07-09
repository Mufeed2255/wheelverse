from decimal import Decimal

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from adminpanel.models import Coupon

@staff_member_required(login_url="admin_login")
def admin_coupons(request):
    status = request.GET.get("status", "all")
    sort = request.GET.get("sort", "newest")
    today = timezone.now().date()

    coupons = Coupon.objects.filter(is_deleted=False)

    if status == "active":
        coupons = coupons.filter(is_active=True, valid_till__gte=today)
    elif status == "expired":
        coupons = coupons.filter(valid_till__lt=today)
    elif status == "inactive":
        coupons = coupons.filter(is_active=False)

    if sort == "oldest":
        coupons = coupons.order_by("created_at")
    elif sort == "expiry":
        coupons = coupons.order_by("valid_till")
    elif sort == "used":
        coupons = coupons.order_by("-used_count")
    else:
        coupons = coupons.order_by("-created_at")

    active_count = Coupon.objects.filter(
        is_deleted=False,
        is_active=True,
        valid_till__gte=today
    ).count()

    total_redeemed = Coupon.objects.filter(
        is_deleted=False
    ).aggregate(total=Sum("used_count"))["total"] or 0

    paginator = Paginator(coupons, 5)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "adminpanel/coupons/admin_coupon.html", {
        "page_obj": page_obj,
        "status": status,
        "sort": sort,
        "active_count": active_count,
        "total_redeemed": total_redeemed,
    })


@staff_member_required(login_url="admin_login")
def add_coupon(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        code = request.POST.get("code", "").strip().upper()
        discount_type = request.POST.get("discount_type", "PERCENTAGE")
        discount_value = request.POST.get("discount_value") or 0
        min_cart_amount = request.POST.get("min_cart_amount") or 0
        max_discount_amount = request.POST.get("max_discount_amount") or 0
        usage_limit = request.POST.get("usage_limit") or 0
        valid_from = request.POST.get("valid_from")
        valid_till = request.POST.get("valid_till")
        is_active = request.POST.get("is_active") == "on"

        if not name or not code or not valid_till:
            messages.error(request, "Coupon name, code and valid till date are required.")
            return redirect("add_coupon")

        if Coupon.objects.filter(code=code, is_deleted=False).exists():
            messages.error(request, "Coupon code already exists.")
            return redirect("add_coupon")

        Coupon.objects.create(
            name=name,
            code=code,
            discount_type=discount_type,
            discount_value=Decimal(discount_value),
            min_cart_amount=Decimal(min_cart_amount),
            max_discount_amount=Decimal(max_discount_amount),
            usage_limit=int(usage_limit),
            valid_from=valid_from or timezone.now().date(),
            valid_till=valid_till,
            is_active=is_active,
        )

        messages.success(request, "Coupon added successfully.")
        return redirect("admin_coupons")

    return render(request, "adminpanel/coupons/admin_add_coupon.html")


@staff_member_required(login_url="admin_login")
def edit_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id, is_deleted=False)

    if request.method == "POST":
        code = request.POST.get("code", "").strip().upper()

        if Coupon.objects.filter(code=code, is_deleted=False).exclude(id=coupon.id).exists():
            messages.error(request, "Coupon code already exists.")
            return redirect("edit_coupon", coupon_id=coupon.id)

        coupon.name = request.POST.get("name", "").strip()
        coupon.code = code
        coupon.discount_type = request.POST.get("discount_type", "PERCENTAGE")
        coupon.discount_value = Decimal(request.POST.get("discount_value") or 0)
        coupon.min_cart_amount = Decimal(request.POST.get("min_cart_amount") or 0)
        coupon.max_discount_amount = Decimal(request.POST.get("max_discount_amount") or 0)
        coupon.usage_limit = int(request.POST.get("usage_limit") or 0)
        coupon.valid_from = request.POST.get("valid_from")
        coupon.valid_till = request.POST.get("valid_till")
        coupon.is_active = request.POST.get("is_active") == "on"
        coupon.save()

        messages.success(request, "Coupon updated successfully.")
        return redirect("admin_coupons")

    return render(request, "adminpanel/coupons/admin_edit_coupon.html", {
        "coupon": coupon
    })


@staff_member_required(login_url="admin_login")
def delete_coupon_confirm(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id, is_deleted=False)
    return render(request, "adminpanel/coupons/admin_delete_coupon_confirm.html", {
        "coupon": coupon
    })


@staff_member_required(login_url="admin_login")
def delete_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id, is_deleted=False)

    if request.method == "POST":
        coupon.is_deleted = True
        coupon.save()
        messages.success(request, "Coupon deleted successfully.")
        return redirect("admin_coupons")

    return redirect("delete_coupon_confirm", coupon_id=coupon.id)