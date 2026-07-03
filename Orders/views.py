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
from .models import Order, OrderItem, OrderAddress,  ReturnRequest, ReturnRequestImage
from django.db.models import Sum
from adminpanel.models import Product as AdminProduct

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
        status="CONFIRMED",
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



@login_required
@transaction.atomic
def cancel_order(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related(
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

        for item in order.items.filter(is_cancelled=False):
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save(update_fields=["stock"])
                product_ids_to_sync.add(item.variant.product.id)

            item.is_cancelled = True
            item.cancel_reason = final_reason
            item.save(update_fields=["is_cancelled", "cancel_reason"])

        order.status = "CANCELLED"
        order.cancel_reason = final_reason
        order.save(update_fields=["status", "cancel_reason", "updated_at"])

        def sync_stock(pids=product_ids_to_sync):
            from django.db.models import Sum
            from adminpanel.models import Product as AdminProduct
            for pid in pids:
                p = AdminProduct.objects.get(id=pid)
                total = p.variants.filter(
                    is_deleted=False,
                    is_active=True
                ).aggregate(total=Sum('stock'))['total'] or 0
                p.total_stock = total
                p.save(update_fields=['total_stock'])

        transaction.on_commit(sync_stock)

        messages.success(request, "Order cancelled successfully.")
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

