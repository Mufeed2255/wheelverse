from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.shortcuts import render

from .models import Wallet, WalletTransaction


@login_required
def wallet_view(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)

    transactions = (
        WalletTransaction.objects
        .filter(wallet=wallet)
        .select_related("order", "return_request")
        .order_by("-created_at")
    )

    total_credit = transactions.filter(
        transaction_type="CREDIT",
        status="COMPLETED"
    ).aggregate(total=Sum("amount"))["total"] or 0

    total_debit = transactions.filter(
        transaction_type="DEBIT",
        status="COMPLETED"
    ).aggregate(total=Sum("amount"))["total"] or 0

    pending_refund = transactions.filter(
        transaction_type="CREDIT",
        purpose="RETURN_REFUND",
        status="PENDING"
    ).aggregate(total=Sum("amount"))["total"] or 0

    paginator = Paginator(transactions, 5)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "wallet.html", {
        "wallet": wallet,
        "page_obj": page_obj,
        "transactions": page_obj.object_list,
        "total_credit": total_credit,
        "total_debit": total_debit,
        "pending_refund": pending_refund,
    })