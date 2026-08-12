import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, Min, Prefetch, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from Orders.models import ProductReview
from adminpanel.models import Category, Product, ProductVariant
from adminpanel.models import Offer
from django.utils import timezone
from .models import Cart, Wishlist
from .utils import attach_collection_offer_badge, cart_ajax_response, get_cart_totals, is_ajax_request


MAX_QUANTITY_PER_PRODUCT = 5

def user_collections(request):
    search_query = request.GET.get("search", "").strip()
    category_id = request.GET.get("category", "").strip()
    status = request.GET.get("status", "").strip()
    sort_by = request.GET.get("sort_by", "newest").strip()
    rarity = request.GET.get("rarity", "").strip()
 
    try:
        price_min = max(int(request.GET.get("price_min", 0)), 0)
    except (ValueError, TypeError):
        price_min = 0
 
    try:
        price_max = max(int(request.GET.get("price_max", 150000)), 0)
    except (ValueError, TypeError):
        price_max = 150000
 
    if price_min > price_max:
        price_min, price_max = price_max, price_min
 
    active_variants = ProductVariant.objects.filter(
        is_active=True, is_deleted=False,
    ).prefetch_related("images").order_by("id")
 
    products_queryset = (
        Product.objects
        .filter(is_deleted=False, is_active=True)
        .select_related("category")
        .prefetch_related(Prefetch("variants", queryset=active_variants, to_attr="active_variants"))
        .annotate(min_price=Min("variants__price", filter=Q(variants__is_active=True, variants__is_deleted=False)))
    )
 
    categories = (
        Category.objects
        .filter(is_active=True)
        .annotate(total_items=Count("products", filter=Q(products__is_deleted=False, products__is_active=True), distinct=True))
        .order_by("name")
    )
 
    if search_query:
        products_queryset = products_queryset.filter(
            Q(name__icontains=search_query) | Q(category__name__icontains=search_query) | Q(sku__icontains=search_query)
        )
 
    if category_id:
        products_queryset = products_queryset.filter(category_id=category_id)
 
    if rarity:
        products_queryset = products_queryset.filter(rarity__iexact=rarity)
 
    products_queryset = products_queryset.filter(
        min_price__isnull=False, min_price__gte=price_min, min_price__lte=price_max,
    )
 
    sort_map = {
        "oldest": "id",
        "a-z": "name",
        "z-a": "-name",
        "price-low": ("min_price", "name"),
        "price-high": ("-min_price", "name"),
    }
 
    if sort_by in sort_map:
        order = sort_map[sort_by]
        products_queryset = products_queryset.order_by(*order) if isinstance(order, tuple) else products_queryset.order_by(order)
    else:
        sort_by = "newest"
        products_queryset = products_queryset.order_by("-id")
 
    products_list = list(products_queryset)
 
    if status == "in_stock":
        products_list = [p for p in products_list if p.total_stock > 10]
    elif status == "limited":
        products_list = [p for p in products_list if 0 < p.total_stock <= 10]
    elif status == "out_of_stock":
        products_list = [p for p in products_list if p.total_stock == 0]
 
    attach_collection_offer_badge(products_list)
 
    wishlisted_variant_ids = set()
    if request.user.is_authenticated:
        wishlisted_variant_ids = set(Wishlist.objects.filter(user=request.user).values_list("variant_id", flat=True))
 
    for product in products_list:
        for variant in getattr(product, "active_variants", []):
            variant.is_wishlisted = variant.id in wishlisted_variant_ids
 
    paginator = Paginator(products_list, 6)
    page_number = request.GET.get("page", 1)
 
    try:
        paginated_products = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)
 
    has_active_filters = bool(
        search_query or category_id or status or rarity or price_min > 0 or price_max < 150000
    )
 
    return render(request, "products/collections.html", {
        "products": paginated_products,
        "categories": categories,
        "total_products_count": len(products_list),
        "current_search": search_query,
        "current_category": category_id,
        "current_status": status,
        "current_sort": sort_by,
        "current_rarity": rarity,
        "price_min": price_min,
        "price_max": price_max,
        "rarity_choices": [("", "All Rarities")] + list(Product.RARITY_CHOICES),
        "has_active_filters": has_active_filters,
    })
 
 
