from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import (
    staff_member_required,
)
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.views.decorators.http import require_POST

from adminpanel.models import Coupon


VALID_DISCOUNT_TYPES = {
    "PERCENTAGE",
    "FIXED",
}


def parse_decimal(value, default=None):
    """
    Safely convert a form value into Decimal.

    Returns default when the submitted value is
    empty or invalid.
    """
    if value in (None, ""):
        return default

    try:
        return Decimal(str(value))
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return default


def parse_positive_integer(value, default=0):
    """
    Safely convert a form value into a
    non-negative integer.
    """
    try:
        parsed_value = int(value or default)
    except (
        TypeError,
        ValueError,
    ):
        return default

    return max(parsed_value, 0)


def get_coupon_form_data(request):
    """
    Read and clean coupon form values.
    """
    discount_type = (
        request.POST.get(
            "discount_type",
            "PERCENTAGE",
        )
        .strip()
        .upper()
    )

    max_discount_amount = parse_decimal(
        request.POST.get(
            "max_discount_amount"
        ),
        default=None,
    )

    # Fixed coupons do not use a maximum cap.
    if discount_type == "FIXED":
        max_discount_amount = Decimal("0.00")

    return {
        "name": (
            request.POST.get("name", "")
            .strip()
        ),
        "code": (
            request.POST.get("code", "")
            .strip()
            .upper()
        ),
        "discount_type": discount_type,
        "discount_value": parse_decimal(
            request.POST.get(
                "discount_value"
            ),
            default=None,
        ),
        "min_cart_amount": parse_decimal(
            request.POST.get(
                "min_cart_amount"
            ),
            default=Decimal("0.00"),
        ),
        "max_discount_amount": (
            max_discount_amount
        ),
        "usage_limit": parse_positive_integer(
            request.POST.get("usage_limit"),
            default=0,
        ),
        "valid_from": (
            request.POST.get(
                "valid_from",
                "",
            )
            .strip()
        ),
        "valid_till": (
            request.POST.get(
                "valid_till",
                "",
            )
            .strip()
        ),
        "is_active": (
            request.POST.get("is_active")
            == "on"
        ),
    }


