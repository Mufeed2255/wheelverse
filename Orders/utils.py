from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Sum

from Accounts.utils import validate_address_data
from Wallet.models import Wallet, WalletTransaction
from adminpanel.models import Product as AdminProduct

TWO_PLACES = Decimal("0.01")


def q(value):
    """Quantize a Decimal to 2 places, safely handling None."""
    if value is None:
        value = Decimal("0.00")
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# Address validation (checkout's quick-add-address form)

def validate_checkout_address(data):

    is_valid, _cleaned, _field, message = validate_address_data(data, allow_garage=False)
    return is_valid, (message or "")


# Coupons
def calculate_coupon_discount(coupon, subtotal):
    if subtotal < coupon.min_cart_amount:
        return Decimal("0.00")

    if coupon.discount_type == "PERCENTAGE":
        discount = (subtotal * coupon.discount_value) / Decimal("100")
        if coupon.max_discount_amount > 0:
            discount = min(discount, coupon.max_discount_amount)
        return q(discount)

    return q(min(coupon.discount_value, subtotal))


def refund_order_amount_to_wallet(order, amount, reference):
    """Credits `amount` to the order owner's wallet, guarded by a unique
    `reference` so retries/duplicate calls can never double-refund.
    Never refunds COD orders (nothing was pre-paid)."""
    if amount <= 0:
        return False

    if order.payment_method == "COD":
        return False

    if WalletTransaction.objects.filter(reference=reference).exists():
        return False

    wallet, _ = Wallet.objects.select_for_update().get_or_create(user=order.user)
    wallet.balance += amount
    wallet.save(update_fields=["balance", "updated_at"])

    WalletTransaction.objects.create(
        wallet=wallet,
        order=order,
        transaction_type="CREDIT",
        purpose="CANCEL_REFUND",
        payment_method=order.payment_method,
        amount=amount,
        status="COMPLETED",
        description=f"Cancel refund for order {order.order_id}",
        reference=reference,
    )
    return True


# ---------------------------------------------------------------------------
# Stock resync (previously a copy-pasted closure in 3 different views)
# ---------------------------------------------------------------------------
def sync_products_total_stock(product_ids, *, active_only=False):
    """Recomputes AdminProduct.total_stock from the sum of its variants'
    stock. Pass this to `transaction.on_commit` after adjusting variant
    stock so the cached total stays correct.

    active_only=True also filters on variant.is_active (used by the
    cancellation flows, which only want to count sellable variants).
    """
    for product_id in product_ids:
        product = AdminProduct.objects.get(id=product_id)
        variants = product.variants.filter(is_deleted=False)
        if active_only:
            variants = variants.filter(is_active=True)
        total_stock = variants.aggregate(total=Sum("stock"))["total"] or 0
        product.total_stock = total_stock
        product.save(update_fields=["total_stock"])


# ---------------------------------------------------------------------------
# Returns
# ---------------------------------------------------------------------------
VALID_RETURN_REASONS = [
    "Damaged Product",
    "Wrong Product Received",
    "Product Quality Issue",
    "Missing Parts",
    "Other",
]


def get_item_returned_qty(order_item):
    if hasattr(order_item, "return_request"):
        if order_item.return_request.status != "REJECTED":
            return order_item.quantity
    return 0


ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/jpg", "image/webp"]
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB


def validate_images(images, *, required=True):
    """Shared image-upload validation for return proofs and review photos.
    `required=True` (returns) demands at least one image;
    `required=False` (reviews) allows zero images but still validates any
    that are present."""
    if not images:
        return "Please upload at least one return proof image." if required else None

    if len(images) > 5:
        return "Maximum 5 images allowed."

    for image in images:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            return "Only JPG, PNG, and WEBP images are allowed."
        if image.size > MAX_IMAGE_SIZE:
            return "Each image must be less than 5MB."

    return None


def validate_return_images(images):
    return validate_images(images, required=True)


def refunded_qty_and_amount(order_item):
    """Sum up quantity + amount that has actually been refunded for this
    item (status == REFUNDED). PICKED_UP / APPROVED are "in progress" and
    should NOT reduce the invoice yet â€” only a completed refund changes
    the money the customer owes."""
    refunded = order_item.order_return_requests.filter(status="REFUNDED")
    refunded_qty = sum(r.return_quantity for r in refunded)
    refunded_amount = sum((r.refund_amount or Decimal("0.00")) for r in refunded)
    return refunded_qty, q(refunded_amount)


def pending_return_qty(order_item):
    """Quantity that is requested/approved/picked-up but not yet refunded."""
    pending = order_item.order_return_requests.filter(status__in=["REQUESTED", "APPROVED", "PICKED_UP"])
    return sum(r.return_quantity for r in pending)


def item_line_status(order_item, refunded_qty, pending_qty):
    if order_item.is_cancelled and order_item.cancelled_quantity >= order_item.quantity:
        return "Cancelled"
    if refunded_qty >= order_item.quantity:
        return "Returned & Refunded"
    if pending_qty > 0:
        return "Return In Progress"
    if order_item.cancelled_quantity > 0:
        return "Partially Cancelled"
    if refunded_qty > 0:
        return "Partially Returned"
    return "Active"