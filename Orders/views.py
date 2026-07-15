import re
from decimal import Decimal

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction

from Accounts.models import Address
from Products.models import Cart, ProductVariant
from .models import Order, OrderItem, OrderAddress,  ReturnRequest, ReturnRequestImage ,ProductReview, ProductReviewImage
from django.db.models import Sum
from adminpanel.models import Product as AdminProduct
from django.utils import timezone
from adminpanel.models import Coupon
from .models import CouponUsage

from django.db import models
from django.core.paginator import Paginator
from django.db.models import Q
from decimal import Decimal


from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import razorpay
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from Wallet.models import Wallet, WalletTransaction

from adminpanel.services.offers import (
    build_cart_offer_summary,
)



def validate_checkout_address(data):
    name = data.get("name", "").strip()
    phone_number = data.get("phone_number", "").strip()
    address_line_1 = data.get("address_line_1", "").strip()
    address_line_2 = data.get("address_line_2", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()
    pincode = data.get("pincode", "").strip()
    address_type = data.get("address_type", "HOME").strip().upper()


    if not name:
        return False, "Full name is required."

    if len(name) < 2 or len(name) > 60:
        return False, "Full name must be between 2 and 60 characters."


    if not re.fullmatch(r"[A-Za-z][A-Za-z\s.'-]*", name):
        return False, (
            "Full name must contain only letters, spaces, dots,"
        )

    if not re.search(r"[A-Za-z]", name):
        return False, "Full name must contain letters."

    if "  " in name:
        return False, "Full name cannot contain multiple consecutive spaces."


    if not phone_number:
        return False, "Phone number is required."

    if not phone_number.isdigit():
        return False, "Phone number must contain only digits."

    if len(phone_number) != 10:
        return False, "Phone number must be exactly 10 digits."


    if len(set(phone_number)) == 1:
        return False, "Please enter a valid phone number."


    if not address_line_1:
        return False, "Address Line 1 is required."

    if len(address_line_1) < 5 or len(address_line_1) > 150:
        return False, (
            "Address Line 1 must be between 5 and 150 characters."
        )

    if not re.search(r"[A-Za-z]", address_line_1):
        return False, "Address Line 1 must contain letters."

    if not re.fullmatch(
        r"[A-Za-z0-9\s,./#()&'-]+",
        address_line_1
    ):
        return False, (
            "Address Line 1 contains invalid characters."
        )


    if address_line_2:
        if len(address_line_2) > 150:
            return False, (
                "Address Line 2 cannot exceed 150 characters."
            )

        if not re.fullmatch(
            r"[A-Za-z0-9\s,./#()&'-]+",
            address_line_2
        ):
            return False, (
                "Address Line 2 contains invalid characters."
            )


    if not city:
        return False, "City is required."

    if len(city) < 2 or len(city) > 50:
        return False, "City must be between 2 and 50 characters."


    if not re.fullmatch(r"[A-Za-z][A-Za-z\s.'-]*", city):
        return False, (
            "City must contain only letters, spaces, dots, "
            "apostrophes or hyphens."
        )


    if not state:
        return False, "State is required."

    if len(state) < 2 or len(state) > 50:
        return False, "State must be between 2 and 50 characters."

    if not re.fullmatch(r"[A-Za-z][A-Za-z\s.'-]*", state):
        return False, (
            "State must contain only letters, spaces, dots, "
            "apostrophes or hyphens."
        )


    if not pincode:
        return False, "Pincode is required."

    if not pincode.isdigit():
        return False, "Pincode must contain only digits."

    if not re.fullmatch(r"[1-9]\d{5}", pincode):
        return False, (
            "Please enter a valid 6-digit Indian pincode."
        )


    allowed_address_types = {"HOME", "WORK", "OTHER"}

    if address_type not in allowed_address_types:
        return False, "Please select a valid address type."

    return True, ""


@login_required
@require_POST
def checkout_add_address(request):
    is_valid, error_message = validate_checkout_address(
        request.POST
    )

    if not is_valid:
        return JsonResponse(
            {
                "success": False,
                "message": error_message,
            },
            status=400,
        )

    name = request.POST.get("name", "").strip()
    phone_number = request.POST.get(
        "phone_number",
        "",
    ).strip()
    address_line_1 = request.POST.get(
        "address_line_1",
        "",
    ).strip()
    address_line_2 = request.POST.get(
        "address_line_2",
        "",
    ).strip()
    city = request.POST.get("city", "").strip()
    state = request.POST.get("state", "").strip()
    pincode = request.POST.get("pincode", "").strip()
    address_type = request.POST.get(
        "address_type",
        "HOME",
    ).strip().upper()

    is_default = request.POST.get("is_default") == "on"

    user_has_address = Address.objects.filter(
        user=request.user
    ).exists()

    if not user_has_address:
        is_default = True

    if is_default:
        Address.objects.filter(
            user=request.user,
            is_default=True,
        ).update(is_default=False)

    address = Address.objects.create(
        user=request.user,
        name=name,
        phone_number=phone_number,
        address_line_1=address_line_1,
        address_line_2=address_line_2,
        city=city,
        state=state,
        pincode=pincode,
        country="INDIA",
        address_type=address_type,
        is_default=is_default,
    )

    return JsonResponse(
        {
            "success": True,
            "message": "Address added successfully.",
            "address": {
                "id": address.id,
                "name": address.name,
                "phone_number": address.phone_number,
                "address_line_1": address.address_line_1,
                "address_line_2": (
                    address.address_line_2 or ""
                ),
                "city": address.city,
                "state": address.state,
                "pincode": address.pincode,
                "country": address.country,
                "address_type": address.address_type,
                "is_default": address.is_default,
            },
        },
        status=201,
    )

@login_required
def checkout(request):
    cart_items = list(
        Cart.objects.filter(
            user=request.user,
            variant__is_active=True,
            variant__is_deleted=False
        )
        .select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        )
        .prefetch_related(
            "variant__images"
        )
    )

    if not cart_items:
        messages.error(
            request,
            "Your cart is empty."
        )
        return redirect("cart")

    # Calculate product/category offers
    offer_summary = build_cart_offer_summary(
        cart_items
    )

    original_subtotal = (
        offer_summary["original_subtotal"]
    )

    offer_discount = (
        offer_summary["offer_discount"]
    )

    subtotal_after_offer = (
        offer_summary["subtotal_after_offer"]
    )

    # Attach offer data to each cart item
    for line in offer_summary["lines"]:
        cart_item = line["cart_item"]
        cart_item.offer_data = line

    shipping = (
        Decimal("80.00")
        if subtotal_after_offer > 0
        else Decimal("0.00")
    )

    coupon_discount = Decimal("0.00")
    applied_coupon = None

    coupon_code = request.session.get(
        "applied_coupon_code"
    )

    if coupon_code:
        today = timezone.localdate()

        applied_coupon = Coupon.objects.filter(
            code=coupon_code,
            is_active=True,
            is_deleted=False,
            valid_from__lte=today,
            valid_till__gte=today,
        ).first()

        if applied_coupon:
            usage_available = (
                applied_coupon.usage_limit == 0
                or
                applied_coupon.used_count
                < applied_coupon.usage_limit
            )

            if usage_available:
                # Coupon is applied after offer discount
                coupon_discount = (
                    calculate_coupon_discount(
                        applied_coupon,
                        subtotal_after_offer,
                    )
                )
            else:
                request.session.pop(
                    "applied_coupon_code",
                    None
                )
                applied_coupon = None

        else:
            request.session.pop(
                "applied_coupon_code",
                None
            )

    total_discount = (
        offer_discount
        + coupon_discount
    )

    grand_total = (
        original_subtotal
        - offer_discount
        - coupon_discount
        + shipping
    )

    if grand_total < 0:
        grand_total = Decimal("0.00")

    addresses = Address.objects.filter(
        user=request.user
    ).order_by(
        "-is_default",
        "-created_at"
    )

    today = timezone.localdate()

    available_coupons = Coupon.objects.filter(
        is_active=True,
        is_deleted=False,
        valid_from__lte=today,
        valid_till__gte=today,
    ).order_by("-created_at")

    wallet, created = Wallet.objects.get_or_create(
        user=request.user
    )

    context = {
        "cart_items": cart_items,
        "addresses": addresses,
        "wallet": wallet,

        "subtotal": original_subtotal,
        "offer_discount": offer_discount,
        "subtotal_after_offer": subtotal_after_offer,
        "coupon_discount": coupon_discount,
        "discount": total_discount,

        "shipping": shipping,
        "grand_total": grand_total,

        "cart_count": len(cart_items),
        "available_coupons": available_coupons,
        "applied_coupon": applied_coupon,
    }

    return render(
        request,
        "orders/checkout.html",
        context
    )
