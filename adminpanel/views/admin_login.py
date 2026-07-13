from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models.functions import Coalesce, TruncDate, TruncMonth
from django.utils import timezone
from Orders.models import Order, OrderItem

from calendar import month_abbr
from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DecimalField,
    IntegerField,
    Sum,
    Value,
)

User = get_user_model()



def admin_login(request):

    if request.user.is_authenticated:
        if request.session.get("login_type") == "user":
            return redirect("landing_page")

        if request.user.is_staff or request.user.is_superuser:
            return redirect("admin_dashboard")

        logout(request)
        return redirect("admin_login")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        if not username or not password:
            messages.error(request, "Username and Password are required.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid username or password.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        if not user.is_active:
            messages.error(request, "This account has been deactivated.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        if not (user.is_staff or user.is_superuser):
            messages.error(request, "Access denied. Admin login only.")
            return render(request, "adminpanel/admin_login/admin_login.html")

        login(request, user)
        request.session["login_type"] = "admin"


        messages.success(request, "Welcome to the Admin Dashboard.")
        return redirect("admin_dashboard")

    return render(request, "adminpanel/admin_login/admin_login.html")




def _shift_month(year, month, offset):
    absolute_month = (year * 12 + (month - 1)) + offset

    return (
        absolute_month // 12,
        absolute_month % 12 + 1,
    )


@login_required(login_url="admin_login")
def admin_dashboard(request):
    if not (
        request.user.is_staff
        or request.user.is_superuser
    ):
        logout(request)

        messages.error(
            request,
            "You are not authorized to access the admin panel."
        )

        return redirect("admin_login")

    today = timezone.localdate()

    performance_period = request.GET.get(
        "performance",
        "weekly"
    ).strip().lower()

    if performance_period not in {
        "weekly",
        "monthly",
    }:
        performance_period = "weekly"

#costomer counts

    customers = User.objects.filter(
        is_staff=False,
        is_superuser=False,
    )

    total_users = customers.count()

    active_users = customers.filter(
        is_active=True
    ).count()

    inactive_users = customers.filter(
        is_active=False
    ).count()

    recent_signups = customers.order_by(
        "-date_joined"
    )[:5]

#order counts

    total_orders = Order.objects.count()

    completed_orders = Order.objects.filter(
        status="DELIVERED"
    ).count()

    pending_orders = Order.objects.filter(
        status__in=[
            "PENDING",
            "CONFIRMED",
            "SHIPPED",
            "OUT_FOR_DELIVERY",
        ]
    ).count()

#recent orders

    recent_orders = list(
        Order.objects
        .select_related(
            "user",
            "shipping_address",
        )
        .prefetch_related(
            "items",
            "items__variant",
            "items__variant__product",
            "items__variant__product__category",
        )
        .order_by("-ordered_at")[:6]
    )

    for order in recent_orders:
        product_names = []

        for item in order.items.all():
            if item.variant and item.variant.product:
                product_name = item.variant.product.name
            else:
                product_name = item.product_name

            if product_name and product_name not in product_names:
                product_names.append(product_name)

        if not product_names:
            order.dashboard_product_names = "No product"
        elif len(product_names) == 1:
            order.dashboard_product_names = product_names[0]
        else:
            order.dashboard_product_names = (
                f"{product_names[0]} +{len(product_names) - 1} more"
            )

        address = getattr(order, "shipping_address", None)

        if address and address.full_name:
            order.dashboard_customer_name = address.full_name
        elif order.user.get_full_name():
            order.dashboard_customer_name = order.user.get_full_name()
        else:
            order.dashboard_customer_name = order.user.username

#delivered sales items

    delivered_items = (
        OrderItem.objects
        .filter(
            order__status="DELIVERED",
            is_cancelled=False,
        )
        .select_related(
            "order",
            "variant",
            "variant__product",
            "variant__product__category",
        )
    )

#momthly performance

    if performance_period == "monthly":
        month_pairs = [
            _shift_month(
                today.year,
                today.month,
                offset
            )
            for offset in range(-11, 1)
        ]

        first_year, first_month = month_pairs[0]

        performance_start = timezone.datetime(
            first_year,
            first_month,
            1,
        ).date()

        monthly_rows = (
            delivered_items
            .filter(
                order__ordered_at__date__gte=(
                    performance_start
                )
            )
            .annotate(
                period=TruncMonth(
                    "order__ordered_at"
                )
            )
            .values("period")
            .annotate(
                revenue=Coalesce(
                    Sum("item_total"),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2,
                    ),
                ),

                orders=Count(
                    "order_id",
                    distinct=True,
                ),
            )
            .order_by("period")
        )

        monthly_map = {
            (
                row["period"].year,
                row["period"].month,
            ): row
            for row in monthly_rows
            if row["period"]
        }

        performance_labels = [
            (
                f"{month_abbr[month]} "
                f"{str(year)[-2:]}"
            )
            for year, month in month_pairs
        ]

        performance_revenue = [
            float(
                monthly_map.get(
                    (year, month),
                    {}
                ).get(
                    "revenue",
                    Decimal("0.00")
                )
                or Decimal("0.00")
            )
            for year, month in month_pairs
        ]

        performance_orders = [
            int(
                monthly_map.get(
                    (year, month),
                    {}
                ).get("orders", 0)
                or 0
            )
            for year, month in month_pairs
        ]

        performance_title = (
            "Monthly Performance"
        )

        performance_subtitle = (
            "Delivered sales during the "
            "last 12 months"
        )

#weekly performance

    else:
        performance_start = (
            today - timedelta(days=6)
        )

        week_dates = [
            performance_start
            + timedelta(days=index)
            for index in range(7)
        ]

        weekly_rows = (
            delivered_items
            .filter(
                order__ordered_at__date__range=[
                    performance_start,
                    today,
                ]
            )
            .annotate(
                period=TruncDate(
                    "order__ordered_at"
                )
            )
            .values("period")
            .annotate(
                revenue=Coalesce(
                    Sum("item_total"),
                    Value(Decimal("0.00")),
                    output_field=DecimalField(
                        max_digits=15,
                        decimal_places=2,
                    ),
                ),

                orders=Count(
                    "order_id",
                    distinct=True,
                ),
            )
            .order_by("period")
        )

        weekly_map = {
            row["period"]: row
            for row in weekly_rows
            if row["period"]
        }

        performance_labels = [
            date_value.strftime("%a")
            for date_value in week_dates
        ]

        performance_revenue = [
            float(
                weekly_map.get(
                    date_value,
                    {}
                ).get(
                    "revenue",
                    Decimal("0.00")
                )
                or Decimal("0.00")
            )
            for date_value in week_dates
        ]

        performance_orders = [
            int(
                weekly_map.get(
                    date_value,
                    {}
                ).get("orders", 0)
                or 0
            )
            for date_value in week_dates
        ]

        performance_title = (
            "Weekly Performance"
        )

        performance_subtitle = (
            "Delivered sales during the "
            "last 7 days"
        )

#catagory performance

    category_start = today - timedelta(days=29)

    category_rows = list(
        delivered_items
        .filter(
            order__ordered_at__date__range=[
                category_start,
                today,
            ],
            variant__isnull=False,
            variant__product__isnull=False,
            variant__product__category__isnull=False,
        )
        .values(
            "variant__product__category_id",
            "variant__product__category__name",
        )
        .annotate(
            revenue=Coalesce(
                Sum("item_total"),
                Value(Decimal("0.00")),
                output_field=DecimalField(
                    max_digits=15,
                    decimal_places=2,
                ),
            ),
            quantity=Coalesce(
                Sum("quantity"),
                Value(0),
                output_field=IntegerField(),
            ),
            orders=Count(
                "order_id",
                distinct=True,
            ),
        )
        .order_by("-revenue")[:6]
    )

    category_labels = [
        row["variant__product__category__name"]
        for row in category_rows
    ]

    category_revenue = [
        float(row["revenue"] or 0)
        for row in category_rows
    ]

    category_quantity = [
        int(row["quantity"] or 0)
        for row in category_rows
    ]

#total revenue(delivered)

    total_revenue = delivered_items.aggregate(
        total=Coalesce(
            Sum("item_total"),
            Value(Decimal("0.00")),
            output_field=DecimalField(
                max_digits=15,
                decimal_places=2,
            ),
        )
    )["total"]

    context = {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,

        "total_orders": total_orders,
        "completed_orders": completed_orders,
        "pending_orders": pending_orders,
        "total_revenue": total_revenue,

        "recent_signups": recent_signups,
        "recent_orders": recent_orders,

        "performance_period": performance_period,
        "performance_title": performance_title,
        "performance_subtitle": (
            performance_subtitle
        ),
        "performance_labels": (
            performance_labels
        ),
        "performance_revenue": (
            performance_revenue
        ),
        "performance_orders": (
            performance_orders
        ),

        "category_labels": category_labels,
        "category_revenue": category_revenue,
        "category_quantity": category_quantity,
    }

    return render(
        request,
        "adminpanel/admin_login/admin_dashboard.html",
        context,
    )

@login_required(login_url="admin_login")
def admin_logout_view(request):
    logout(request)
    messages.success(request, "Admin logged out successfully.")
    return redirect("admin_login")