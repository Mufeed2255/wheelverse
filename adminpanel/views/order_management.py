import csv

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from Orders.models import Order


@staff_member_required(login_url="admin_login")
def admin_orders(request):
    orders = (
        Order.objects
        .select_related("user", "shipping_address")
        .prefetch_related("items", "items__variant", "items__variant__images")
        .order_by("-ordered_at")
    )

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "all").strip()
    payment_method = request.GET.get("payment_method", "all").strip()

    if search:
        orders = orders.filter(
            Q(order_id__icontains=search) |
            Q(user__username__icontains=search) |
            Q(user__email__icontains=search) |
            Q(shipping_address__full_name__icontains=search) |
            Q(shipping_address__email__icontains=search)
        )

    if status != "all":
        orders = orders.filter(status=status)

    if payment_method != "all":
        orders = orders.filter(payment_method=payment_method)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="wheelverse_orders.csv"'

        writer = csv.writer(response)
        writer.writerow(["Order ID", "Customer", "Email", "Amount", "Date", "Status", "Payment Method"])

        for order in orders:
            address = getattr(order, "shipping_address", None)
            writer.writerow([
                order.order_id,
                address.full_name if address else order.user.username,
                address.email if address else order.user.email,
                order.total_amount,
                order.ordered_at.strftime("%Y-%m-%d"),
                order.status,
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

    status_steps = ["PENDING", "CONFIRMED", "SHIPPED", "DELIVERED"]
    current_index = status_steps.index(order.status) if order.status in status_steps else -1

    timeline = []
    for index, step in enumerate(status_steps):
        timeline.append({
            "key": step,
            "label": step.replace("_", " ").title(),
            "completed": index <= current_index,
        })

    return render(request, "adminpanel/admin_order/admin_order_detail.html",{
        "order": order,
        "items": order.items.all(),
        "timeline": timeline,
        "status_choices": Order.STATUS_CHOICES,
    })


@staff_member_required(login_url="admin_login")
def admin_update_order_status(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        new_status = request.POST.get("status")
        valid_statuses = [status[0] for status in Order.STATUS_CHOICES]

        if new_status in valid_statuses:
            order.status = new_status
            order.save(update_fields=["status", "updated_at"])
            messages.success(request, "Order status updated successfully.")
        else:
            messages.error(request, "Invalid order status.")

    return redirect("admin_order_detail", order_id=order.id)


@staff_member_required(login_url="admin_login")
def admin_cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":
        reason = request.POST.get("cancel_reason", "").strip()

        if not reason:
            messages.error(request, "Please enter cancel reason.")
            return redirect("admin_order_detail", order_id=order.id)

        if order.status in ["DELIVERED", "RETURNED", "CANCELLED"]:
            messages.error(request, "This order cannot be cancelled.")
            return redirect("admin_order_detail", order_id=order.id)

        order.status = "CANCELLED"
        order.cancel_reason = reason
        order.save(update_fields=["status", "cancel_reason", "updated_at"])
        messages.success(request, "Order cancelled successfully.")

    return redirect("admin_order_detail", order_id=order.id)