@login_required
@require_POST
def apply_coupon(request):
    code = request.POST.get(
        "coupon_code",
        ""
    ).strip().upper()

    if not code:
        messages.error(
            request,
            "Please enter a coupon code."
        )
        return redirect("checkout")

    cart_items = list(
        Cart.objects.filter(
            user=request.user,
            variant__is_active=True,
            variant__is_deleted=False
        )
        .select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        )
    )

    if not cart_items:
        messages.error(
            request,
            "Your cart is empty."
        )
        return redirect("cart")

    offer_summary = build_cart_offer_summary(
        cart_items
    )

    subtotal_after_offer = (
        offer_summary["subtotal_after_offer"]
    )

    today = timezone.localdate()

    coupon = Coupon.objects.filter(
        code=code,
        is_active=True,
        is_deleted=False,
        valid_from__lte=today,
        valid_till__gte=today,
    ).first()

    if not coupon:
        messages.error(
            request,
            "Invalid or expired coupon."
        )
        return redirect("checkout")

    if (
        coupon.usage_limit > 0
        and coupon.used_count >= coupon.usage_limit
    ):
        messages.error(
            request,
            "Coupon usage limit reached."
        )
        return redirect("checkout")

    if subtotal_after_offer < coupon.min_cart_amount:
        messages.error(
            request,
            (
                f"Minimum amount "
                f"₹{coupon.min_cart_amount} "
                f"is required after offer discount."
            )
        )
        return redirect("checkout")

    request.session[
        "applied_coupon_code"
    ] = coupon.code

    messages.success(
        request,
        f"Coupon {coupon.code} applied successfully."
    )

    return redirect("checkout")


def calculate_coupon_discount(coupon, subtotal):
    if subtotal < coupon.min_cart_amount:
        return Decimal("0.00")

    if coupon.discount_type == "PERCENTAGE":
        discount = (subtotal * coupon.discount_value) / Decimal("100")
        if coupon.max_discount_amount > 0:
            discount = min(discount, coupon.max_discount_amount)
        return discount.quantize(Decimal("0.01"))

    return min(coupon.discount_value, subtotal).quantize(Decimal("0.01"))

@login_required
def remove_coupon(request):
    request.session.pop("applied_coupon_code", None)
    messages.success(request, "Coupon removed successfully.")
    return redirect("checkout")

