from Orders.models import ProductReview

from itertools import product

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Count, Q, Min ,Prefetch
from adminpanel.models import Product, Category, ProductVariant
from Products.models import Cart, Wishlist
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from decimal import Decimal
from Orders.models import ProductReview
from adminpanel.services.offers import build_cart_offer_summary
import json
from django.shortcuts import get_object_or_404, render
from django.db.models import Sum, Min
from adminpanel.models import Product, ProductVariant
from Products.models import Cart, Wishlist
from Orders.models import ProductReview
from adminpanel.services.offers import build_cart_offer_summary

from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

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
        is_active=True,
        is_deleted=False,
    ).prefetch_related("images").order_by("id")

    products_queryset = (
        Product.objects
        .filter(is_deleted=False, is_active=True)
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=active_variants,
                to_attr="active_variants",
            )
        )
        .annotate(
            min_price=Min(
                "variants__price",
                filter=Q(
                    variants__is_active=True,
                    variants__is_deleted=False,
                ),
            )
        )
    )

    categories = (
        Category.objects
        .filter(is_active=True)
        .annotate(
            total_items=Count(
                "products",
                filter=Q(
                    products__is_deleted=False,
                    products__is_active=True,
                ),
                distinct=True,
            )
        )
        .order_by("name")
    )

    if search_query:
        products_queryset = products_queryset.filter(
            Q(name__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(sku__icontains=search_query)
        )

    if category_id:
        products_queryset = products_queryset.filter(category_id=category_id)

    if rarity:
        products_queryset = products_queryset.filter(rarity__iexact=rarity)

    products_queryset = products_queryset.filter(
        min_price__isnull=False,
        min_price__gte=price_min,
        min_price__lte=price_max,
    )

    if sort_by == "oldest":
        products_queryset = products_queryset.order_by("id")
    elif sort_by == "a-z":
        products_queryset = products_queryset.order_by("name")
    elif sort_by == "z-a":
        products_queryset = products_queryset.order_by("-name")
    elif sort_by == "price-low":
        products_queryset = products_queryset.order_by("min_price", "name")
    elif sort_by == "price-high":
        products_queryset = products_queryset.order_by("-min_price", "name")
    else:
        sort_by = "newest"
        products_queryset = products_queryset.order_by("-id")

    products_list = list(products_queryset)

    if status == "in_stock":
        products_list = [
            product for product in products_list
            if product.total_stock > 10
        ]
    elif status == "limited":
        products_list = [
            product for product in products_list
            if 0 < product.total_stock <= 10
        ]
    elif status == "out_of_stock":
        products_list = [
            product for product in products_list
            if product.total_stock == 0
        ]

    # Mark the first displayed variant as already wishlisted.
    # This is used by collections.html to render a filled yellow heart.
    wishlisted_variant_ids = set()

    if request.user.is_authenticated:
        wishlisted_variant_ids = set(
            Wishlist.objects.filter(user=request.user)
            .values_list("variant_id", flat=True)
        )

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
        search_query
        or category_id
        or status
        or rarity
        or price_min > 0
        or price_max < 150000
    )

    context = {
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
    }

    return render(request, "products/collections.html", context)


def product_search_suggestions(request):
    """
    Return product suggestions for the collection-page search box.

    URL example:
        /collections/search-suggestions/?q=ferrari
    """
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"suggestions": []})

    active_variants = (
        ProductVariant.objects
        .filter(is_active=True, is_deleted=False)
        .prefetch_related("images")
        .order_by("id")
    )

    products = (
        Product.objects
        .filter(
            is_deleted=False,
            is_active=True,
        )
        .filter(
            Q(name__icontains=query)
            | Q(category__name__icontains=query)
            | Q(sku__icontains=query)
        )
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "variants",
                queryset=active_variants,
                to_attr="active_variants",
            )
        )
        .annotate(
            min_price=Min(
                "variants__price",
                filter=Q(
                    variants__is_active=True,
                    variants__is_deleted=False,
                ),
            )
        )
        .order_by("name")[:8]
    )

    suggestions = []

    for product in products:
        image_url = ""
        first_variant = (
            product.active_variants[0]
            if product.active_variants
            else None
        )

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
            "price": (
                f"{product.min_price:.2f}"
                if product.min_price is not None
                else ""
            ),
            "stock": product.total_stock,
            "image_url": image_url,
            "detail_url": reverse("product_detail", kwargs={"product_id": product.id}),
        })

    return JsonResponse({"suggestions": suggestions})

