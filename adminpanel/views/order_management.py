import csv
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render

from Orders.models import Order  


@staff_member_required(login_url="admin_login")
def admin_orders(request):
    orders = Order.objects.select_related("user").order_by("-created_at")

    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "all").strip()
    payment_method = request.GET.get("payment_method", "all").strip()

    if search:
        orders = orders.filter(
            Q(order_id__icontains=search) |
            Q(user__full_name__icontains=search) |
            Q(user__email__icontains=search) |
            Q(id__icontains=search)
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
            writer.writerow([
                getattr(order, "order_id", f"#WLV-{order.id}"),
                getattr(order.user, "full_name", order.user.username),
                order.user.email,
                getattr(order, "total_amount", getattr(order, "total", 0)),
                order.created_at.strftime("%Y-%m-%d"),
                order.status,
                order.payment_method,
            ])

        return response

    paginator = Paginator(orders, 8)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search": search,
        "current_status": status,
        "current_payment_method": payment_method,
        "total_orders": paginator.count,
    }

    return render(request, "adminpanel/orders/admin_orders.html", context)