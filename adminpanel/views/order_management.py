from decimal import Decimal
import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q, Count, F, Prefetch, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from Orders.models import Order, ReturnRequest, ReturnRequestImage
from django.utils import timezone
from django.contrib import messages
from django.utils import timezone


from django.db import transaction
from Wallet.utils import credit_wallet
from Wallet.models import Wallet, WalletTransaction

import csv


@staff_member_required(login_url="admin_login")
def admin_orders(request):
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "all").strip()
    payment_method = request.GET.get("payment_method", "all").strip()
    sort = request.GET.get("sort", "newest").strip()

    orders = (
        Order.objects
        .select_related("user", "shipping_address")
        .prefetch_related("items", "items__variant", "items__variant__images")
        .annotate(
            total_items_count=Count("items", distinct=True),
            cancelled_items_count=Count(
                "items",
                filter=Q(items__is_cancelled=True),
                distinct=True
            )
        )
    )

    if search:
        orders = orders.filter(
            Q(order_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(shipping_address__full_name__icontains=search) |
            Q(shipping_address__email__icontains=search) |
            Q(items__product_name__icontains=search)
        ).distinct()

    if status != "all":
        orders = orders.filter(status=status)

    if payment_method != "all":
        orders = orders.filter(payment_method=payment_method)

    if sort == "oldest":
        orders = orders.order_by("ordered_at")
    elif sort == "amount_high":
        orders = orders.order_by("-total_amount")
    elif sort == "amount_low":
        orders = orders.order_by("total_amount")
    else:
        orders = orders.order_by("-ordered_at")

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="wheelverse_orders.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Order ID",
            "Customer",
            "Email",
            "Amount",
            "Date",
            "Order Status",
            "Cancelled Items",
            "Total Items",
            "Payment Method",
        ])

        for order in orders:
            address = getattr(order, "shipping_address", None)

            writer.writerow([
                order.order_id,
                address.full_name if address else order.user.username,
                address.email if address else order.user.email,
                order.total_amount,
                order.ordered_at.strftime("%Y-%m-%d"),
                order.status,
                order.cancelled_items_count,
                order.total_items_count,
                order.payment_method,
            ])

        return response

    paginator = Paginator(orders, 8)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "adminpanel/admin_order/admin_orders.html", {
        "page_obj": page_obj,
        "search": search,
        "current_status": status,
        "current_payment_method": payment_method,
        "current_sort": sort,
        "total_orders": paginator.count,
    })

