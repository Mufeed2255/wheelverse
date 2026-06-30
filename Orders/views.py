import re
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db import transaction

from Accounts.models import Address
from Products.models import Cart, ProductVariant
from .models import Order, OrderItem, OrderAddress
from django.db.models import Sum
from adminpanel.models import Product as AdminProduct

    
from django.core.paginator import Paginator
from django.db.models import Q




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
    cart_items = Cart.objects.filter(
        user=request.user,
        variant__is_active=True,
        variant__is_deleted=False
    ).select_related(
        "variant",
        "variant__product"
    ).prefetch_related(
        "variant__images"
    )

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    subtotal = sum(item.subtotal() for item in cart_items)
    discount = Decimal("0.00")
    shipping = Decimal("80.00") if subtotal > 0 else Decimal("0.00")
    grand_total = subtotal - discount + shipping

    addresses = Address.objects.filter(
        user=request.user
    ).order_by(
        "-is_default",
        "-created_at"
    )

    context = {
        "cart_items": cart_items,
        "addresses": addresses,
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "grand_total": grand_total,
        "cart_count": cart_items.count(),
    }

    return render(request, "orders/checkout.html", context)


@login_required
@transaction.atomic
def place_order(request):
    if request.method != "POST":
        return redirect("checkout")

    cart_items = Cart.objects.filter(
        user=request.user,
        variant__is_active=True,
        variant__is_deleted=False
    ).select_related(
        "variant",
        "variant__product"
    )

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart")

    selected_address_id = request.POST.get("selected_address")
    payment_method = request.POST.get("payment_method", "COD")

    if not selected_address_id:
        messages.error(request, "Please select a delivery address.")
        return redirect("checkout")

    selected_address = get_object_or_404(
        Address,
        id=selected_address_id,
        user=request.user
    )

    phone = selected_address.phone_number
    postal_code = selected_address.pincode

    if not phone.isdigit() or len(phone) != 10:
        messages.error(request, "Selected address has an invalid phone number.")
        return redirect("checkout")

    if not postal_code.isdigit() or len(postal_code) != 6:
        messages.error(request, "Selected address has an invalid pincode.")
        return redirect("checkout")

    subtotal = Decimal("0.00")

    for item in cart_items:
        variant = ProductVariant.objects.select_for_update().get(
            id=item.variant.id
        )

        if item.quantity > variant.stock:
            messages.error(
                request,
                f"Only {variant.stock} unit(s) available for {variant.product.name}."
            )
            return redirect("cart")

        subtotal += variant.price * item.quantity

    discount = Decimal("0.00")
    shipping = Decimal("80.00") if subtotal > 0 else Decimal("0.00")
    grand_total = subtotal - discount + shipping

    address_str = selected_address.address_line_1
    if selected_address.address_line_2:
        address_str += f", {selected_address.address_line_2}"

    order = Order.objects.create(
        user=request.user,
        subtotal=subtotal,
        discount=discount,
        shipping_charge=shipping,
        total_amount=grand_total,
        payment_method=payment_method,
        status="PENDING",
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

    updated_product_ids = set()

    for item in cart_items:
        variant = ProductVariant.objects.select_for_update().get(
            id=item.variant.id
        )

        item_total = variant.price * item.quantity

        OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name=variant.product.name,
            variant_color=variant.color,
            variant_size=variant.size,
            price=variant.price,
            quantity=item.quantity,
            item_total=item_total,
        )

        variant.stock -= item.quantity
        variant.save()

        updated_product_ids.add(variant.product.id)  
    cart_items.delete()

    def sync_stock():
        for pid in updated_product_ids:
            product = AdminProduct.objects.get(id=pid)
            total_stock = product.variants.filter(is_deleted=False).aggregate(
                total=Sum("stock")
            )["total"] or 0

            product.total_stock = total_stock
            product.save(update_fields=["total_stock"])

    transaction.on_commit(sync_stock)

    return redirect("payment", order_id=order.id)

@login_required
def payment_view(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    order_address = OrderAddress.objects.filter(
        order=order
    ).first()

    context = {
        "order": order,
        "address": order_address,
        "subtotal": order.subtotal,
        "discount": order.discount,
        "shipping": order.shipping_charge,
        "grand_total": order.total_amount,
    }

    return render(request, "orders/payment.html", context)



@login_required
@require_POST
def confirm_payment(request, order_id):
    order = get_object_or_404(
        Order,
        id=order_id,
        user=request.user
    )

    if order.status == "CONFIRMED":
        messages.info(request, "This order is already confirmed.")
        return redirect("order_success", order_id=order.id)

    payment_method = request.POST.get("payment_method", "COD")

    if payment_method != "COD":
        messages.error(request, "Payment failed. Currently only Cash on Delivery is available.")
        return redirect("order_failed_with_order", order_id=order.id)

    order.payment_method = "COD"
    order.status = "CONFIRMED"
    order.save()

    messages.success(request, "Order placed successfully.")
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


@login_required
def order_failed(request):
    return render(request, "orders/order_failed.html")