@login_required
@require_POST
def toggle_wishlist(request, variant_id):
    """
    AJAX endpoint - reload illathe wishlist add/remove cheyyan.
    Returns JSON: {status: 'added'/'removed', message: '...'}
    """
    variant = get_object_or_404(ProductVariant, id=variant_id, is_deleted=False)
 
    wishlist_item, created = Wishlist.objects.get_or_create(
        user=request.user,
        variant=variant,
    )
 
    if not created:
        wishlist_item.delete()
        return JsonResponse({
            "status": "removed",
            "message": "Removed from wishlist",
            "variant_id": variant_id,
        })
 
    return JsonResponse({
        "status": "added",
        "message": "Added to wishlist",
        "variant_id": variant_id,
    })


def product_search_suggestions(request):
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"suggestions": []})

    active_variants = (
        ProductVariant.objects.filter(is_active=True, is_deleted=False)
        .prefetch_related("images").order_by("id")
    )

    products = (
        Product.objects
        .filter(is_deleted=False, is_active=True)
        .filter(Q(name__icontains=query) | Q(category__name__icontains=query) | Q(sku__icontains=query))
        .select_related("category")
        .prefetch_related(Prefetch("variants", queryset=active_variants, to_attr="active_variants"))
        .annotate(min_price=Min("variants__price", filter=Q(variants__is_active=True, variants__is_deleted=False)))
        .order_by("name")[:8]
    )

    suggestions = []
    for product in products:
        image_url = ""
        first_variant = product.active_variants[0] if product.active_variants else None

        if first_variant:
            first_image = first_variant.images.first()
            if first_image and first_image.image:
                image_url = first_image.image.url
            elif first_variant.image:
                image_url = first_variant.image.url

        suggestions.append({
            "id": product.id,
            "name": product.name,
            "category": product.category.name if product.category else "",
            "rarity": product.rarity,
            "price": f"{product.min_price:.2f}" if product.min_price is not None else "",
            "stock": product.total_stock,
            "image_url": image_url,
            "detail_url": reverse("product_detail", kwargs={"product_id": product.id}),
        })

    return JsonResponse({"suggestions": suggestions})


def get_best_offer_for_price(product, price):
    """Returns (offer, discount_amount) for the best applicable offer on this price, or (None, 0)."""
    today = timezone.localdate()

    offers = Offer.objects.filter(
        Q(offer_type="PRODUCT", product=product) |
        Q(offer_type="CATEGORY", category=product.category),
        is_active=True,
        is_deleted=False,
        start_date__lte=today,
        end_date__gte=today,
    )

    best_offer = None
    best_discount = Decimal("0.00")

    for offer in offers:
        if offer.discount_type == "PERCENTAGE":
            discount = (price * offer.discount_value / Decimal("100")).quantize(Decimal("0.01"))
        else:
            discount = min(offer.discount_value, price)

        if discount > best_discount:
            best_discount = discount
            best_offer = offer

    return best_offer, best_discount

def q(value):
    return value.quantize(Decimal("0.01"))

