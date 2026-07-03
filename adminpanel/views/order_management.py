import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q,Count
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse

from Orders.models import Order, ReturnRequest, ReturnRequestImage
from django.utils import timezone
from django.contrib import messages
from django.utils import timezone

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
    order = get_object_or_404(
        Order.objects.select_related("user", "shipping_address").prefetch_related(
            "items",
            "items__variant",
            "items__variant__images",
        ),
        id=order_id,
    )

    status_steps =["CONFIRMED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED"]
    final_statuses = ["DELIVERED", "CANCELLED", "RETURNED"]
    

    current_index = status_steps.index(order.status) if order.status in status_steps else -1

    timeline = []
    for index, step in enumerate(status_steps):
        timeline.append({
            "key": step,
            "label": step.replace("_", " ").title(),
            "completed": index <= current_index,
        })

    allowed_status_choices = []

    if order.status not in final_statuses and order.status in status_steps:
        allowed_statuses = status_steps[current_index:]
        allowed_status_choices = [
            (value, label)
            for value, label in Order.STATUS_CHOICES
            if value in allowed_statuses
        ]

    return render(request, "adminpanel/admin_order/admin_order_detail.html", {
        "order": order,
        "items": order.items.all(),
        "timeline": timeline,
        "status_choices": allowed_status_choices,
        "final_statuses": final_statuses,
    })
    
    

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
def process_refund(request, return_id):
    return_request = get_object_or_404(ReturnRequest, id=return_id)

    if return_request.status != "PICKED_UP":
        messages.error(request, "Refund can be processed only after product is picked up.")
        return redirect("admin_return_detail", return_id=return_request.id)

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

    messages.success(request, "Refund processed successfully.")
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
def mark_return_picked_up(request, return_id):
    return_request = get_object_or_404(ReturnRequest, id=return_id)

    if return_request.status != "APPROVED":
        messages.error(request, "Only approved returns can be picked up.")
        return redirect("admin_return_detail", return_id=return_request.id)

    return_request.status = "PICKED_UP"
    return_request.picked_up_at = timezone.now()

    return_request.save(update_fields=[
        "status",
        "picked_up_at",
        "updated_at",
    ])

    messages.success(request, "Return marked as picked up.")
    return redirect("admin_return_detail", return_id=return_request.id)