def validate_coupon_data(
    form_data,
    *,
    coupon=None,
):
    """
    Validate add/edit coupon data.

    Returns:
        field_name, error_message

    Returns:
        None, None
    when everything is valid.
    """

    name = form_data["name"]
    code = form_data["code"]
    discount_type = form_data[
        "discount_type"
    ]
    discount_value = form_data[
        "discount_value"
    ]
    min_cart_amount = form_data[
        "min_cart_amount"
    ]
    max_discount_amount = form_data[
        "max_discount_amount"
    ]
    usage_limit = form_data["usage_limit"]
    valid_from = form_data["valid_from"]
    valid_till = form_data["valid_till"]

    if not name:
        return (
            "name",
            "Coupon name is required.",
        )

    if len(name) < 3 or len(name) > 100:
        return (
            "name",
            (
                "Coupon name must be between "
                "3 and 100 characters."
            ),
        )

    if not code:
        return (
            "code",
            "Coupon code is required.",
        )

    if len(code) < 3 or len(code) > 30:
        return (
            "code",
            (
                "Coupon code must be between "
                "3 and 30 characters."
            ),
        )

    if not code.replace("_", "").isalnum():
        return (
            "code",
            (
                "Coupon code can contain only "
                "letters, numbers and underscores."
            ),
        )

    duplicate_query = Coupon.objects.filter(
        code__iexact=code,
        is_deleted=False,
    )

    if coupon:
        duplicate_query = duplicate_query.exclude(
            id=coupon.id
        )

    if duplicate_query.exists():
        return (
            "code",
            "Coupon code already exists.",
        )

    if (
        discount_type
        not in VALID_DISCOUNT_TYPES
    ):
        return (
            "discount_type",
            "Select a valid discount type.",
        )

    if discount_value is None:
        return (
            "discount_value",
            "Discount value is required.",
        )

    if discount_value <= 0:
        return (
            "discount_value",
            (
                "Discount value must be greater "
                "than zero."
            ),
        )

    if min_cart_amount is None:
        return (
            "min_cart_amount",
            (
                "Minimum cart amount must be "
                "a valid number."
            ),
        )

    if min_cart_amount < 0:
        return (
            "min_cart_amount",
            (
                "Minimum cart amount cannot "
                "be negative."
            ),
        )

    # -----------------------------------------
    # Percentage coupon validations
    # -----------------------------------------
    if discount_type == "PERCENTAGE":
        if discount_value > Decimal("100.00"):
            return (
                "discount_value",
                (
                    "Percentage discount cannot "
                    "exceed 100%."
                ),
            )

        if max_discount_amount is None:
            return (
                "max_discount_amount",
                (
                    "Maximum discount amount is "
                    "required for percentage coupons."
                ),
            )

        if max_discount_amount <= 0:
            return (
                "max_discount_amount",
                (
                    "Maximum discount amount must "
                    "be greater than zero."
                ),
            )

        if (
            min_cart_amount > 0
            and max_discount_amount
            > min_cart_amount
        ):
            return (
                "max_discount_amount",
                (
                    "Maximum discount amount cannot "
                    "be greater than the minimum "
                    "cart amount."
                ),
            )

    # -----------------------------------------
    # Fixed coupon validations
    # -----------------------------------------
    elif discount_type == "FIXED":
        # A fixed discount must always be lower
        # than the required minimum cart amount.
        if min_cart_amount <= 0:
            return (
                "min_cart_amount",
                (
                    "Minimum cart amount is required "
                    "for a fixed coupon."
                ),
            )

        if min_cart_amount <= discount_value:
            return (
                "min_cart_amount",
                (
                    "Minimum cart amount must be "
                    "greater than the fixed discount "
                    "value."
                ),
            )

        # Fixed coupons do not use a maximum cap.
        form_data[
            "max_discount_amount"
        ] = Decimal("0.00")

    if usage_limit < 0:
        return (
            "usage_limit",
            "Usage limit cannot be negative.",
        )

    if not valid_from:
        return (
            "valid_from",
            "Valid from date is required.",
        )

    if not valid_till:
        return (
            "valid_till",
            "Valid till date is required.",
        )

    if valid_till < valid_from:
        return (
            "valid_till",
            (
                "Valid till date must be on or "
                "after the valid from date."
            ),
        )

    return None, None


def coupon_form_context(
    *,
    coupon=None,
    form_data=None,
    error_field=None,
    error_message=None,
):
    return {
        "coupon": coupon,
        "form_data": form_data,
        "error_field": error_field,
        "error_message": error_message,
    }


@staff_member_required(
    login_url="admin_login"
)
def admin_coupons(request):
    status = (
        request.GET.get("status", "all")
        .strip()
        .lower()
    )

    sort = (
        request.GET.get("sort", "newest")
        .strip()
        .lower()
    )

    today = timezone.localdate()

    coupons = Coupon.objects.filter(
        is_deleted=False
    )

    if status == "active":
        coupons = coupons.filter(
            is_active=True,
            valid_from__lte=today,
            valid_till__gte=today,
        )

    elif status == "upcoming":
        coupons = coupons.filter(
            is_active=True,
            valid_from__gt=today,
        )

    elif status == "expired":
        coupons = coupons.filter(
            valid_till__lt=today
        )

    elif status == "inactive":
        coupons = coupons.filter(
            is_active=False
        )

    if sort == "oldest":
        coupons = coupons.order_by(
            "created_at"
        )

    elif sort == "expiry":
        coupons = coupons.order_by(
            "valid_till",
            "-created_at",
        )

    elif sort == "used":
        coupons = coupons.order_by(
            "-used_count",
            "-created_at",
        )

    else:
        coupons = coupons.order_by(
            "-created_at"
        )

    active_count = Coupon.objects.filter(
        is_deleted=False,
        is_active=True,
        valid_from__lte=today,
        valid_till__gte=today,
    ).count()

    total_redeemed = (
        Coupon.objects
        .filter(is_deleted=False)
        .aggregate(
            total=Sum("used_count")
        )["total"]
        or 0
    )

    paginator = Paginator(
        coupons,
        5,
    )

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "adminpanel/coupons/admin_coupon.html",
        {
            "page_obj": page_obj,
            "status": status,
            "sort": sort,
            "active_count": active_count,
            "total_redeemed": total_redeemed,
        },
    )