@staff_member_required(login_url="admin_login")
def admin_order_detail(request, order_id):

    return_request_queryset = (
        ReturnRequest.objects
        .select_related("user")
        .order_by("requested_at")
    )

    order = get_object_or_404(
        Order.objects
        .select_related(
            "user",
            "shipping_address",
        )
        .prefetch_related(
            "items",
            "items__variant",
            "items__variant__images",
            Prefetch(
                "items__order_return_requests",
                queryset=return_request_queryset,
                to_attr="loaded_return_requests",
            ),
        ),
        id=order_id,
    )

    items = list(order.items.all())

    original_subtotal = Decimal("0.00")
    original_offer_discount = Decimal("0.00")
    original_after_offer = Decimal("0.00")

    total_ordered_quantity = 0
    total_cancelled_quantity = 0
    total_return_requested_quantity = 0
    total_returned_quantity = 0
    total_active_quantity = 0

    for item in items:
        ordered_quantity = item.quantity or 0
        cancelled_quantity = min(
            getattr(item, "cancelled_quantity", 0) or 0,
            ordered_quantity,
        )

        return_requests = list(
            getattr(
                item,
                "loaded_return_requests",
                [],
            )
        )

        return_requested_quantity = sum(
            (
                return_request.return_quantity or 0
                for return_request in return_requests
                if return_request.status in {
                    "REQUESTED",
                    "APPROVED",
                    "PICKED_UP",
                }
            ),
            0,
        )

        returned_quantity = sum(
            (
                return_request.return_quantity or 0
                for return_request in return_requests
                if return_request.status == "REFUNDED"
            ),
            0,
        )

        unavailable_quantity = (
            cancelled_quantity
            + return_requested_quantity
            + returned_quantity
        )

        active_quantity = max(
            ordered_quantity - unavailable_quantity,
            0,
        )

        item.display_ordered_quantity = ordered_quantity
        item.display_cancelled_quantity = cancelled_quantity
        item.display_return_requested_quantity = (
            return_requested_quantity
        )
        item.display_returned_quantity = returned_quantity
        item.display_active_quantity = active_quantity
        item.display_return_requests = return_requests

        if cancelled_quantity >= ordered_quantity:
            item.display_quantity_status = "FULLY CANCELLED"
            item.display_quantity_status_class = "text-red-300"
        elif cancelled_quantity > 0:
            item.display_quantity_status = "PARTIALLY CANCELLED"
            item.display_quantity_status_class = "text-amber-300"
        elif returned_quantity >= ordered_quantity:
            item.display_quantity_status = "FULLY RETURNED"
            item.display_quantity_status_class = "text-purple-300"
        elif returned_quantity > 0:
            item.display_quantity_status = "PARTIALLY RETURNED"
            item.display_quantity_status_class = "text-purple-300"
        elif return_requested_quantity > 0:
            item.display_quantity_status = "RETURN IN PROGRESS"
            item.display_quantity_status_class = "text-blue-300"
        else:
            item.display_quantity_status = "ACTIVE"
            item.display_quantity_status_class = "text-green-300"

        item_original_price = (
            getattr(item, "original_price", None)
            or item.price
            or Decimal("0.00")
        )

        item_unit_offer_discount = (
            getattr(item, "offer_discount", None)
            or Decimal("0.00")
        )

        item.display_original_total = (
            item_original_price * ordered_quantity
        ).quantize(Decimal("0.01"))

        item.display_offer_discount_total = (
            item_unit_offer_discount * ordered_quantity
        ).quantize(Decimal("0.01"))

        item.display_current_product_total = (
            (item.price or Decimal("0.00"))
            * active_quantity
        ).quantize(Decimal("0.01"))

        original_subtotal += item.display_original_total
        original_offer_discount += (
            item.display_offer_discount_total
        )

        total_ordered_quantity += ordered_quantity
        total_cancelled_quantity += cancelled_quantity
        total_return_requested_quantity += (
            return_requested_quantity
        )
        total_returned_quantity += returned_quantity
        total_active_quantity += active_quantity

    original_after_offer = max(
        original_subtotal - original_offer_discount,
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    current_subtotal_after_offer = max(
        order.subtotal - order.offer_discount,
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    calculated_current_total = max(
        order.subtotal
        - order.offer_discount
        - order.coupon_discount
        + order.shipping_fee,
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    cancellation_refunded_amount = (
        WalletTransaction.objects
        .filter(
            order=order,
            purpose="CANCEL_REFUND",
            status="COMPLETED",
            transaction_type="CREDIT",
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return_refunded_amount = (
        WalletTransaction.objects
        .filter(
            order=order,
            purpose="RETURN_REFUND",
            status="COMPLETED",
            transaction_type="CREDIT",
        )
        .aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    total_refunded_amount = (
        cancellation_refunded_amount
        + return_refunded_amount
    ).quantize(Decimal("0.01"))

    if order.payment_method == "COD":
        if order.status == "DELIVERED":
            payment_status = "COD COLLECTED"
            payment_status_class = "text-green-300"
        elif order.status == "CANCELLED":
            payment_status = "CANCELLED — NOT COLLECTED"
            payment_status_class = "text-red-300"
        else:
            payment_status = "COD PENDING"
            payment_status_class = "text-amber-300"

    elif order.payment_method == "RAZORPAY":
        if order.razorpay_payment_id:
            payment_status = "PAID"
            payment_status_class = "text-green-300"
        else:
            payment_status = "PAYMENT PENDING"
            payment_status_class = "text-amber-300"

    elif order.payment_method == "WALLET":
        payment_status = "PAID FROM WALLET"
        payment_status_class = "text-green-300"

    else:
        payment_status = (
            "PAID"
            if order.status != "PAYMENT_PENDING"
            else "PAYMENT PENDING"
        )
        payment_status_class = (
            "text-green-300"
            if payment_status == "PAID"
            else "text-amber-300"
        )

    status_steps = [
        "CONFIRMED",
        "SHIPPED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
    ]

    final_statuses = [
        "DELIVERED",
        "CANCELLED",
        "RETURNED",
    ]

    current_index = (
        status_steps.index(order.status)
        if order.status in status_steps
        else -1
    )

    timeline = []

    for index, step in enumerate(status_steps):
        timeline.append({
            "key": step,
            "label": step.replace("_", " ").title(),
            "completed": index <= current_index,
        })

    allowed_status_choices = []

    if (
        order.status not in final_statuses
        and order.status in status_steps
    ):
        allowed_statuses = status_steps[current_index:]

        allowed_status_choices = [
            (value, label)
            for value, label in Order.STATUS_CHOICES
            if value in allowed_statuses
        ]

    context = {
        "order": order,
        "items": items,
        "timeline": timeline,
        "status_choices": allowed_status_choices,
        "final_statuses": final_statuses,

        "payment_status": payment_status,
        "payment_status_class": payment_status_class,

        "original_subtotal": original_subtotal.quantize(
            Decimal("0.01")
        ),
        "original_offer_discount": (
            original_offer_discount.quantize(
                Decimal("0.01")
            )
        ),
        "original_after_offer": original_after_offer,

        "current_subtotal_after_offer": (
            current_subtotal_after_offer
        ),
        "calculated_current_total": (
            calculated_current_total
        ),

        "cancellation_refunded_amount": (
            cancellation_refunded_amount
        ),
        "return_refunded_amount": (
            return_refunded_amount
        ),
        "total_refunded_amount": total_refunded_amount,

        "total_ordered_quantity": total_ordered_quantity,
        "total_cancelled_quantity": (
            total_cancelled_quantity
        ),
        "total_return_requested_quantity": (
            total_return_requested_quantity
        ),
        "total_returned_quantity": (
            total_returned_quantity
        ),
        "total_active_quantity": total_active_quantity,
    }

    return render(
        request,
        "adminpanel/admin_order/admin_order_detail.html",
        context,
    )

    
    

@staff_member_required(login_url="admin_login")
def admin_update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    status_flow = [
        "CONFIRMED",
        "SHIPPED",
        "OUT_FOR_DELIVERY",
        "DELIVERED",
    ]

    final_statuses = [
        "DELIVERED",
        "CANCELLED",
        "RETURNED",
    ]

    if request.method == "POST":
        new_status = request.POST.get("status")

        if order.status in final_statuses:
            messages.error(
                request,
                f"This order is {order.get_status_display()}. The status can no longer be changed."
            )
            return redirect("admin_order_detail", order_id=order.id)

        if order.status not in status_flow:
            messages.error(
                request,
                f"Cannot update order from {order.status}. Please confirm the order first."
            )
            return redirect("admin_order_detail", order_id=order.id)

        if new_status not in status_flow:
            messages.error(request, "Invalid order status.")
            return redirect("admin_order_detail", order_id=order.id)

        current_index = status_flow.index(order.status)
        new_index = status_flow.index(new_status)

        if new_index == current_index:
            messages.info(request, "Order status is already selected.")
            return redirect("admin_order_detail", order_id=order.id)

        if new_index < current_index:
            messages.error(
                request,
                f"Cannot change order status from {order.status} back to {new_status}."
            )
            return redirect("admin_order_detail", order_id=order.id)

        if new_index != current_index + 1:
            next_status = status_flow[current_index + 1]

            messages.error(
                request,
                f"Cannot change order status from {order.status} → {new_status}. Please update to {next_status} first."
            )
            return redirect("admin_order_detail", order_id=order.id)

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        messages.success(
            request,
            f"Order status updated to {order.get_status_display()} successfully."
        )

    return redirect("admin_order_detail", order_id=order.id)

@staff_member_required(login_url="admin_login")
def admin_cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        reason = request.POST.get("cancel_reason", "").strip()

        if not reason:
            messages.error(request, "Please enter cancel reason.")
            return redirect("admin_order_detail", order_id=order.id)

        if order.status in ["SHIPPED", "DELIVERED", "RETURNED", "CANCELLED"]:
            messages.error(request, "This order cannot be cancelled.")
            return redirect("admin_order_detail", order_id=order.id)

        order.status = "CANCELLED"
        order.cancel_reason = reason
        order.save(update_fields=["status", "cancel_reason", "updated_at"])

        messages.success(request, "Order cancelled successfully.")

    return redirect("admin_order_detail", order_id=order.id)




@staff_member_required(login_url="admin_login")
def admin_returns(request):
    returns = (
        ReturnRequest.objects
        .select_related(
            "order",
            "order_item",
            "order_item__variant",
            "order_item__variant__product",
            "user",
        )
        .prefetch_related("order_item__variant__images")
    )

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "all").strip()

    if search:
        returns = returns.filter(
            Q(order__order_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(order_item__product_name__icontains=search)
        )

    if status != "all":
        returns = returns.filter(status=status)

    total_returns = ReturnRequest.objects.count()
    pending_returns = ReturnRequest.objects.filter(status="REQUESTED").count()
    approved_returns = ReturnRequest.objects.filter(status="APPROVED").count()
    refunded_returns = ReturnRequest.objects.filter(status="REFUNDED").count()
    rejected_returns = ReturnRequest.objects.filter(status="REJECTED").count()
    refunded_returns = ReturnRequest.objects.filter(status="REFUNDED").count()

    paginator = Paginator(returns, 6)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "adminpanel/admin_returns/admin_returns.html", {
        "page_obj": page_obj,
        "search": search,
        "current_status": status,

        "total_returns": total_returns,
        "pending_returns": pending_returns,
        "approved_returns": approved_returns,
        "rejected_returns": rejected_returns,
        ""
        "refunded_returns": refunded_returns,

        "status_choices": ReturnRequest.STATUS_CHOICES,
    })


@staff_member_required(login_url="admin_login")
def approve_return(request, return_id):
    return_request = get_object_or_404(ReturnRequest, id=return_id)

    return_request.status = "APPROVED"
    return_request.save(update_fields=["status", "updated_at"])

    order = return_request.order
    order.status = "RETURN_APPROVED"
    order.save(update_fields=["status", "updated_at"])

    messages.success(request, "Return request approved successfully.")
    return redirect("admin_returns")


@staff_member_required(login_url="admin_login")
def reject_return(request, return_id):
    return_request = get_object_or_404(ReturnRequest, id=return_id)

    if request.method == "POST":
        admin_note = request.POST.get("admin_note", "").strip()

        return_request.status = "REJECTED"
        return_request.admin_note = admin_note
        return_request.save(update_fields=["status", "admin_note", "updated_at"])

        order = return_request.order
        order.status = "RETURN_REJECTED"
        order.save(update_fields=["status", "updated_at"])

        messages.success(request, "Return request rejected successfully.")

    return redirect("admin_returns")




@staff_member_required(login_url="admin_login")
@transaction.atomic
def process_refund(request, return_id):
    return_request = get_object_or_404(
        ReturnRequest.objects.select_related(
            "order",
            "order_item",
            "user"
        ),
        id=return_id
    )

    if return_request.status == "REFUNDED":
        messages.info(request, "Refund already processed.")
        return redirect("admin_return_detail", return_id=return_request.id)

    if return_request.status != "PICKED_UP":
        messages.error(request, "Refund can be processed only after product is picked up.")
        return redirect("admin_return_detail", return_id=return_request.id)

    refund_amount = return_request.refund_amount or return_request.order_item.item_total

    wallet, created = Wallet.objects.select_for_update().get_or_create(
        user=return_request.user
    )

    pending_txn = WalletTransaction.objects.filter(
        wallet=wallet,
        return_request=return_request,
        purpose="RETURN_REFUND",
        status="PENDING"
    ).first()

    if pending_txn:
        pending_txn.status = "COMPLETED"
        pending_txn.description = f"Return refund completed for order {return_request.order.order_id}"
        pending_txn.save(update_fields=["status", "description"])
    else:
        pending_txn = WalletTransaction.objects.create(
            wallet=wallet,
            order=return_request.order,
            return_request=return_request,
            transaction_type="CREDIT",
            purpose="RETURN_REFUND",
            amount=refund_amount,
            status="COMPLETED",
            description=f"Return refund completed for order {return_request.order.order_id}",
            reference=f"RETURN_REFUND_{return_request.id}",
        )

    Wallet.objects.filter(id=wallet.id).update(
        balance=F("balance") + refund_amount
    )

    return_request.status = "REFUNDED"
    return_request.refunded_at = timezone.now()
    return_request.save(update_fields=[
        "status",
        "refunded_at",
        "updated_at",
    ])

    order = return_request.order
    order.status = "RETURNED"
    order.save(update_fields=["status", "updated_at"])

    messages.success(
        request,
        f"₹{refund_amount} refunded to {return_request.user.username}'s wallet."
    )

    return redirect("admin_return_detail", return_id=return_request.id)



@staff_member_required(login_url="admin_login")
def return_action_page(request, return_id):
    return_request = get_object_or_404(
        ReturnRequest.objects.select_related(
            "order",
            "order_item",
            "order_item__variant",
            "order_item__variant__product",
            "user",
        ).prefetch_related("order_item__variant__images"),
        id=return_id
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if return_request.status != "REQUESTED":
            messages.error(request, "This return request is already processed.")
            return redirect("admin_returns")

        if action == "approve":
            return_request.status = "APPROVED"
            return_request.save(update_fields=["status", "updated_at"])

            return_request.order.status = "RETURN_APPROVED"
            return_request.order.save(update_fields=["status", "updated_at"])

            messages.success(request, "Return request approved successfully.")
            return redirect("admin_returns")

        if action == "reject":
            return_request.status = "REJECTED"
            return_request.admin_note = "Rejected by admin."
            return_request.save(update_fields=["status", "admin_note", "updated_at"])

            return_request.order.status = "RETURN_REJECTED"
            return_request.order.save(update_fields=["status", "updated_at"])

            messages.success(request, "Return request rejected successfully.")
            return redirect("admin_returns")

        messages.error(request, "Invalid action.")
        return redirect("return_action_page", return_id=return_request.id)

    return render(request, "adminpanel/admin_returns/return_action.html", {
        "return_request": return_request,
        "item": return_request.order_item,
        "variant": return_request.order_item.variant,
    })
    
    
@staff_member_required(login_url="admin_login")
def admin_return_detail(request, return_id):
    return_request = get_object_or_404(
        ReturnRequest.objects.select_related(
            "order",
            "order__user",
            "order__shipping_address",
            "order_item",
            "order_item__variant",
            "order_item__variant__product",
            "user",
        ).prefetch_related(
            "images",
            "order_item__variant__images",
        ),
        id=return_id
    )

    order = return_request.order
    item = return_request.order_item
    variant = item.variant

    timeline = [
        {
            "key": "REQUESTED",
            "label": "Return Requested",
            "completed": return_request.status in [
                "REQUESTED",
                "PICKED_UP",
                "APPROVED",
                "REJECTED",
                "REFUNDED",
            ],
            "date": return_request.requested_at,
        },

        {
            "key": "APPROVED",
            "label": "Return Approved",
            "completed": return_request.status in [
                "APPROVED",
                "REFUNDED",
            ],
            "date": return_request.updated_at if return_request.status in [
                "APPROVED",
                "REFUNDED",
            ] else None,
        },

        {
            "key": "REJECTED",
            "label": "Return Rejected",
            "completed": return_request.status == "REJECTED",
            "date": return_request.updated_at if return_request.status == "REJECTED" else None,
        },
        
        {
            "key": "PICKED_UP",
            "label": "Product Picked Up",
            "completed": return_request.status in [
                "PICKED_UP",
                "APPROVED",
                "REJECTED",
                "REFUNDED",
            ],
            "date": return_request.picked_up_at,
        },

        {
            "key": "REFUNDED",
            "label": "Refund Completed",
            "completed": return_request.status == "REFUNDED",
            "date": return_request.refunded_at,
        },
    ]

    return render(request, "adminpanel/admin_returns/admin_return_detail.html", {
        "return_request": return_request,
        "order": order,
        "item": item,
        "variant": variant,
        "timeline": timeline,
    })
    





@staff_member_required(login_url="admin_login")
@transaction.atomic
def mark_return_picked_up(request, return_id):
    return_request = get_object_or_404(
        ReturnRequest.objects.select_related(
            "order",
            "order_item",
            "user"
        ),
        id=return_id
    )

    if return_request.status != "APPROVED":
        messages.error(request, "Only approved returns can be picked up.")
        return redirect("admin_return_detail", return_id=return_request.id)

    refund_amount = return_request.refund_amount or return_request.order_item.item_total

    wallet, created = Wallet.objects.get_or_create(user=return_request.user)

    WalletTransaction.objects.get_or_create(
        reference=f"RETURN_PENDING_{return_request.id}",
        defaults={
            "wallet": wallet,
            "order": return_request.order,
            "return_request": return_request,
            "transaction_type": "CREDIT",
            "purpose": "RETURN_REFUND",
            "amount": refund_amount,
            "status": "PENDING",
            "description": f"Pending return refund for order {return_request.order.order_id}",
        }
    )

    return_request.status = "PICKED_UP"
    return_request.picked_up_at = timezone.now()
    return_request.save(update_fields=[
        "status",
        "picked_up_at",
        "updated_at",
    ])

    messages.success(
        request,
        f"Return marked as picked up. ₹{refund_amount} added to user's pending refund."
    )
    return redirect("admin_return_detail", return_id=return_request.id)