@login_required
@require_POST
@transaction.atomic
def place_order(request):
    cart_items = list(
        Cart.objects.filter(
            user=request.user,
            variant__is_active=True,
            variant__is_deleted=False,
        ).select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        )
    )

    if not cart_items:
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    selected_address_id = request.POST.get("selected_address", "").strip()
    payment_method = request.POST.get("payment_method", "COD").strip().upper()

    # UPI is intentionally removed as a separate option. Razorpay itself
    # already supports UPI, cards, netbanking and other enabled methods.
    if payment_method not in {"COD", "WALLET", "RAZORPAY"}:
        messages.error(request, "Invalid payment method.")
        return redirect("checkout")

    if not selected_address_id:
        messages.error(request, "Please select a delivery address.")
        return redirect("checkout")

    selected_address = get_object_or_404(
        Address,
        id=selected_address_id,
        user=request.user,
    )

    phone = (selected_address.phone_number or "").strip()
    postal_code = (selected_address.pincode or "").strip()

    if not re.fullmatch(r"[6-9]\d{9}", phone):
        messages.error(request, "Selected address has an invalid phone number.")
        return redirect("checkout")

    if not re.fullmatch(r"[1-9]\d{5}", postal_code):
        messages.error(request, "Selected address has an invalid pincode.")
        return redirect("checkout")

    locked_cart_items = []

    for cart_item in cart_items:
        variant = (
            ProductVariant.objects
            .select_for_update()
            .select_related("product", "product__category")
            .get(id=cart_item.variant_id)
        )

        if not variant.is_active or variant.is_deleted:
            messages.error(
                request,
                f"{variant.product.name} is no longer available.",
            )
            return redirect("cart")

        if cart_item.quantity > variant.stock:
            messages.error(
                request,
                f"Only {variant.stock} unit(s) available for {variant.product.name}.",
            )
            return redirect("cart")

        cart_item.variant = variant
        locked_cart_items.append(cart_item)

    offer_summary = build_cart_offer_summary(locked_cart_items)

    original_subtotal = offer_summary["original_subtotal"]
    offer_discount = offer_summary["offer_discount"]
    subtotal_after_offer = offer_summary["subtotal_after_offer"]

    coupon_discount = Decimal("0.00")
    applied_coupon = None
    coupon_code = request.session.get("applied_coupon_code")

    if coupon_code:
        today = timezone.localdate()

        applied_coupon = (
            Coupon.objects
            .select_for_update()
            .filter(
                code=coupon_code,
                is_active=True,
                is_deleted=False,
                valid_from__lte=today,
                valid_till__gte=today,
            )
            .first()
        )

        if not applied_coupon:
            request.session.pop("applied_coupon_code", None)
            messages.error(request, "Applied coupon is invalid or expired.")
            return redirect("checkout")

        if (
            applied_coupon.usage_limit > 0
            and applied_coupon.used_count >= applied_coupon.usage_limit
        ):
            request.session.pop("applied_coupon_code", None)
            messages.error(request, "Coupon usage limit reached.")
            return redirect("checkout")

        if subtotal_after_offer < applied_coupon.min_cart_amount:
            messages.error(
                request,
                f"Minimum amount ₹{applied_coupon.min_cart_amount} is required after offer discount.",
            )
            return redirect("checkout")

        coupon_discount = calculate_coupon_discount(
            applied_coupon,
            subtotal_after_offer,
        )

    shipping_fee = (
        Decimal("80.00")
        if subtotal_after_offer > 0
        else Decimal("0.00")
    )

    total_discount = offer_discount + coupon_discount

    grand_total = (
        original_subtotal
        - offer_discount
        - coupon_discount
        + shipping_fee
    )
    grand_total = max(
        grand_total.quantize(Decimal("0.01")),
        Decimal("0.00"),
    )

    address_str = selected_address.address_line_1
    if selected_address.address_line_2:
        address_str += f", {selected_address.address_line_2}"

    # Remove abandoned drafts belonging to this user. They were never paid,
    # never reduced stock and never consumed a coupon.
    Order.objects.filter(
        user=request.user,
        status="PAYMENT_PENDING",
    ).delete()

    order = Order.objects.create(
        user=request.user,
        subtotal=original_subtotal,
        offer_discount=offer_discount,
        coupon_discount=coupon_discount,
        discount_amount=total_discount,
        shipping_fee=shipping_fee,
        total_amount=grand_total,
        payment_method=payment_method,
        status="PAYMENT_PENDING",
        coupon_code=applied_coupon.code if applied_coupon else None,
    )

    OrderAddress.objects.create(
        order=order,
        full_name=selected_address.name,
        email=request.user.email,
        phone=phone,
        address=address_str,
        city=selected_address.city,
        state=selected_address.state,
        postal_code=postal_code,
    )

    for line in offer_summary["lines"]:
        variant = line["variant"]
        cart_item = line["cart_item"]

        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            product_name=variant.product.name,
            variant_color=variant.color,
            variant_size=variant.size,
            original_price=line["original_unit_price"],
            offer_price=line["final_unit_price"],
            offer_discount=line["unit_offer_discount"],
            offer_name=line["offer_title"] or None,
            offer_type=line["offer_type"] or None,
            price=line["final_unit_price"],
            quantity=cart_item.quantity,
            item_total=line["final_line_total"],
        )

    # Do not increment coupon usage and do not clear the coupon session here.
    # Both happen only after the order is successfully confirmed.
    return redirect("payment", order_id=order.id)

@login_required
def payment_view(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items",
            "items__variant",
            "items__variant__images",
        ),
        id=order_id,
        user=request.user,
    )

    if order.status == "CONFIRMED":
        return redirect("order_success", order_id=order.id)

    if order.status != "PAYMENT_PENDING":
        messages.error(request, "This payment session is no longer available.")
        return redirect("checkout")

    address = OrderAddress.objects.filter(order=order).first()
    wallet, _ = Wallet.objects.get_or_create(user=request.user)

    subtotal_after_offer = order.subtotal - order.offer_discount
    total_savings = order.offer_discount + order.coupon_discount

    razorpay_amount = int(order.total_amount * Decimal("100"))
    razorpay_order_id = None

    if order.payment_method == "RAZORPAY":
        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

        if not order.razorpay_order_id:
            try:
                razorpay_order = client.order.create({
                    "amount": razorpay_amount,
                    "currency": "INR",
                    "payment_capture": 1,
                    "notes": {
                        "order_id": order.order_id,
                        "user_id": str(request.user.id),
                    },
                })
            except Exception:
                messages.error(
                    request,
                    "Unable to start Razorpay. Please try again.",
                )
                return redirect("checkout")

            order.razorpay_order_id = razorpay_order["id"]
            order.save(update_fields=["razorpay_order_id", "updated_at"])

        razorpay_order_id = order.razorpay_order_id

    return render(
        request,
        "orders/payment.html",
        {
            "order": order,
            "address": address,
            "wallet": wallet,
            "subtotal": order.subtotal,
            "offer_discount": order.offer_discount,
            "subtotal_after_offer": subtotal_after_offer,
            "coupon_discount": order.coupon_discount,
            "total_savings": total_savings,
            "shipping": order.shipping_fee,
            "grand_total": order.total_amount,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "razorpay_amount": razorpay_amount,
            "razorpay_order_id": razorpay_order_id,
        },
    )

def confirm_order_after_payment(order):
    """
    Finalize an order only after COD confirmation, successful wallet debit,
    or verified Razorpay payment.

    Stock, coupon usage and cart clearing happen exactly once here.
    """
    if order.status == "CONFIRMED":
        return True, "Already confirmed."

    if order.status != "PAYMENT_PENDING":
        return False, "Order cannot be confirmed."

    order_items = list(
        order.items.select_related("variant", "variant__product")
    )
    updated_product_ids = set()
    locked_variants = {}

    for order_item in order_items:
        if not order_item.variant_id:
            return False, f"Variant unavailable for {order_item.product_name}."

        variant = (
            ProductVariant.objects
            .select_for_update()
            .select_related("product")
            .get(id=order_item.variant_id)
        )

        if not variant.is_active or variant.is_deleted:
            return False, f"{order_item.product_name} is no longer available."

        if order_item.quantity > variant.stock:
            return False, (
                f"Only {variant.stock} unit(s) left for "
                f"{order_item.product_name}."
            )

        locked_variants[order_item.id] = variant

    # Validate and lock coupon before changing stock.
    coupon = None
    if order.coupon_code:
        today = timezone.localdate()
        coupon = (
            Coupon.objects
            .select_for_update()
            .filter(
                code=order.coupon_code,
                is_active=True,
                is_deleted=False,
                valid_from__lte=today,
                valid_till__gte=today,
            )
            .first()
        )

        if not coupon:
            return False, "The applied coupon is no longer valid."

        if coupon.usage_limit > 0 and coupon.used_count >= coupon.usage_limit:
            return False, "Coupon usage limit reached."

    for order_item in order_items:
        variant = locked_variants[order_item.id]
        variant.stock -= order_item.quantity
        variant.save(update_fields=["stock"])
        updated_product_ids.add(variant.product_id)

    if coupon:
        usage, created = CouponUsage.objects.get_or_create(
            user=order.user,
            coupon=coupon,
            order=order,
        )
        if created:
            coupon.used_count += 1
            coupon.save(update_fields=["used_count"])

    order.status = "CONFIRMED"
    order.save(update_fields=["status", "updated_at"])

    # Clear only variants included in this order, not unrelated cart rows.
    ordered_variant_ids = [
        item.variant_id for item in order_items if item.variant_id
    ]
    Cart.objects.filter(
        user=order.user,
        variant_id__in=ordered_variant_ids,
    ).delete()

    def sync_stock():
        for product_id in updated_product_ids:
            product = AdminProduct.objects.get(id=product_id)
            total_stock = product.variants.filter(
                is_deleted=False,
            ).aggregate(total=Sum("stock"))["total"] or 0
            product.total_stock = total_stock
            product.save(update_fields=["total_stock"])

    transaction.on_commit(sync_stock)
    return True, "Order confirmed."


