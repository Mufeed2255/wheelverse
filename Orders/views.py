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
    pincode = data.get("pincode", "").strip()
    address_line_1 = data.get("address_line_1", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "").strip()

    if not name or len(name) < 2 or len(name) > 60:
        return False, "Please enter a valid name (2 to 60 characters)."

    if not phone_number or not re.match(r"^\d{10}$", phone_number):
        return False, "Please enter a valid 10-digit phone number."

    if not address_line_1 or len(address_line_1) < 5:
        return False, "Address Line 1 must be at least 5 characters."

    if not city or len(city) < 2:
        return False, "Please enter a valid city name."

    if not state or len(state) < 2:
        return False, "Please enter a valid state name."

    if not pincode or not re.match(r"^\d{6}$", pincode):
        return False, "Pincode must be exactly 6 digits."

    return True, ""



@login_required
@require_POST
def checkout_add_address(request):
    is_valid, error_message = validate_checkout_address(request.POST)

    if not is_valid:
        return JsonResponse(
            {
                "success": False,
                "message": error_message,
            },
            status=400
        )

    is_default = request.POST.get("is_default") == "on"

    if is_default:
        Address.objects.filter(
            user=request.user,
            is_default=True
        ).update(is_default=False)

    if not Address.objects.filter(user=request.user).exists():
        is_default = True

    address = Address.objects.create(
        user=request.user,
        name=request.POST.get("name", "").strip(),
        phone_number=request.POST.get("phone_number", "").strip(),
        address_line_1=request.POST.get("address_line_1", "").strip(),
        address_line_2=request.POST.get("address_line_2", "").strip(),
        city=request.POST.get("city", "").strip(),
        state=request.POST.get("state", "").strip(),
        pincode=request.POST.get("pincode", "").strip(),
        country="INDIA",
        address_type=request.POST.get("address_type", "HOME"),
        is_default=is_default,
    )

    return JsonResponse({
        "success": True,
        "message": "Address added successfully.",
        "address": {
            "id": address.id,
            "name": address.name,
            "phone_number": address.phone_number,
            "address_line_1": address.address_line_1,
            "address_line_2": address.address_line_2 or "",
            "city": address.city,
            "state": address.state,
            "pincode": address.pincode,
            "country": address.country,
            "address_type": address.address_type,
            "is_default": address.is_default,
        }
    })


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
@transaction.atomic
def place_order(request):
    if request.method != "POST":
        return redirect("checkout")

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

    selected_address_id = request.POST.get("selected_address")
    payment_method = request.POST.get("payment_method", "COD")

    if payment_method not in {"COD", "WALLET", "RAZORPAY", "UPI"}:
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

    if not phone.isdigit() or len(phone) != 10:
        messages.error(request, "Selected address has an invalid phone number.")
        return redirect("checkout")

    if not postal_code.isdigit() or len(postal_code) != 6:
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

        if cart_item.quantity > variant.stock:
            messages.error(
                request,
                f"Only {variant.stock} unit(s) available for {variant.product.name}."
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
                f"Minimum amount ₹{applied_coupon.min_cart_amount} is required after offer discount."
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

    order = Order.objects.create(
        user=request.user,
        subtotal=original_subtotal,
        offer_discount=offer_discount,
        coupon_discount=coupon_discount,
        discount_amount=total_discount,
        shipping_fee=shipping_fee,
        total_amount=grand_total,
        payment_method=payment_method,
        status="PENDING",
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

    if applied_coupon:
        applied_coupon.used_count += 1
        applied_coupon.save(update_fields=["used_count"])

        CouponUsage.objects.create(
            user=request.user,
            coupon=applied_coupon,
            order=order,
        )

        request.session.pop("applied_coupon_code", None)

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

    address = OrderAddress.objects.filter(order=order).first()
    wallet, created = Wallet.objects.get_or_create(user=request.user)

    subtotal_after_offer = order.subtotal - order.offer_discount
    total_savings = order.offer_discount + order.coupon_discount

    razorpay_amount = int(order.total_amount * Decimal("100"))
    razorpay_order_id = None

    if order.payment_method in {"RAZORPAY", "UPI"}:
        client = razorpay.Client(
            auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET,
            )
        )

        if not order.razorpay_order_id:
            razorpay_order = client.order.create({
                "amount": razorpay_amount,
                "currency": "INR",
                "payment_capture": 1,
                "notes": {
                    "order_id": order.order_id,
                    "user_id": str(request.user.id),
                },
            })

            order.razorpay_order_id = razorpay_order["id"]
            order.save(
                update_fields=[
                    "razorpay_order_id",
                    "updated_at",
                ]
            )

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
    if order.status == "CONFIRMED":
        return True, "Already confirmed."

    if order.status != "PENDING":
        return False, "Order cannot be confirmed."

    order_items = order.items.select_related("variant", "variant__product")
    updated_product_ids = set()

    for oi in order_items:
        variant = ProductVariant.objects.select_for_update().get(id=oi.variant.id)

        if oi.quantity > variant.stock:
            return False, f"Only {variant.stock} unit(s) left for {oi.product_name}."

        variant.stock -= oi.quantity
        variant.save(update_fields=["stock"])
        updated_product_ids.add(variant.product.id)

    order.status = "CONFIRMED"
    order.save(update_fields=["status", "updated_at"])

    Cart.objects.filter(user=order.user).delete()

    def sync_stock():
        for pid in updated_product_ids:
            product = AdminProduct.objects.get(id=pid)
            total_stock = product.variants.filter(
                is_deleted=False
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

    payment_method = request.POST.get("payment_method")

    if payment_method == "COD":
        success, msg = confirm_order_after_payment(order)

        if not success:
            messages.error(request, msg)
            return redirect("order_failed_with_order", order_id=order.id)

        order.payment_method = "COD"
        order.save(update_fields=["payment_method", "updated_at"])

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
        user=request.user
    )

    razorpay_payment_id = request.POST.get("razorpay_payment_id")
    razorpay_order_id = request.POST.get("razorpay_order_id")
    razorpay_signature = request.POST.get("razorpay_signature")

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except Exception:
        messages.error(request, "Payment verification failed.")
        return redirect("order_failed_with_order", order_id=order.id)

    success, msg = confirm_order_after_payment(order)

    if not success:
        messages.error(request, msg)
        return redirect("order_failed_with_order", order_id=order.id)

    order.razorpay_payment_id = razorpay_payment_id
    order.razorpay_order_id = razorpay_order_id
    order.razorpay_signature = razorpay_signature
    order.save(update_fields=[
        "razorpay_payment_id",
        "razorpay_order_id",
        "razorpay_signature",
        "updated_at",
    ])

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
        user=request.user
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

    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related(
        "items",
        "items__variant",
        "items__variant__images"
    ).order_by("-ordered_at")

    if status_filter != "all":
        orders = orders.filter(status=status_filter)

    if search_query:
        orders = orders.filter(
            Q(order_id__icontains=search_query) |
            Q(items__product_name__icontains=search_query)
        ).distinct()

    paginator = Paginator(orders, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    counts = {
        "all": Order.objects.filter(user=request.user).count(),
        "pending": Order.objects.filter(user=request.user, status="PENDING").count(),
        "confirmed": Order.objects.filter(user=request.user, status="CONFIRMED").count(),
        "shipped": Order.objects.filter(user=request.user, status="SHIPPED").count(),
        "delivered": Order.objects.filter(user=request.user, status="DELIVERED").count(),
        "returned": Order.objects.filter(user=request.user, status="RETURNED").count(),
    }

    return render(request, "orders/my_orders.html", {
        "page_obj": page_obj,
        "orders": page_obj.object_list,
        "status_filter": status_filter,
        "search_query": search_query,
        "counts": counts,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related(
            "items",
            "items__variant",
            "items__variant__images"
        ),
        id=order_id,
        user=request.user
    )

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

    return render(request, "orders/order_detail.html", {
        "order": order,
        "address": address,
        "first_item": first_item,
        "current_step": current_step,
        "progress_percent": progress_percent,
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

    if order.status in ["DELIVERED", "CANCELLED", "RETURNED", "RETURN_REQUESTED"]:
        messages.error(request, "This item cannot be cancelled.")
        return redirect("order_detail", order_id=order.id)

    if order_item.is_cancelled:
        messages.info(request, "This item is already cancelled.")
        return redirect("order_detail", order_id=order.id)

    if request.method == "POST":
        reason = request.POST.get("cancel_reason", "").strip()
        comments = request.POST.get("comments", "").strip()

        if not reason:
            messages.error(request, "Please select a cancellation reason.")
            return redirect("cancel_order_item", item_id=order_item.id)

        final_reason = f"{reason}\n\n{comments}" if comments else reason

        order_item.is_cancelled = True
        order_item.cancel_reason = final_reason
        order_item.save(update_fields=["is_cancelled", "cancel_reason"])

        product_id_to_sync = None

        if order_item.variant:
            order_item.variant.stock += order_item.quantity
            order_item.variant.save(update_fields=["stock"])
            product_id_to_sync = order_item.variant.product.id  

        active_items = order.items.filter(is_cancelled=False)

        if active_items.exists():
            order.subtotal = sum(item.item_total for item in active_items)
            order.total_amount = order.subtotal - order.discount + order.shipping_charge
            order.save(update_fields=["subtotal", "total_amount", "updated_at"])
        else:
            order.status = "CANCELLED"
            order.cancel_reason = final_reason
            order.save(update_fields=["status", "cancel_reason", "updated_at"])
            
        refund_done = False

        if order.payment_method != "COD" and order.status in [
            "CONFIRMED",
            "SHIPPED",
            "OUT_FOR_DELIVERY",
            "CANCELLED",
        ]:
            refund_done = refund_to_wallet_for_cancel(
                order=order,
                amount=order_item.item_total,
                reference_suffix=f"ITEM_{order_item.id}"
            )

        if product_id_to_sync:
            def sync_stock(pid=product_id_to_sync):
                from django.db.models import Sum
                from adminpanel.models import Product as AdminProduct
                p = AdminProduct.objects.get(id=pid)
                total = p.variants.filter(
                    is_deleted=False,
                    is_active=True
                ).aggregate(total=Sum('stock'))['total'] or 0
                p.total_stock = total
                p.save(update_fields=['total_stock'])

            transaction.on_commit(sync_stock)

        messages.success(request, "Item cancelled successfully.")
        return redirect("order_detail", order_id=order.id)

    return render(request, "orders/cancel_item.html", {
        "order": order,
        "item": order_item,
    })
    



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
        Order.objects.prefetch_related("items"),
        id=order_id,
        user=request.user
    )

    address = OrderAddress.objects.filter(order=order).first()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="invoice_{order.order_id}.pdf"'

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
        ["Payment Method", order.payment_method],
        ["Order Status", order.status],
    ]

    table = Table(invoice_info, colWidths=[45 * mm, 110 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2ca50")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#241a00")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    story.append(Spacer(1, 16))

    story.append(Paragraph("Billing / Delivery Address", heading_style))

    if address:
        address_text = f"""
        <b>{address.full_name}</b><br/>
        {address.address}<br/>
        {address.city}, {address.state} - {address.postal_code}<br/>
        Phone: {address.phone}<br/>
        Email: {address.email}
        """
    else:
        address_text = "Address not available."

    story.append(Paragraph(address_text, normal_style))
    story.append(Spacer(1, 16))

    story.append(Paragraph("Order Items", heading_style))

    item_data = [
        ["Product", "Variant", "Qty", "Price", "Total"]
    ]

    for item in order.items.all():
        variant_text = ""

        if item.variant_color:
            variant_text += item.variant_color

        if item.variant_size:
            variant_text += f" / {item.variant_size}"

        item_data.append([
            item.product_name,
            variant_text or "-",
            str(item.quantity),
            f"Rs. {item.price}",
            f"Rs. {item.item_total}",
        ])

    item_table = Table(
        item_data,
        colWidths=[65 * mm, 35 * mm, 18 * mm, 28 * mm, 30 * mm]
    )

    item_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111111")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#f2ca50")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (2, 1), (-1, -1), "CENTER"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))

    story.append(item_table)
    story.append(Spacer(1, 16))

    summary_data = [
        ["Subtotal", f"Rs. {order.subtotal}"],
        ["Discount", f"- Rs. {order.discount}"],
        ["Shipping Charge", f"Rs. {order.shipping_charge}"],
        ["Total Amount", f"Rs. {order.total_amount}"],
    ]

    summary_table = Table(summary_data, colWidths=[120 * mm, 55 * mm])
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
        "Thank you for shopping with WheelVerse. This is a computer-generated invoice.",
        normal_style
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