@login_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.filter(is_deleted=False, is_active=True).annotate(
            variant_stock=Sum("variants__stock", filter=Q(variants__is_active=True, variants__is_deleted=False)),
            min_variant_price=Min("variants__price", filter=Q(variants__is_active=True, variants__is_deleted=False)),
        ),
        id=product_id,
    )

    variants_list = list(
        ProductVariant.objects.filter(product=product, is_active=True, is_deleted=False)
        .prefetch_related("images").order_by("id")
    )

    wishlisted_variant_ids = set(
        Wishlist.objects.filter(user=request.user, variant__product=product).values_list("variant_id", flat=True)
    )

    for variant in variants_list:
        variant.image_urls_json = json.dumps([image.image.url for image in variant.images.all()])
        variant.is_wishlisted = variant.id in wishlisted_variant_ids

        offer, discount_amount = get_best_offer_for_price(product, variant.price)
        variant.applied_offer = offer
        variant.offer_discount_amount = discount_amount
        variant.offer_price = q(variant.price - discount_amount) if discount_amount > 0 else variant.price

        if offer and discount_amount > 0:
            if offer.discount_type == "PERCENTAGE":
                variant.offer_badge_text = f"{offer.discount_value:.0f}% OFF"
            else:
                variant.offer_badge_text = f"₹{discount_amount:.0f} OFF"
        else:
            variant.offer_badge_text = ""
            
    first_variant = variants_list[0] if variants_list else None

    cart_count = Cart.objects.filter(user=request.user, variant__is_active=True, variant__is_deleted=False).count()
    wishlist_count = Wishlist.objects.filter(user=request.user, variant__is_active=True, variant__is_deleted=False).count()

    reviews = (
        ProductReview.objects.filter(product=product, is_active=True)
        .select_related("user", "variant").prefetch_related("images")
        .order_by("-created_at")
    )

    review_count = reviews.count()
    average_rating = round(sum(r.rating for r in reviews) / review_count, 1) if review_count else 0

    return render(request, "products/product_detail.html", {
        "product": product,
        "variants": variants_list,
        "first_variant": first_variant,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
        "reviews": reviews,
        "review_count": review_count,
        "average_rating": average_rating,
        "max_quantity": MAX_QUANTITY_PER_PRODUCT,
    })
    
    
@login_required
@require_POST
def add_to_cart(request):
    variant_id = request.POST.get("variant_id", "").strip()
    quantity_value = request.POST.get("quantity", "1").strip()
    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id, is_active=True, is_deleted=False,
        product__is_active=True, product__is_deleted=False,
    )
    product = variant.product
    detail_redirect = redirect("product_detail", product_id=product.id)
    try:
        quantity = int(quantity_value)
    except (TypeError, ValueError):
        messages.error(request, "Invalid quantity.")
        return detail_redirect
    if quantity < 1:
        messages.error(request, "Quantity must be at least 1.")
        return detail_redirect
    if quantity > MAX_QUANTITY_PER_PRODUCT:
        messages.error(request, f"You can only order up to {MAX_QUANTITY_PER_PRODUCT} unit(s) of this product.")
        return detail_redirect
    if variant.stock <= 0:
        messages.error(request, "This variant is out of stock.")
        return detail_redirect
    if quantity > variant.stock:
        messages.error(request, f"Only {variant.stock} unit(s) are available.")
        return detail_redirect

    existing_cart_item = Cart.objects.filter(user=request.user, variant=variant).first()

    if existing_cart_item:
        Wishlist.objects.filter(user=request.user, variant=variant).delete()
        messages.info(request, "This variant is already in your cart. It was removed from your wishlist.")
        return detail_redirect

    Cart.objects.create(user=request.user, variant=variant, quantity=quantity)
    Wishlist.objects.filter(user=request.user, variant=variant).delete()

    messages.success(request, "Product added to cart successfully.")
    return detail_redirect


@login_required
def cart_view(request):
    totals = get_cart_totals(request.user)

    return render(request, "products/cart.html", {
        "cart_items": totals["cart_items"],
        "subtotal": totals["original_subtotal"],
        "offer_discount": totals["offer_discount"],
        "subtotal_after_offer": totals["subtotal_after_offer"],
        "shipping": totals["shipping"],
        "grand_total": totals["grand_total"],
        "cart_count": totals["cart_count"],
    })


@login_required
@require_POST
def increase_cart_item(request, item_id):
    cart_item = get_object_or_404(
        Cart.objects.select_related("variant", "variant__product", "variant__product__category"),
        id=item_id, user=request.user,
    )
    effective_limit = min(cart_item.variant.stock, MAX_QUANTITY_PER_PRODUCT)
    if cart_item.quantity >= effective_limit:
        message=(
            "Stock unavailable."
            if cart_item.variant.stock <= MAX_QUANTITY_PER_PRODUCT
            else f"You can only order up to {MAX_QUANTITY_PER_PRODUCT} unit(s) of this product."
        )

        if is_ajax_request(request):
            return JsonResponse({"success": False, "message": message})
        messages.error(request, message)
        return redirect("cart")
    cart_item.quantity += 1
    cart_item.save(update_fields=["quantity"])

    totals = get_cart_totals(request.user)

    if is_ajax_request(request):
        return JsonResponse(cart_ajax_response(cart_item, totals))

    messages.success(request, "Cart updated successfully.")
    return redirect("cart")