@login_required
@require_POST
@transaction.atomic
def confirm_payment(request, order_id):
    order = get_object_or_404(
        Order.objects.select_for_update(),
        id=order_id,
        user=request.user
    )

    payment_method = request.POST.get("payment_method", "").strip().upper()

    if payment_method != order.payment_method:
        messages.error(request, "Payment method mismatch.")
        return redirect("payment", order_id=order.id)

    if payment_method == "COD":
        success, msg = confirm_order_after_payment(order)

        if not success:
            messages.error(request, msg)
            return redirect("order_failed_with_order", order_id=order.id)

        order.payment_method = "COD"
        order.save(update_fields=["payment_method", "updated_at"])

        if request.session.get("applied_coupon_code") == order.coupon_code:
            request.session.pop("applied_coupon_code", None)

        messages.success(request, "COD order placed successfully.")
        return redirect("order_success", order_id=order.id)

    if payment_method == "WALLET":
        wallet = Wallet.objects.select_for_update().get(user=request.user)

        if wallet.balance < order.total_amount:
            messages.error(request, "Insufficient wallet balance.")
            return redirect("payment", order_id=order.id)

        success, msg = confirm_order_after_payment(order)

        if not success:
            messages.error(request, msg)
            return redirect("order_failed_with_order", order_id=order.id)

        wallet.balance -= order.total_amount
        wallet.save(update_fields=["balance", "updated_at"])

        WalletTransaction.objects.create(
            wallet=wallet,
            order=order,
            transaction_type="DEBIT",
            purpose="WALLET_PAYMENT",
            payment_method="WALLET",
            amount=order.total_amount,
            status="COMPLETED",
            description=f"Wallet payment for order {order.order_id}",
            reference=f"WALLET_ORDER_{order.id}",
        )

        order.payment_method = "WALLET"
        order.save(update_fields=["payment_method", "updated_at"])

        if request.session.get("applied_coupon_code") == order.coupon_code:
            request.session.pop("applied_coupon_code", None)

        messages.success(request, "Order paid using wallet successfully.")
        return redirect("order_success", order_id=order.id)

    messages.error(request, "Invalid payment method.")
    return redirect("payment", order_id=order.id)


@login_required
@require_POST
@transaction.atomic
def verify_razorpay_payment(request, order_id):
    order = get_object_or_404(
        Order.objects.select_for_update(),
        id=order_id,
        user=request.user,
        payment_method="RAZORPAY",
    )

    if order.status == "CONFIRMED":
        return redirect("order_success", order_id=order.id)

    if order.status != "PAYMENT_PENDING":
        messages.error(request, "This payment session is no longer active.")
        return redirect("checkout")

    razorpay_payment_id = request.POST.get("razorpay_payment_id", "").strip()
    razorpay_order_id = request.POST.get("razorpay_order_id", "").strip()
    razorpay_signature = request.POST.get("razorpay_signature", "").strip()

    if not all([
        razorpay_payment_id,
        razorpay_order_id,
        razorpay_signature,
    ]):
        messages.error(request, "Incomplete Razorpay payment response.")
        return redirect("payment", order_id=order.id)

    if razorpay_order_id != order.razorpay_order_id:
        messages.error(request, "Razorpay order ID mismatch.")
        return redirect("payment", order_id=order.id)

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except razorpay.errors.SignatureVerificationError:
        messages.error(request, "Payment verification failed.")
        return redirect("payment", order_id=order.id)
    except Exception:
        messages.error(request, "Unable to verify payment. Please try again.")
        return redirect("payment", order_id=order.id)

    success, message = confirm_order_after_payment(order)
    if not success:
        messages.error(request, message)
        return redirect("payment", order_id=order.id)

    order.razorpay_payment_id = razorpay_payment_id
    order.razorpay_signature = razorpay_signature
    order.save(update_fields=[
        "razorpay_payment_id",
        "razorpay_signature",
        "updated_at",
    ])

    if request.session.get("applied_coupon_code") == order.coupon_code:
        request.session.pop("applied_coupon_code", None)

    messages.success(request, "Online payment successful.")
    return redirect("order_success", order_id=order.id)

@login_required
def order_success(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items",
            "items__variant",
            "items__variant__images"
        ),
        id=order_id,
        user=request.user,
        status="CONFIRMED",
    )

    return render(request, "orders/order_success.html", {
        "order": order
    })
    
    
@login_required
def order_failed(request, order_id=None):
    order = None
    if order_id:
        order = Order.objects.filter(
            id=order_id,
            user=request.user
        ).first()
    return render(request, "orders/order_failed.html", {
        "order": order
    })
    



@login_required
def my_orders(request):
    status_filter = request.GET.get("status", "all")
    search_query = request.GET.get("search", "").strip()

    visible_orders = Order.objects.filter(
        user=request.user,
    ).exclude(
        status="PAYMENT_PENDING",
    )

    orders = visible_orders.prefetch_related(
        "items",
        "items__variant",
        "items__variant__images",
    ).order_by("-ordered_at")

    allowed_filters = {
        "all",
        "PENDING",
        "CONFIRMED",
        "SHIPPED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
        "CANCELLED",
        "RETURN_REQUESTED",
        "RETURN_APPROVED",
        "RETURN_REJECTED",
        "RETURNED",
    }

    if status_filter not in allowed_filters:
        status_filter = "all"

    if status_filter != "all":
        orders = orders.filter(status=status_filter)

    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query)
            | Q(items__product_name__icontains=search_query)
        ).distinct()

    paginator = Paginator(orders, 5)
    page_obj = paginator.get_page(request.GET.get("page"))

    counts = {
        "all": visible_orders.count(),
        "pending": visible_orders.filter(status="PENDING").count(),
        "confirmed": visible_orders.filter(status="CONFIRMED").count(),
        "shipped": visible_orders.filter(status="SHIPPED").count(),
        "delivered": visible_orders.filter(status="DELIVERED").count(),
        "returned": visible_orders.filter(status="RETURNED").count(),
    }

    return render(
        request,
        "orders/my_orders.html",
        {
            "page_obj": page_obj,
            "orders": page_obj.object_list,
            "status_filter": status_filter,
            "search_query": search_query,
            "counts": counts,
        },
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items",
            "items__variant",
            "items__variant__images"
        ),
        id=order_id,
        user=request.user,
    )

    if order.status == "PAYMENT_PENDING":
        messages.info(request, "Complete payment before viewing order details.")
        return redirect("payment", order_id=order.id)

    address = OrderAddress.objects.filter(order=order).first()

    first_item = order.items.first()

    status_steps = [
        "PENDING",
        "CONFIRMED",
        "SHIPPED",
        "DELIVERED",
    ]

    try:
        current_step = status_steps.index(order.status)
    except ValueError:
        current_step = 0

    progress_percent = {
        "PENDING": 15,
        "CONFIRMED": 35,
        "SHIPPED": 70,
        "DELIVERED": 100,
        "CANCELLED": 0,
        "RETURN_REQUESTED": 100,
        "RETURNED": 100,
    }.get(order.status, 15)

    has_cancelled_item = order.items.filter(
        cancelled_quantity__gt=0
    ).exists()

    cancelled_item = order.items.filter(
        cancelled_quantity__gt=0
    ).first()

    # Attach database-backed item offer totals for the template.
    # The queryset is already prefetched, so these attributes are available
    # when the template loops through order.items.all.
    for item in order.items.all():
        active_quantity = max(
            item.quantity - item.cancelled_quantity,
            0,
        )

        item.active_offer_discount_total = (
            item.offer_discount * active_quantity
        ).quantize(Decimal("0.01"))

    subtotal_after_offer = max(
        order.subtotal - order.offer_discount,
        Decimal("0.00"),
    )

    total_savings = (
        order.offer_discount
        + order.coupon_discount
    )

    return render(request, "orders/order_detail.html", {
        "order": order,
        "address": address,
        "first_item": first_item,
        "current_step": current_step,
        "progress_percent": progress_percent,
        "has_cancelled_item": has_cancelled_item,
        "cancelled_item": cancelled_item,
        "subtotal_after_offer": subtotal_after_offer,
        "total_savings": total_savings,
    })

