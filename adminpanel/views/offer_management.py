from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from adminpanel.models import Category, Offer, Product
from django.views.decorators.http import require_POST

def _parse_decimal(value):
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _offer_form_context(offer=None):
    return {
        "offer": offer,
        "products": Product.objects.filter(
            is_active=True,
            is_deleted=False,
        ).select_related("category").order_by("name"),
        "categories": Category.objects.filter(
            is_active=True,
        ).order_by("name"),
    }


def _save_offer_from_request(request, offer=None):
    title = request.POST.get("title", "").strip()
    offer_type = request.POST.get("offer_type", "").strip().upper()
    discount_type = request.POST.get(
        "discount_type",
        "PERCENTAGE",
    ).strip().upper()

    product_id = request.POST.get("product") or None
    category_id = request.POST.get("category") or None
    discount_value = _parse_decimal(
        request.POST.get("discount_value")
    )
    start_date = request.POST.get("start_date")
    end_date = request.POST.get("end_date")
    is_active = request.POST.get("is_active") == "on"

    if not title:
        return None, "Offer title is required."

    if offer_type not in {"PRODUCT", "CATEGORY"}:
        return None, "Select a valid offer type."

    if discount_type not in {"PERCENTAGE", "FIXED"}:
        return None, "Select a valid discount type."

    if discount_value is None or discount_value <= 0:
        return None, "Discount value must be greater than zero."

    if not start_date or not end_date:
        return None, "Start date and end date are required."

    offer = offer or Offer()

    offer.title = title
    offer.offer_type = offer_type
    offer.discount_type = discount_type
    offer.discount_value = discount_value
    offer.start_date = start_date
    offer.end_date = end_date
    offer.is_active = is_active

    if offer_type == "PRODUCT":
        offer.product_id = product_id
        offer.category = None
    else:
        offer.category_id = category_id
        offer.product = None

    try:
        offer.full_clean()
        offer.save()
    except ValidationError as exc:
        error_messages = []

        if hasattr(exc, "message_dict"):
            for values in exc.message_dict.values():
                error_messages.extend(values)
        else:
            error_messages.extend(exc.messages)

        return None, " ".join(error_messages)

    return offer, None


@staff_member_required(login_url="admin_login")
def admin_offers(request):
    search = request.GET.get("search", "").strip()
    offer_type = request.GET.get("type", "all").strip().upper()
    status = request.GET.get("status", "all").strip().lower()

    today = timezone.localdate()

    offers = Offer.objects.filter(
        is_deleted=False
    ).select_related(
        "product",
        "category",
    )

    if search:
        offers = offers.filter(
            Q(title__icontains=search)
            | Q(product__name__icontains=search)
            | Q(category__name__icontains=search)
        )

    if offer_type in {"PRODUCT", "CATEGORY"}:
        offers = offers.filter(offer_type=offer_type)

    if status == "active":
        offers = offers.filter(
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
        )
    elif status == "upcoming":
        offers = offers.filter(
            is_active=True,
            start_date__gt=today,
        )
    elif status == "expired":
        offers = offers.filter(end_date__lt=today)
    elif status == "inactive":
        offers = offers.filter(is_active=False)

    offers = offers.order_by("-created_at")

    paginator = Paginator(offers, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(
        request,
        "adminpanel/offers/offer_list.html",
        {
            "page_obj": page_obj,
            "search": search,
            "offer_type": offer_type.lower(),
            "status": status,
            "base_query": query_params.urlencode(),
        },
    )


@staff_member_required(login_url="admin_login")
def add_offer(request):
    if request.method == "POST":
        offer, error = _save_offer_from_request(request)

        if error:
            messages.error(request, error)
            return render(
                request,
                "adminpanel/offers/offer_form.html",
                {
                    **_offer_form_context(),
                    "mode": "add",
                    "form_data": request.POST,
                },
            )

        messages.success(request, "Offer created successfully.")
        return redirect("admin_offers")

    return render(
        request,
        "adminpanel/offers/offer_form.html",
        {
            **_offer_form_context(),
            "mode": "add",
        },
    )


@staff_member_required(login_url="admin_login")
def edit_offer(request, offer_id):
    offer = get_object_or_404(
        Offer,
        id=offer_id,
        is_deleted=False,
    )

    if request.method == "POST":
        saved_offer, error = _save_offer_from_request(
            request,
            offer=offer,
        )

        if error:
            messages.error(request, error)
            return render(
                request,
                "adminpanel/offers/offer_form.html",
                {
                    **_offer_form_context(offer),
                    "mode": "edit",
                    "form_data": request.POST,
                },
            )

        messages.success(request, "Offer updated successfully.")
        return redirect("admin_offers")

    return render(
        request,
        "adminpanel/offers/offer_form.html",
        {
            **_offer_form_context(offer),
            "mode": "edit",
        },
    )



@staff_member_required(login_url="admin_login")
@require_POST
def delete_offer(request, offer_id):
    offer = get_object_or_404(
        Offer,
        id=offer_id,
        is_deleted=False,
    )

    offer.is_deleted = True
    offer.is_active = False

    update_fields = ["is_deleted", "is_active"]
    if hasattr(offer, "updated_at"):
        offer.updated_at = timezone.now()
        update_fields.append("updated_at")

    offer.save(update_fields=update_fields)

    messages.success(request, f"Offer '{offer.title}' deleted successfully.")
    return redirect("admin_offers")


@staff_member_required(login_url="admin_login")
def toggle_offer_status(request, offer_id):
    offer = get_object_or_404(
        Offer,
        id=offer_id,
        is_deleted=False,
    )

    if request.method == "POST":
        offer.is_active = not offer.is_active
        offer.save(update_fields=["is_active", "updated_at"])

        messages.success(
            request,
            f"Offer {'activated' if offer.is_active else 'deactivated'} successfully.",
        )

    return redirect("admin_offers")
