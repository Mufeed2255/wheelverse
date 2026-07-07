from decimal import Decimal

import razorpay

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Wallet, WalletTransaction


def get_razorpay_client():
    return razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )


def map_razorpay_method(method):
    method = (method or "").lower()

    if method == "card":
        return "CARD"
    if method == "upi":
        return "UPI"
    if method == "netbanking":
        return "NETBANKING"
    if method == "wallet":
        return "WALLET"
    if method == "paylater":
        return "PAY_LATER"

    return "RAZORPAY"


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


@login_required
def add_money(request):
    wallet, created = Wallet.objects.get_or_create(user=request.user)

    context = {
        "wallet": wallet,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "open_razorpay": False,
    }

    if request.method == "POST":
        amount_value = request.POST.get("amount", "").strip()

        try:
            amount = Decimal(amount_value)
        except Exception:
            messages.error(request, "Please enter a valid amount.")
            return redirect("add_money")

        if amount < Decimal("100"):
            messages.error(request, "Minimum add money amount is ₹100.")
            return redirect("add_money")

        if amount > Decimal("50000"):
            messages.error(request, "Maximum add money amount is ₹50,000.")
            return redirect("add_money")

        razorpay_amount = int(amount * 100)

        client = get_razorpay_client()

        razorpay_order = client.order.create({
            "amount": razorpay_amount,
            "currency": "INR",
            "payment_capture": 1,
        })

        wallet_txn = WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type="CREDIT",
            purpose="ADD_MONEY",
            payment_method="RAZORPAY",
            amount=amount,
            status="PENDING",
            description="Wallet top-up initiated via Razorpay.",
            reference=f"WALLET_TOPUP_{razorpay_order['id']}",
            razorpay_order_id=razorpay_order["id"],
        )

        context.update({
            "open_razorpay": True,
            "amount": amount,
            "razorpay_amount": razorpay_amount,
            "razorpay_order_id": razorpay_order["id"],
            "wallet_txn": wallet_txn,
        })

    return render(request, "add_money.html", context)


@login_required
@require_POST
@transaction.atomic
def verify_wallet_payment(request):
    wallet_txn = get_object_or_404(
        WalletTransaction.objects.select_for_update(),
        id=request.POST.get("wallet_txn_id"),
        wallet__user=request.user,
        purpose="ADD_MONEY",
    )

    if wallet_txn.status == "COMPLETED":
        messages.info(request, "Payment already completed.")
        return redirect("wallet_payment_success", txn_id=wallet_txn.id)

    razorpay_payment_id = request.POST.get("razorpay_payment_id")
    razorpay_order_id = request.POST.get("razorpay_order_id")
    razorpay_signature = request.POST.get("razorpay_signature")

    if razorpay_order_id != wallet_txn.razorpay_order_id:
        wallet_txn.status = "FAILED"
        wallet_txn.description = "Razorpay order mismatch."
        wallet_txn.save(update_fields=["status", "description"])
        messages.error(request, "Payment verification failed.")
        return redirect("wallet_payment_failed", txn_id=wallet_txn.id)

    client = get_razorpay_client()

    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        })
    except Exception:
        wallet_txn.status = "FAILED"
        wallet_txn.description = "Payment signature verification failed."
        wallet_txn.save(update_fields=["status", "description"])
        messages.error(request, "Payment verification failed.")
        return redirect("wallet_payment_failed", txn_id=wallet_txn.id)

    try:
        payment = client.payment.fetch(razorpay_payment_id)
        payment_method = map_razorpay_method(payment.get("method"))
    except Exception:
        payment_method = "RAZORPAY"

    Wallet.objects.filter(id=wallet_txn.wallet.id).update(
        balance=F("balance") + wallet_txn.amount
    )

    wallet_txn.status = "COMPLETED"
    wallet_txn.payment_method = payment_method
    wallet_txn.razorpay_payment_id = razorpay_payment_id
    wallet_txn.razorpay_signature = razorpay_signature
    wallet_txn.description = f"Wallet top-up completed using {payment_method.replace('_', ' ').title()}."
    wallet_txn.save(update_fields=[
        "status",
        "payment_method",
        "razorpay_payment_id",
        "razorpay_signature",
        "description",
    ])

    messages.success(request, f"₹{wallet_txn.amount} added to your wallet.")
    return redirect("wallet_payment_success", txn_id=wallet_txn.id)


@login_required
def wallet_payment_success(request, txn_id):
    txn = get_object_or_404(
        WalletTransaction,
        id=txn_id,
        wallet__user=request.user,
        purpose="ADD_MONEY",
    )

    return render(request, "wallet_payment_success.html", {
        "txn": txn,
        "amount": txn.amount,
        "wallet": txn.wallet,
    })


@login_required
def wallet_payment_failed(request, txn_id):
    txn = get_object_or_404(
        WalletTransaction,
        id=txn_id,
        wallet__user=request.user,
        purpose="ADD_MONEY",
    )

    if txn.status == "PENDING":
        txn.status = "FAILED"
        txn.description = "Payment cancelled or failed."
        txn.save(update_fields=["status", "description"])

    return render(request, "wallet_payment_failed.html", {
        "txn": txn,
        "amount": txn.amount,
    })