def refund_to_wallet_for_cancel(order, amount, reference_suffix):
    if amount <= 0:
        return False

    # COD no refund because user did not pay yet
    if order.payment_method == "COD":
        return False

    reference = f"CANCEL_REFUND_{reference_suffix}"

    if WalletTransaction.objects.filter(reference=reference).exists():
        return False

    wallet, created = Wallet.objects.select_for_update().get_or_create(
        user=order.user
    )

    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        transaction_type="CREDIT",
        purpose="CANCEL_REFUND",
        payment_method=order.payment_method,
        amount=amount,
        status="COMPLETED",
        description=f"Cancel refund for order {order.order_id}",
        reference=reference,
    )

    return True


@login_required
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(
        Order.objects.select_for_update().select_related("user").prefetch_related(
            "items",
            "items__variant",
            "items__variant__product"
        ),
        id=order_id,
        user=request.user
    )

    if order.status in ["DELIVERED", "CANCELLED", "RETURNED", "RETURN_REQUESTED"]:
        messages.error(request, "This order cannot be cancelled.")
        return redirect("order_detail", order_id=order.id)

    if request.method == "POST":
        reason = request.POST.get("cancel_reason", "").strip()
        comments = request.POST.get("comments", "").strip()

        if not reason:
            messages.error(request, "Please select a cancellation reason.")
            return redirect("cancel_order", order_id=order.id)

        final_reason = f"{reason}\n\n{comments}" if comments else reason

        product_ids_to_sync = set()

        stock_should_restore = order.status in [
            "CONFIRMED",
            "SHIPPED",
            "OUT_FOR_DELIVERY",
        ]

        for item in order.items.filter(is_cancelled=False):
            if stock_should_restore and item.variant:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=["stock"])
                product_ids_to_sync.add(item.variant.product.id)

            item.is_cancelled = True
            item.cancel_reason = final_reason
            item.save(update_fields=["is_cancelled", "cancel_reason"])

        refund_done = False

        if order.payment_method != "COD" and order.status in [
            "CONFIRMED",
            "SHIPPED",
            "OUT_FOR_DELIVERY",
        ]:
            refund_done = refund_to_wallet_for_cancel(
                order=order,
                amount=order.total_amount,
                reference_suffix=f"ORDER_{order.id}"
            )
        order.status = "CANCELLED"
        order.cancel_reason = final_reason
        order.save(update_fields=["status", "cancel_reason", "updated_at"])

        def sync_stock(pids=product_ids_to_sync):
            for pid in pids:
                product = AdminProduct.objects.get(id=pid)
                total = product.variants.filter(
                    is_deleted=False,
                    is_active=True
                ).aggregate(total=Sum("stock"))["total"] or 0

                product.total_stock = total
                product.save(update_fields=["total_stock"])

        transaction.on_commit(sync_stock)

        if refund_done:
            messages.success(request, "Item cancelled and amount refunded to wallet.")
        else:
            messages.success(request, "Item cancelled successfully.")

        return redirect("order_detail", order_id=order.id)

    return render(request, "orders/cancel_order.html", {
        "order": order,
        "first_item": order.items.filter(is_cancelled=False).first(),
    })
    
    