@login_required
@require_POST
def decrease_cart_item(request, item_id):
    cart_item = get_object_or_404(
        Cart.objects.select_related("variant", "variant__product", "variant__product__category"),
        id=item_id, user=request.user,
    )

    if cart_item.quantity <= 1:
        if is_ajax_request(request):
            return JsonResponse({
                "success": False,
                "message": "Minimum quantity is 1"
            })

        messages.error(request, "Minimum quantity is 1.")
        return redirect("cart")

    cart_item.quantity -= 1
    cart_item.save(update_fields=["quantity"])

    totals = get_cart_totals(request.user)

    if is_ajax_request(request):
        return JsonResponse(cart_ajax_response(cart_item, totals))

    messages.success(request, "Cart updated successfully.")
    return redirect("cart")


@login_required
@require_POST
def remove_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
    cart_item.delete()

    if is_ajax_request(request):
        totals = get_cart_totals(request.user)
        return JsonResponse({
            "success": True,
            "removed_item_id": item_id,
            "subtotal": f'{totals["original_subtotal"]:.2f}',
            "offer_discount": f'{totals["offer_discount"]:.2f}',
            "subtotal_after_offer": f'{totals["subtotal_after_offer"]:.2f}',
            "shipping": f'{totals["shipping"]:.2f}',
            "grand_total": f'{totals["grand_total"]:.2f}',
            "cart_count": totals["cart_count"],
            "cart_empty": totals["cart_count"] == 0,
        })

    messages.success(request, "Product removed from cart.")
    return redirect("cart")


@login_required
def wishlist_view(request):
    wishlist_items = Wishlist.objects.filter(
        user=request.user, variant__is_active=True, variant__is_deleted=False,
    ).order_by("-created_at")

    wishlist_value = sum(item.variant.price for item in wishlist_items)
    available_stock = sum(item.variant.stock for item in wishlist_items)

    cart_count = Cart.objects.filter(user=request.user, variant__is_active=True, variant__is_deleted=False).count()
    wishlist_count = wishlist_items.count()

    return render(request, "products/wishlist.html", {
        "wishlist_items": wishlist_items,
        "wishlist_value": wishlist_value,
        "available_stock": available_stock,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
    })


@login_required
@require_POST
def add_to_wishlist(request):
    variant_id = request.POST.get("variant_id", "").strip()
    next_url = request.POST.get("next", "").strip()

    fallback_url = reverse("collections")

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        redirect_url = next_url
    else:
        redirect_url = fallback_url

    if not variant_id:
        messages.error(request, "Variant not selected.")
        return redirect(redirect_url)

    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id, is_active=True, is_deleted=False,
        product__is_active=True, product__is_deleted=False,
    )

    wishlist_item = Wishlist.objects.filter(user=request.user, variant=variant).first()

    if wishlist_item:
        wishlist_item.delete()
        messages.success(request, "Product removed from wishlist.")
        return redirect(redirect_url)

    if Cart.objects.filter(user=request.user, variant=variant).exists():
        messages.info(request, "This variant is already in your cart.")
        return redirect(redirect_url)

    Wishlist.objects.create(user=request.user, variant=variant)
    messages.success(request, "Product added to wishlist.")
    return redirect(redirect_url)


@login_required
def remove_wishlist(request, item_id):
    item = get_object_or_404(Wishlist, id=item_id, user=request.user)
    item.delete()
    messages.success(request, "Product removed from wishlist.")
    return redirect("wishlist")


@login_required
def move_wishlist_to_cart(request, item_id):
    item = get_object_or_404(Wishlist, id=item_id, user=request.user)
    variant = item.variant

    if variant.stock <= 0:
        messages.error(request, "Stock unavailable.")
        return redirect("wishlist")

    if Cart.objects.filter(user=request.user, variant=variant).exists():
        item.delete()
        messages.error(request, "This product is already in your cart. Removed from wishlist.")
        return redirect("wishlist")

    Cart.objects.create(user=request.user, variant=variant, quantity=1)
    item.delete()

    messages.success(request, "Product moved to cart.")
    return redirect("cart")