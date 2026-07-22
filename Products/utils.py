from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from adminpanel.models import Offer
from adminpanel.services.offers import build_cart_offer_summary

from .models import Cart

from Accounts.utils import is_ajax_request  # noqa: F401


def attach_collection_offer_badge(products):
    """Attaches `.offer_badge`, `.offer_title`, `.offer_discount_amount`
    to each product in `products` based on the best currently-active
    PRODUCT or CATEGORY offer."""
    today = timezone.localdate()
    product_ids = [product.id for product in products]
    category_ids = {product.category_id for product in products if product.category_id}

    active_offers = (
        Offer.objects
        .filter(is_active=True, is_deleted=False, start_date__lte=today, end_date__gte=today)
        .filter(Q(offer_type="PRODUCT", product_id__in=product_ids) | Q(offer_type="CATEGORY", category_id__in=category_ids))
        .select_related("product", "category")
    )

    product_offer_map = {}
    category_offer_map = {}

    for offer in active_offers:
        if offer.offer_type == "PRODUCT" and offer.product_id:
            product_offer_map.setdefault(offer.product_id, []).append(offer)
        elif offer.offer_type == "CATEGORY" and offer.category_id:
            category_offer_map.setdefault(offer.category_id, []).append(offer)

    for product in products:
        product.offer_badge = ""
        product.offer_title = ""
        product.offer_discount_amount = Decimal("0.00")

        base_price = product.min_price
        if base_price is None or base_price <= 0:
            continue

        candidates = product_offer_map.get(product.id, []) + category_offer_map.get(product.category_id, [])

        best_offer = None
        best_discount_amount = Decimal("0.00")

        for offer in candidates:
            if offer.discount_type == "PERCENTAGE":
                discount_amount = base_price * offer.discount_value / Decimal("100")
            else:
                discount_amount = min(offer.discount_value, base_price)

            discount_amount = max(discount_amount, Decimal("0.00")).quantize(Decimal("0.01"))

            if discount_amount > best_discount_amount:
                best_offer = offer
                best_discount_amount = discount_amount

        if not best_offer:
            continue

        product.offer_title = best_offer.title
        product.offer_discount_amount = best_discount_amount

        if best_offer.discount_type == "PERCENTAGE":
            value = best_offer.discount_value.quantize(Decimal("0.01"))
            value_text = str(int(value)) if value == value.to_integral() else format(value.normalize(), "f")
            product.offer_badge = f"{value_text}% OFF"
        else:
            value = best_offer.discount_value.quantize(Decimal("0.01"))
            value_text = str(int(value)) if value == value.to_integral() else format(value, ".2f")
            product.offer_badge = f"\u20b9{value_text} OFF"


def get_cart_totals(user):
    """Computes cart items + offer-adjusted totals for a user. Shared by
    cart_view and the AJAX increase/decrease/remove cart endpoints, which
    previously each recomputed this inline."""
    cart_items = list(
        Cart.objects.filter(user=user, variant__is_active=True, variant__is_deleted=False)
        .select_related("variant", "variant__product", "variant__product__category")
        .prefetch_related("variant__images")
        .order_by("-created_at")
    )

    offer_summary = build_cart_offer_summary(cart_items)

    for line in offer_summary["lines"]:
        line["cart_item"].offer_data = line

    original_subtotal = offer_summary["original_subtotal"]
    offer_discount = offer_summary["offer_discount"]
    subtotal_after_offer = offer_summary["subtotal_after_offer"]

    shipping = Decimal("80.00") if subtotal_after_offer > 0 else Decimal("0.00")
    grand_total = subtotal_after_offer + shipping

    return {
        "cart_items": cart_items,
        "original_subtotal": original_subtotal,
        "offer_discount": offer_discount,
        "subtotal_after_offer": subtotal_after_offer,
        "shipping": shipping,
        "grand_total": grand_total,
        "cart_count": len(cart_items),
    }


def cart_ajax_response(cart_item, totals):
    current_line = next((line for line in totals["cart_items"] if line.id == cart_item.id), None)

    if current_line is None:
        return {"success": False, "message": "Cart item not found."}

    offer_data = current_line.offer_data

    return {
        "success": True,
        "item_id": current_line.id,
        "quantity": current_line.quantity,
        "unit_original_price": f'{offer_data["original_unit_price"]:.2f}',
        "unit_final_price": f'{offer_data["final_unit_price"]:.2f}',
        "item_original_total": f'{offer_data["original_line_total"]:.2f}',
        "item_offer_discount": f'{offer_data["line_offer_discount"]:.2f}',
        "item_final_total": f'{offer_data["final_line_total"]:.2f}',
        "offer_title": offer_data["offer_title"],
        "has_offer": offer_data["line_offer_discount"] > 0,
        "subtotal": f'{totals["original_subtotal"]:.2f}',
        "offer_discount": f'{totals["offer_discount"]:.2f}',
        "subtotal_after_offer": f'{totals["subtotal_after_offer"]:.2f}',
        "shipping": f'{totals["shipping"]:.2f}',
        "grand_total": f'{totals["grand_total"]:.2f}',
        "cart_count": totals["cart_count"],
    }