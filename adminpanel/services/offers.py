from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Q
from django.utils import timezone

from adminpanel.models import Offer


MONEY = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(
        MONEY,
        rounding=ROUND_HALF_UP
    )


def calculate_offer_discount(offer, price):
    price = money(price)

    if not offer or price <= 0:
        return Decimal("0.00")

    if offer.discount_type == "PERCENTAGE":
        discount = (
            price * Decimal(offer.discount_value)
        ) / Decimal("100")
    else:
        discount = Decimal(offer.discount_value)

    return min(
        money(discount),
        price
    )


def get_best_offer_for_variant(variant):
    """
    Check both product and category offers.

    The offer giving the highest rupee discount is applied.
    """

    today = timezone.localdate()
    original_price = money(variant.price)

    offers = (
        Offer.objects
        .filter(
            is_active=True,
            is_deleted=False,
            start_date__lte=today,
            end_date__gte=today,
        )
        .filter(
            Q(
                offer_type="PRODUCT",
                product_id=variant.product_id,
            )
            |
            Q(
                offer_type="CATEGORY",
                category_id=variant.product.category_id,
            )
        )
        .select_related(
            "product",
            "category",
        )
    )

    best_offer = None
    best_discount = Decimal("0.00")

    for offer in offers:
        discount = calculate_offer_discount(
            offer,
            original_price
        )

        if discount > best_discount:
            best_offer = offer
            best_discount = discount

    final_price = money(
        original_price - best_discount
    )

    return {
        "offer": best_offer,
        "offer_title": (
            best_offer.title
            if best_offer
            else ""
        ),
        "offer_type": (
            best_offer.offer_type
            if best_offer
            else ""
        ),
        "original_price": original_price,
        "discount_amount": best_discount,
        "final_price": final_price,
    }


def build_cart_offer_summary(cart_items):
    lines = []

    original_subtotal = Decimal("0.00")
    offer_discount = Decimal("0.00")
    subtotal_after_offer = Decimal("0.00")

    for cart_item in cart_items:
        offer_data = get_best_offer_for_variant(
            cart_item.variant
        )

        quantity = Decimal(cart_item.quantity)

        original_line_total = money(
            offer_data["original_price"] * quantity
        )

        line_offer_discount = money(
            offer_data["discount_amount"] * quantity
        )

        final_line_total = money(
            offer_data["final_price"] * quantity
        )

        line = {
            "cart_item": cart_item,
            "variant": cart_item.variant,
            "quantity": cart_item.quantity,

            "offer": offer_data["offer"],
            "offer_title": offer_data["offer_title"],
            "offer_type": offer_data["offer_type"],

            "original_unit_price": (
                offer_data["original_price"]
            ),

            "final_unit_price": (
                offer_data["final_price"]
            ),

            "unit_offer_discount": (
                offer_data["discount_amount"]
            ),

            "original_line_total": (
                original_line_total
            ),

            "line_offer_discount": (
                line_offer_discount
            ),

            "final_line_total": (
                final_line_total
            ),
        }

        lines.append(line)

        original_subtotal += original_line_total
        offer_discount += line_offer_discount
        subtotal_after_offer += final_line_total

    return {
        "lines": lines,

        "original_subtotal": money(
            original_subtotal
        ),

        "offer_discount": money(
            offer_discount
        ),

        "subtotal_after_offer": money(
            subtotal_after_offer
        ),
    }