@staff_member_required(
    login_url="admin_login"
)
@transaction.atomic
def add_coupon(request):
    if request.method == "POST":
        form_data = get_coupon_form_data(
            request
        )

        error_field, error_message = (
            validate_coupon_data(
                form_data
            )
        )

        if error_message:
            messages.error(
                request,
                error_message,
            )

            return render(
                request,
                (
                    "adminpanel/coupons/"
                    "admin_add_coupon.html"
                ),
                coupon_form_context(
                    form_data=form_data,
                    error_field=error_field,
                    error_message=error_message,
                ),
                status=400,
            )

        Coupon.objects.create(
            name=form_data["name"],
            code=form_data["code"],
            discount_type=(
                form_data["discount_type"]
            ),
            discount_value=(
                form_data["discount_value"]
            ),
            min_cart_amount=(
                form_data["min_cart_amount"]
            ),
            max_discount_amount=(
                form_data[
                    "max_discount_amount"
                ]
            ),
            usage_limit=(
                form_data["usage_limit"]
            ),
            valid_from=(
                form_data["valid_from"]
            ),
            valid_till=(
                form_data["valid_till"]
            ),
            is_active=(
                form_data["is_active"]
            ),
        )

        messages.success(
            request,
            "Coupon added successfully.",
        )

        return redirect("admin_coupons")

    return render(
        request,
        (
            "adminpanel/coupons/"
            "admin_add_coupon.html"
        ),
    )


@staff_member_required(
    login_url="admin_login"
)
@transaction.atomic
def edit_coupon(
    request,
    coupon_id,
):
    coupon = get_object_or_404(
        Coupon,
        id=coupon_id,
        is_deleted=False,
    )

    if request.method == "POST":
        form_data = get_coupon_form_data(
            request
        )

        error_field, error_message = (
            validate_coupon_data(
                form_data,
                coupon=coupon,
            )
        )

        if error_message:
            messages.error(
                request,
                error_message,
            )

            return render(
                request,
                (
                    "adminpanel/coupons/"
                    "admin_edit_coupon.html"
                ),
                coupon_form_context(
                    coupon=coupon,
                    form_data=form_data,
                    error_field=error_field,
                    error_message=error_message,
                ),
                status=400,
            )

        coupon.name = form_data["name"]
        coupon.code = form_data["code"]
        coupon.discount_type = (
            form_data["discount_type"]
        )
        coupon.discount_value = (
            form_data["discount_value"]
        )
        coupon.min_cart_amount = (
            form_data["min_cart_amount"]
        )
        coupon.max_discount_amount = (
            form_data[
                "max_discount_amount"
            ]
        )
        coupon.usage_limit = (
            form_data["usage_limit"]
        )
        coupon.valid_from = (
            form_data["valid_from"]
        )
        coupon.valid_till = (
            form_data["valid_till"]
        )
        coupon.is_active = (
            form_data["is_active"]
        )

        coupon.save()

        messages.success(
            request,
            "Coupon updated successfully.",
        )

        return redirect("admin_coupons")

    return render(
        request,
        (
            "adminpanel/coupons/"
            "admin_edit_coupon.html"
        ),
        {
            "coupon": coupon,
        },
    )


@staff_member_required(
    login_url="admin_login"
)
def delete_coupon_confirm(
    request,
    coupon_id,
):
    coupon = get_object_or_404(
        Coupon,
        id=coupon_id,
        is_deleted=False,
    )

    return render(
        request,
        (
            "adminpanel/coupons/"
            "admin_delete_coupon_confirm.html"
        ),
        {
            "coupon": coupon,
        },
    )


@staff_member_required(
    login_url="admin_login"
)
@require_POST
@transaction.atomic
def delete_coupon(
    request,
    coupon_id,
):
    coupon = get_object_or_404(
        Coupon,
        id=coupon_id,
        is_deleted=False,
    )

    coupon.is_deleted = True
    coupon.is_active = False

    coupon.save(
        update_fields=[
            "is_deleted",
            "is_active",
        ]
    )

    messages.success(
        request,
        "Coupon deleted successfully.",
    )

    return redirect("admin_coupons")