@login_required
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.filter(
            is_deleted=False,
            is_active=True,
        ).annotate(
            variant_stock=Sum(
                "variants__stock",
                filter=Q(
                    variants__is_active=True,
                    variants__is_deleted=False,
                ),
            ),
            min_variant_price=Min(
                "variants__price",
                filter=Q(
                    variants__is_active=True,
                    variants__is_deleted=False,
                ),
            ),
        ),
        id=product_id,
    )

    variants = (
        ProductVariant.objects.filter(
            product=product,
            is_active=True,
            is_deleted=False,
        )
        .prefetch_related("images")
        .order_by("id")
    )

    variants_list = list(variants)

    wishlisted_variant_ids = set(
        Wishlist.objects.filter(
            user=request.user,
            variant__product=product,
        ).values_list("variant_id", flat=True)
    )

    for variant in variants_list:
        image_urls = [image.image.url for image in variant.images.all()]
        variant.image_urls_json = json.dumps(image_urls)
        variant.is_wishlisted = variant.id in wishlisted_variant_ids

    first_variant = variants_list[0] if variants_list else None

    cart_count = Cart.objects.filter(
        user=request.user,
        variant__is_active=True,
        variant__is_deleted=False,
    ).count()

    wishlist_count = Wishlist.objects.filter(
        user=request.user,
        variant__is_active=True,
        variant__is_deleted=False,
    ).count()

    reviews = (
        ProductReview.objects.filter(
            product=product,
            is_active=True,
        )
        .select_related("user", "variant")
        .prefetch_related("images")
        .order_by("-created_at")
    )

    review_count = reviews.count()
    average_rating = 0

    if review_count:
        average_rating = round(
            sum(review.rating for review in reviews) / review_count,
            1,
        )

    context = {
        "product": product,
        "variants": variants_list,
        "first_variant": first_variant,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
        "reviews": reviews,
        "review_count": review_count,
        "average_rating": average_rating,
    }

    return render(request, "products/product_detail.html", context)


@login_required
@require_POST
def add_to_cart(request):
    variant_id = request.POST.get("variant_id", "").strip()
    quantity_value = request.POST.get("quantity", "1").strip()

    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
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

    if variant.stock <= 0:
        messages.error(request, "This variant is out of stock.")
        return detail_redirect

    if quantity > variant.stock:
        messages.error(
            request,
            f"Only {variant.stock} unit(s) are available.",
        )
        return detail_redirect

    existing_cart_item = Cart.objects.filter(
        user=request.user,
        variant=variant,
    ).first()

    if existing_cart_item:
        # Keep cart and wishlist mutually exclusive even when the item
        # was already in the cart.
        Wishlist.objects.filter(
            user=request.user,
            variant=variant,
        ).delete()

        messages.info(
            request,
            "This variant is already in your cart. It was removed from your wishlist.",
        )
        return detail_redirect

    Cart.objects.create(
        user=request.user,
        variant=variant,
        quantity=quantity,
    )

    # A variant added to cart should no longer remain in wishlist.
    Wishlist.objects.filter(
        user=request.user,
        variant=variant,
    ).delete()

    messages.success(
        request,
        "Product added to cart successfully.",
    )
    return detail_redirect


def get_cart_totals(user):
    """
    Calculate cart totals using the best active product/category offer
    for each variant.

    Cart model is not changed. Offer values are calculated dynamically.
    """

    cart_items = list(
        Cart.objects.filter(
            user=user,
            variant__is_active=True,
            variant__is_deleted=False,
        )
        .select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        )
        .prefetch_related(
            "variant__images"
        )
        .order_by("-created_at")
    )

    offer_summary = build_cart_offer_summary(cart_items)

    # Attach calculated offer information to every Cart object so the
    # template can access item.offer_data.
    for line in offer_summary["lines"]:
        cart_item = line["cart_item"]
        cart_item.offer_data = line

    original_subtotal = offer_summary["original_subtotal"]
    offer_discount = offer_summary["offer_discount"]
    subtotal_after_offer = offer_summary["subtotal_after_offer"]

    shipping = (
        Decimal("80.00")
        if subtotal_after_offer > 0
        else Decimal("0.00")
    )

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


