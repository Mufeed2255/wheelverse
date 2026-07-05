from decimal import Decimal

from django.db import transaction
from django.db.models import F

from .models import Wallet, WalletTransaction


@transaction.atomic
def get_or_create_wallet(user):
    wallet, created = Wallet.objects.select_for_update().get_or_create(user=user)
    return wallet


@transaction.atomic
def credit_wallet(user, amount, purpose, order=None, return_request=None, description="", reference=None):
    amount = Decimal(amount)

    if amount <= 0:
        raise ValueError("Credit amount must be greater than zero.")

    wallet = get_or_create_wallet(user)

    if reference and WalletTransaction.objects.filter(reference=reference).exists():
        return WalletTransaction.objects.get(reference=reference)

    Wallet.objects.filter(id=wallet.id).update(balance=F("balance") + amount)
    wallet.refresh_from_db()

    txn = WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        return_request=return_request,
        transaction_type="CREDIT",
        purpose=purpose,
        amount=amount,
        status="COMPLETED",
        description=description,
        reference=reference,
    )

    return txn


@transaction.atomic
def debit_wallet(user, amount, purpose, order=None, description="", reference=None):
    amount = Decimal(amount)

    if amount <= 0:
        raise ValueError("Debit amount must be greater than zero.")

    wallet = get_or_create_wallet(user)

    if wallet.balance < amount:
        raise ValueError("Insufficient wallet balance.")

    if reference and WalletTransaction.objects.filter(reference=reference).exists():
        return WalletTransaction.objects.get(reference=reference)

    Wallet.objects.filter(id=wallet.id).update(balance=F("balance") - amount)
    wallet.refresh_from_db()

    txn = WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        transaction_type="DEBIT",
        purpose=purpose,
        amount=amount,
        status="COMPLETED",
        description=description,
        reference=reference,
    )

    return txn