@login_required
@transaction.atomic
def cancel_order_item(request, item_id):
    """
    Cancel a selected quantity from one order item.

    Business rules:
    - Only one cancellation action is allowed for the entire order.
    - The customer may choose a quantity from 1 up to item.quantity.
    - Stock is restored only for the selected quantity.
    - Prepaid refund is calculated from the reduction in the order total.
    - Original item quantity and item_total remain unchanged for history.
    """

    # Lock only the OrderItem row. Do not join nullable variant with
    # select_for_update(), because PostgreSQL rejects FOR UPDATE on the
    # nullable side of an outer join.
    locked_item = get_object_or_404(
        OrderItem.objects.select_for_update(),
        id=item_id,
        order__user=request.user,
    )

    order = get_object_or_404(
        Order.objects.select_for_update(),
        id=locked_item.order_id,
        user=request.user,
    )

    order_item = (
        OrderItem.objects
        .select_related(
            "order",
            "order__user",
            "variant",
            "variant__product",
        )
        .prefetch_related("variant__images")
        .get(id=locked_item.id)
    )

    allowed_statuses = {
        "PENDING",
        "CONFIRMED",
        "SHIPPED",
        "OUT_FOR_DELIVERY",
    }

    if order.status not in allowed_statuses:
        messages.error(
            request,
            "This item cannot be cancelled at the current order stage.",
        )
        return redirect("order_detail", order_id=order.id)

    # Only one cancellation action is allowed for the complete order.
    already_cancelled_item = (
        order.items
        .select_for_update()
        .filter(cancelled_quantity__gt=0)
        .first()
    )

    if already_cancelled_item:
        messages.error(
            request,
            (
                "Only one cancellation is allowed for an order. "
                f"{already_cancelled_item.product_name} already has "
                f"{already_cancelled_item.cancelled_quantity} cancelled "
                "quantity."
            ),
        )
        return redirect("order_detail", order_id=order.id)

    if request.method == "GET":
        return render(
            request,
            "orders/cancel_item.html",
            {
                "order": order,
                "item": order_item,
                "first_item": order_item,
                "available_cancel_quantity": order_item.quantity,
            },
        )

    if request.method != "POST":
        messages.error(request, "Invalid cancellation request.")
        return redirect("order_detail", order_id=order.id)

    reason = request.POST.get("cancel_reason", "").strip()
    comments = request.POST.get("comments", "").strip()

    try:
        cancel_quantity = int(
            request.POST.get("cancel_quantity", "0")
        )
    except (TypeError, ValueError):
        cancel_quantity = 0

    allowed_reasons = {
        "Ordered by Mistake",
        "Found Another Collectible",
        "Financial Reasons",
        "Shipping Delay Concerns",
        "Other",
    }

    if reason not in allowed_reasons:
        messages.error(
            request,
            "Please select a valid cancellation reason.",
        )
        return redirect(
            "cancel_order_item",
            item_id=order_item.id,
        )

    if cancel_quantity < 1:
        messages.error(
            request,
            "Please select at least one quantity to cancel.",
        )
        return redirect(
            "cancel_order_item",
            item_id=order_item.id,
        )

    if cancel_quantity > order_item.quantity:
        messages.error(
            request,
            (
                f"You can cancel a maximum of "
                f"{order_item.quantity} unit(s)."
            ),
        )
        return redirect(
            "cancel_order_item",
            item_id=order_item.id,
        )

    if comments and len(comments) > 500:
        messages.error(
            request,
            "Additional comments cannot exceed 500 characters.",
        )
        return redirect(
            "cancel_order_item",
            item_id=order_item.id,
        )

    final_reason = (
        f"{reason}\n\nAdditional comments: {comments}"
        if comments
        else reason
    )

    old_total_amount = order.total_amount
    old_subtotal_after_offer = max(
        order.subtotal - order.offer_discount,
        Decimal("0.00"),
    )

    product_id_to_sync = None

    if order_item.variant_id:
        variant = (
            ProductVariant.objects
            .select_for_update()
            .select_related("product")
            .get(id=order_item.variant_id)
        )

        variant.stock += cancel_quantity
        variant.save(update_fields=["stock"])
        product_id_to_sync = variant.product_id

    order_item.cancelled_quantity = cancel_quantity
    order_item.is_cancelled = (
        cancel_quantity >= order_item.quantity
    )
    order_item.cancel_reason = final_reason
    order_item.save(
        update_fields=[
            "cancelled_quantity",
            "is_cancelled",
            "cancel_reason",
        ]
    )

    all_items = list(
        order.items
        .select_for_update()
        .all()
    )

    remaining_original_subtotal = Decimal("0.00")
    remaining_offer_discount = Decimal("0.00")
    remaining_active_quantity = 0

    for item in all_items:
        active_quantity = max(
            item.quantity - item.cancelled_quantity,
            0,
        )

        remaining_active_quantity += active_quantity

        remaining_original_subtotal += (
            item.original_price * active_quantity
        )

        remaining_offer_discount += (
            item.offer_discount * active_quantity
        )

    remaining_subtotal_after_offer = max(
        remaining_original_subtotal
        - remaining_offer_discount,
        Decimal("0.00"),
    )

    # Reduce coupon discount proportionally to the remaining payable
    # product value. This prevents over-refunding or retaining the full
    # coupon discount after a partial cancellation.
    if (
        order.coupon_discount > 0
        and old_subtotal_after_offer > 0
        and remaining_subtotal_after_offer > 0
    ):
        coupon_ratio = (
            remaining_subtotal_after_offer
            / old_subtotal_after_offer
        )

        remaining_coupon_discount = (
            order.coupon_discount * coupon_ratio
        ).quantize(Decimal("0.01"))

        remaining_coupon_discount = min(
            remaining_coupon_discount,
            remaining_subtotal_after_offer,
        )
    else:
        remaining_coupon_discount = Decimal("0.00")

    remaining_shipping_fee = (
        order.shipping_fee
        if remaining_active_quantity > 0
        else Decimal("0.00")
    )

    remaining_discount_amount = (
        remaining_offer_discount
        + remaining_coupon_discount
    )

    remaining_total = (
        remaining_original_subtotal
        - remaining_offer_discount
        - remaining_coupon_discount
        + remaining_shipping_fee
    )

    order.subtotal = remaining_original_subtotal.quantize(
        Decimal("0.01")
    )
    order.offer_discount = remaining_offer_discount.quantize(
        Decimal("0.01")
    )
    order.coupon_discount = remaining_coupon_discount.quantize(
        Decimal("0.01")
    )
    order.discount_amount = remaining_discount_amount.quantize(
        Decimal("0.01")
    )
    order.shipping_fee = remaining_shipping_fee.quantize(
        Decimal("0.01")
    )
    order.total_amount = max(
        remaining_total.quantize(Decimal("0.01")),
        Decimal("0.00"),
    )

    if remaining_active_quantity == 0:
        order.status = "CANCELLED"
        order.cancel_reason = final_reason

    order_update_fields = [
        "subtotal",
        "offer_discount",
        "coupon_discount",
        "discount_amount",
        "shipping_fee",
        "total_amount",
        "updated_at",
    ]

    if remaining_active_quantity == 0:
        order_update_fields.extend([
            "status",
            "cancel_reason",
        ])

    order.save(update_fields=order_update_fields)

    refund_amount = max(
        old_total_amount - order.total_amount,
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    refund_done = False

    if order.payment_method != "COD" and refund_amount > 0:
        refund_done = refund_to_wallet_for_cancel(
            order=order,
            amount=refund_amount,
            reference_suffix=f"ITEM_{order_item.id}",
        )

    if product_id_to_sync:
        def sync_product_stock(product_id=product_id_to_sync):
            product = AdminProduct.objects.get(id=product_id)

            total_stock = (
                product.variants
                .filter(
                    is_deleted=False,
                    is_active=True,
                )
                .aggregate(total=Sum("stock"))["total"]
                or 0
            )

            product.total_stock = total_stock
            product.save(update_fields=["total_stock"])

        transaction.on_commit(sync_product_stock)

    if refund_done:
        messages.success(
            request,
            (
                f"{cancel_quantity} unit(s) cancelled successfully. "
                f"₹{refund_amount:.2f} was refunded to your wallet."
            ),
        )
    else:
        messages.success(
            request,
            f"{cancel_quantity} unit(s) cancelled successfully.",
        )

    return redirect("order_detail", order_id=order.id)




VALID_RETURN_REASONS = [
    "Damaged Product",
    "Wrong Product Received",
    "Product Quality Issue",
    "Missing Parts",
    "Other",
]

def refund_cancelled_order_to_wallet(order, amount):
    if amount <= 0:
        return False

    if order.payment_method == "COD":
        return False

    reference = f"CANCEL_REFUND_ORDER_{order.id}"

    if WalletTransaction.objects.filter(reference=reference).exists():
        return False

    wallet, created = Wallet.objects.select_for_update().get_or_create(
        user=order.user
    )

    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        transaction_type="CREDIT",
        purpose="CANCEL_REFUND",
        payment_method=order.payment_method,
        amount=amount,
        status="COMPLETED",
        description=f"Refund for cancelled order {order.order_id}",
        reference=reference,
    )

    return True