@login_required
def cart_view(request):
    totals = get_cart_totals(request.user)

    return render(
        request,
        "products/cart.html",
        {
            "cart_items": totals["cart_items"],
            "subtotal": totals["original_subtotal"],
            "offer_discount": totals["offer_discount"],
            "subtotal_after_offer": totals["subtotal_after_offer"],
            "shipping": totals["shipping"],
            "grand_total": totals["grand_total"],
            "cart_count": totals["cart_count"],
        },
    )


def _cart_ajax_response(cart_item, totals):
    """
    Build one consistent JSON response for quantity increase/decrease.
    """

    current_line = None

    for line in totals["cart_items"]:
        if line.id == cart_item.id:
            current_line = line
            break

    if current_line is None:
        return {
            "success": False,
            "message": "Cart item not found.",
        }

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


@login_required
@require_POST
def increase_cart_item(request, item_id):
    cart_item = get_object_or_404(
        Cart.objects.select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        ),
        id=item_id,
        user=request.user,
    )

    if cart_item.quantity >= cart_item.variant.stock:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": "Stock unavailable.",
            })

        messages.error(request, "Stock unavailable.")
        return redirect("cart")

    cart_item.quantity += 1
    cart_item.save(update_fields=["quantity"])

    totals = get_cart_totals(request.user)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            _cart_ajax_response(cart_item, totals)
        )

    messages.success(request, "Cart updated successfully.")
    return redirect("cart")


@login_required
@require_POST
def decrease_cart_item(request, item_id):
    cart_item = get_object_or_404(
        Cart.objects.select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        ),
        id=item_id,
        user=request.user,
    )

    if cart_item.quantity <= 1:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "message": "Minimum quantity is 1.",
            })

        messages.error(request, "Minimum quantity is 1.")
        return redirect("cart")

    cart_item.quantity -= 1
    cart_item.save(update_fields=["quantity"])

    totals = get_cart_totals(request.user)

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            _cart_ajax_response(cart_item, totals)
        )

    messages.success(request, "Cart updated successfully.")
    return redirect("cart")


@login_required
@require_POST
def remove_cart_item(request, item_id):
    cart_item = get_object_or_404(
        Cart,
        id=item_id,
        user=request.user,
    )

    cart_item.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
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
    user=request.user,
    variant__is_active=True,
    variant__is_deleted=False
).order_by("-created_at")

    wishlist_value = sum(item.variant.price for item in wishlist_items)
    available_stock = sum(item.variant.stock for item in wishlist_items)

    cart_count = Cart.objects.filter(
        user=request.user,
        variant__is_active=True,
        variant__is_deleted=False
    ).count()
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
    """
    Toggle the selected variant in the user's wishlist.

    First click:
        Add to wishlist.

    Second click:
        Remove from wishlist.

    The user is redirected back to the page from which the action started.
    """
    variant_id = request.POST.get("variant_id", "").strip()
    next_url = request.POST.get("next", "").strip()

    fallback_url = reverse("collections")

    if next_url and url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        redirect_url = next_url
    else:
        redirect_url = fallback_url

    if not variant_id:
        messages.error(request, "Variant not selected.")
        return redirect(redirect_url)

    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id,
        is_active=True,
        is_deleted=False,
        product__is_active=True,
        product__is_deleted=False,
    )

    wishlist_item = Wishlist.objects.filter(
        user=request.user,
        variant=variant,
    ).first()

    if wishlist_item:
        wishlist_item.delete()
        messages.success(
            request,
            "Product removed from wishlist.",
        )
        return redirect(redirect_url)

    if Cart.objects.filter(
        user=request.user,
        variant=variant,
    ).exists():
        messages.info(
            request,
            "This variant is already in your cart.",
        )
        return redirect(redirect_url)

    Wishlist.objects.create(
        user=request.user,
        variant=variant,
    )

    messages.success(
        request,
        "Product added to wishlist.",
    )
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