def get_item_returned_qty(order_item):
    if hasattr(order_item, "return_request"):
        if order_item.return_request.status != "REJECTED":
            return order_item.quantity
    return 0


def validate_return_images(images):
    if not images:
        return "Please upload at least one return proof image."

    if len(images) > 5:
        return "Maximum 5 images allowed."

    allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
    max_size = 5 * 1024 * 1024

    for image in images:
        if image.content_type not in allowed_types:
            return "Only JPG, PNG, and WEBP images are allowed."

        if image.size > max_size:
            return "Each image must be less than 5MB."

    return None


@login_required
@transaction.atomic
def return_order_item(request, item_id):
    order_item = get_object_or_404(
        OrderItem.objects.select_related(
            "order",
            "variant",
            "variant__product"
        ).prefetch_related(
            "variant__images"
        ),
        id=item_id,
        order__user=request.user
    )

    order = order_item.order

    if order.status != "DELIVERED":
        messages.error(request, "Only delivered items can be returned.")
        return redirect("order_detail", order.id)

    if order_item.is_cancelled:
        messages.error(request, "Cancelled item cannot be returned.")
        return redirect("order_detail", order.id)

    already_requested_qty = get_item_returned_qty(order_item)
    available_qty = order_item.quantity - already_requested_qty

    if available_qty <= 0:
        messages.info(request, "Return request already submitted for full quantity.")
        return redirect("order_detail", order.id)

    if request.method == "POST":
        reason = request.POST.get("return_reason", "").strip()
        comments = request.POST.get("comments", "").strip()
        images = request.FILES.getlist("return_images")

        try:
            return_quantity = int(request.POST.get("return_quantity", 0))
        except ValueError:
            return_quantity = 0

        if reason not in VALID_RETURN_REASONS:
            messages.error(request, "Please select a valid return reason.")
            return redirect("return_order_item", item_id=item_id)

        if not comments or len(comments) < 15:
            messages.error(request, "Please enter a detailed description with at least 15 characters.")
            return redirect("return_order_item", item_id=item_id)

        if return_quantity < 1:
            messages.error(request, "Please enter a valid return quantity.")
            return redirect("return_order_item", item_id=item_id)

        if return_quantity > available_qty:
            messages.error(request, f"You can return only {available_qty} quantity.")
            return redirect("return_order_item", item_id=item_id)

        image_error = validate_return_images(images)
        if image_error:
            messages.error(request, image_error)
            return redirect("return_order_item", item_id=item_id)

        final_reason = f"{reason}\n\nDescription: {comments}"

        unit_price = order_item.item_total / order_item.quantity
        refund_amount = unit_price * return_quantity

        request_obj = ReturnRequest.objects.create(
            order=order,
            order_item=order_item,
            user=request.user,
            return_quantity=return_quantity,
            reason=final_reason,
            refund_amount=refund_amount,
        )

        for image in images:
            ReturnRequestImage.objects.create(
                return_request=request_obj,
                image=image
            )

        order_item.return_requested_quantity = already_requested_qty + return_quantity

        if order_item.return_requested_quantity >= order_item.quantity:
            order_item.is_return_requested = True

        order_item.return_reason = final_reason
        order_item.save(update_fields=[
            "return_requested_quantity",
            "is_return_requested",
            "return_reason"
        ])

        available_after = order.items.filter(
            is_cancelled=False
        ).exclude(
            return_requested_quantity__gte=models.F("quantity")
        )

        if not available_after.exists():
            order.status = "RETURN_REQUESTED"
            order.return_reason = final_reason
            order.save(update_fields=["status", "return_reason", "updated_at"])

        messages.success(request, "Return request submitted successfully.")
        return redirect("order_detail", order.id)

    return render(request, "orders/return_order.html", {
        "mode": "item",
        "order": order,
        "item": order_item,
        "available_qty": available_qty,
        "already_requested_qty": already_requested_qty,
    })


@login_required
@transaction.atomic
def return_order(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items",
            "items__variant",
            "items__variant__images",
            "items__variant__product",
        ),
        id=order_id,
        user=request.user
    )

    if order.status != "DELIVERED":
        messages.error(request, "Only delivered orders can be returned.")
        return redirect("order_detail", order.id)

    available_items = []

    for item in order.items.filter(is_cancelled=False):
        already_requested_qty = get_item_returned_qty(item)
        available_qty = item.quantity - already_requested_qty

        if available_qty > 0:
            item.already_requested_qty = already_requested_qty
            item.available_qty = available_qty
            available_items.append(item)

    if not available_items:
        messages.info(request, "Return request already submitted for all items.")
        return redirect("order_detail", order.id)

    if request.method == "POST":
        reason = request.POST.get("return_reason", "").strip()
        comments = request.POST.get("comments", "").strip()
        images = request.FILES.getlist("return_images")

        if reason not in VALID_RETURN_REASONS:
            messages.error(request, "Please select a valid return reason.")
            return redirect("return_order", order.id)

        if not comments or len(comments) < 15:
            messages.error(request, "Please enter a detailed description with at least 15 characters.")
            return redirect("return_order", order.id)

        image_error = validate_return_images(images)
        if image_error:
            messages.error(request, image_error)
            return redirect("return_order", order.id)

        final_reason = f"{reason}\n\nDescription: {comments}"

        selected_any = False

        for item in available_items:
            try:
                return_quantity = int(request.POST.get(f"return_quantity_{item.id}", 0))
            except ValueError:
                return_quantity = 0

            if return_quantity <= 0:
                continue

            if return_quantity > item.available_qty:
                messages.error(request, f"{item.product_name}: You can return only {item.available_qty} quantity.")
                return redirect("return_order", order.id)

            selected_any = True

            unit_price = item.item_total / item.quantity
            refund_amount = unit_price * return_quantity

            request_obj = ReturnRequest.objects.create(
                order=order,
                order_item=item,
                user=request.user,
                return_quantity=return_quantity,
                reason=final_reason,
                refund_amount=refund_amount,
            )

            for image in images:
                ReturnRequestImage.objects.create(
                    return_request=request_obj,
                    image=image
                )

            item.return_requested_quantity = item.already_requested_qty + return_quantity

            if item.return_requested_quantity >= item.quantity:
                item.is_return_requested = True

            item.return_reason = final_reason
            item.save(update_fields=[
                "return_requested_quantity",
                "is_return_requested",
                "return_reason"
            ])

        if not selected_any:
            messages.error(request, "Please select at least one item quantity to return.")
            return redirect("return_order", order.id)

        all_items_returned = True

        for item in order.items.filter(is_cancelled=False):
            already_requested_qty = get_item_returned_qty(item)
            if already_requested_qty < item.quantity:
                all_items_returned = False
                break

        if all_items_returned:
            order.status = "RETURN_REQUESTED"
            order.return_reason = final_reason
            order.save(update_fields=["status", "return_reason", "updated_at"])

        messages.success(request, "Return request submitted successfully.")
        return redirect("order_detail", order.id)

    return render(request, "orders/return_order.html", {
        "mode": "order",
        "order": order,
        "items": available_items,
        "item": available_items[0],
    })
    
@login_required
def download_invoice(request, order_id):
    order = get_object_or_404(
        Order.objects
        .select_related("shipping_address")
        .prefetch_related("items"),
        id=order_id,
        user=request.user,
    )

    # Do not generate an invoice for an unpaid draft order.
    if order.status == "PAYMENT_PENDING":
        messages.error(
            request,
            "Invoice is available only after the order is confirmed.",
        )
        return redirect("payment", order_id=order.id)

    address = getattr(order, "shipping_address", None)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="invoice_{order.order_id}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "InvoiceTitle",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.HexColor("#d4af37"),
        spaceAfter=14,
    )

    heading_style = ParagraphStyle(
        "Heading",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#111111"),
        spaceAfter=8,
    )

    normal_style = ParagraphStyle(
        "NormalCustom",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )

    story = []

    story.append(Paragraph("WHEELVERSE INVOICE", title_style))
    story.append(Paragraph("Enter the Universe of Wheels", normal_style))
    story.append(Spacer(1, 12))

    invoice_info = [
        ["Invoice No", f"INV-{order.order_id}"],
        ["Order ID", order.order_id],
        ["Order Date", order.ordered_at.strftime("%d %b %Y")],
        ["Payment Method", order.get_payment_method_display()],
        ["Order Status", order.get_status_display()],
    ]

    invoice_table = Table(
        invoice_info,
        colWidths=[45 * mm, 110 * mm],
    )
    invoice_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2ca50")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#241a00")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(invoice_table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Billing / Delivery Address", heading_style))

    if address:
        address_text = (
            f"<b>{address.full_name}</b><br/>"
            f"{address.address}<br/>"
            f"{address.city}, {address.state} - {address.postal_code}<br/>"
            f"Phone: {address.phone}<br/>"
            f"Email: {address.email}"
        )
    else:
        address_text = "Address not available."

    story.append(Paragraph(address_text, normal_style))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Order Items", heading_style))

    item_data = [
        ["Product", "Variant", "Qty", "Unit Price", "Total"]
    ]

    for item in order.items.all():
        variant_parts = []

        if item.variant_color:
            variant_parts.append(item.variant_color)

        if item.variant_size:
            variant_parts.append(item.variant_size)

        variant_text = " / ".join(variant_parts) or "-"

        item_data.append([
            Paragraph(str(item.product_name), normal_style),
            Paragraph(variant_text, normal_style),
            str(item.quantity),
            f"Rs. {item.price:.2f}",
            f"Rs. {item.item_total:.2f}",
        ])

    item_table = Table(
        item_data,
        colWidths=[65 * mm, 35 * mm, 18 * mm, 28 * mm, 30 * mm],
        repeatRows=1,
    )

    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f2ca50")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))

    story.append(item_table)
    story.append(Spacer(1, 16))

    subtotal_after_offer = (
        order.subtotal - order.offer_discount
    )

    summary_data = [
        ["Original Subtotal", f"Rs. {order.subtotal:.2f}"],
        ["Offer Discount", f"- Rs. {order.offer_discount:.2f}"],
        ["Subtotal After Offer", f"Rs. {subtotal_after_offer:.2f}"],
        ["Coupon Discount", f"- Rs. {order.coupon_discount:.2f}"],
        ["Total Discount", f"- Rs. {order.discount_amount:.2f}"],
        ["Shipping Charge", f"Rs. {order.shipping_fee:.2f}"],
        ["Total Amount", f"Rs. {order.total_amount:.2f}"],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[120 * mm, 55 * mm],
    )
    summary_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f2ca50")),
        ("TEXTCOLOR", (0, -1), (-1, -1), colors.HexColor("#241a00")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))

    story.append(summary_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph(
        (
            "Thank you for shopping with WheelVerse. "
            "This is a computer-generated invoice."
        ),
        normal_style,
    ))

    doc.build(story)
    return response





@login_required
def add_product_review(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_related(
            "order",
            "variant",
            "variant__product"
        ).prefetch_related("variant__images"),
        id=item_id,
        order__user=request.user
    )

    order = item.order

    if order.status != "DELIVERED":
        messages.error(request, "Review is allowed only after delivery.")
        return redirect("order_detail", order_id=order.id)

    if item.is_cancelled:
        messages.error(request, "Cancelled item cannot be reviewed.")
        return redirect("order_detail", order_id=order.id)

    if ProductReview.objects.filter(order_item=item, user=request.user).exists():
        messages.info(request, "You already reviewed this product.")
        return redirect("order_detail", order_id=order.id)

    if request.method == "POST":
        rating = request.POST.get("rating")
        review_text = request.POST.get("review", "").strip()
        images = request.FILES.getlist("review_images")

        if not rating:
            messages.error(request, "Please select a rating.")
            return redirect("add_product_review", item_id=item.id)

        rating = int(rating)

        if rating < 1 or rating > 5:
            messages.error(request, "Invalid rating selected.")
            return redirect("add_product_review", item_id=item.id)

        if not review_text or len(review_text) < 10:
            messages.error(request, "Review must contain at least 10 characters.")
            return redirect("add_product_review", item_id=item.id)

        if len(review_text) > 1000:
            messages.error(request, "Review cannot exceed 1000 characters.")
            return redirect("add_product_review", item_id=item.id)

        if len(images) > 5:
            messages.error(request, "Maximum 5 images allowed.")
            return redirect("add_product_review", item_id=item.id)

        allowed_types = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
        max_size = 5 * 1024 * 1024

        for image in images:
            if image.content_type not in allowed_types:
                messages.error(request, "Only JPG, PNG and WEBP images are allowed.")
                return redirect("add_product_review", item_id=item.id)

            if image.size > max_size:
                messages.error(request, "Each image must be less than 5MB.")
                return redirect("add_product_review", item_id=item.id)

        review = ProductReview.objects.create(
            user=request.user,
            order_item=item,
            product=item.variant.product,
            variant=item.variant,
            rating=rating,
            review=review_text,
        )

        for image in images:
            ProductReviewImage.objects.create(
                review=review,
                image=image
            )

        messages.success(request, "Review submitted successfully.")
        return redirect("product_detail", product_id=item.variant.product.id)

    return render(request, "orders/product_review.html", {
        "item": item,
        "order": order,
        "variant": item.variant,
        "product": item.variant.product,
    })