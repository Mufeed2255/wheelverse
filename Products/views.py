from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Q, Min, Sum
from adminpanel.models import Product, Category, ProductVariant
from Products.models import Cart, Wishlist
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from decimal import Decimal
from adminpanel.models import ProductVariant

def user_collections(request):
    search_query = request.GET.get('search', '').strip()
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    sort_by = request.GET.get('sort_by', '')
    rarity = request.GET.get('rarity', '').strip()
    

    try:
        price_min = int(request.GET.get('price_min', 0))
    except (ValueError, TypeError):
        price_min = 0

    try:
        price_max = int(request.GET.get('price_max', 150000))
    except (ValueError, TypeError):
        price_max = 150000


    products_queryset = Product.objects.filter(is_deleted=False, is_active=True)
    

    categories = Category.objects.filter(is_active=True).annotate(
        total_items=Count('products', filter=Q(products__is_deleted=False, products__is_active=True))
    )


    if search_query:
        products_queryset = products_queryset.filter(name__icontains=search_query)
        

    if category_id:
        products_queryset = products_queryset.filter(category_id=category_id)


    if rarity:
        products_queryset = products_queryset.filter(rarity__iexact=rarity)


    

    products_queryset = products_queryset.annotate(min_price=Min('variants__price'))

    if price_min:
        products_queryset = products_queryset.filter(min_price__gte=price_min)
    if price_max:
        products_queryset = products_queryset.filter(min_price__lte=price_max)

    if sort_by == 'a-z':
        products_queryset = products_queryset.order_by('name')
    elif sort_by == 'z-a':
        products_queryset = products_queryset.order_by('-name')
    elif sort_by == 'price-low': 
        products_queryset = products_queryset.order_by('min_price')
    elif sort_by == 'price-high': 
        products_queryset = products_queryset.order_by('-min_price')
    elif sort_by == 'oldest': 
        products_queryset = products_queryset.order_by('id')
    else:
        products_queryset = products_queryset.order_by('-id')

    products_list = list(products_queryset)

    if status == 'in_stock':
        products_list = [p for p in products_list if p.total_stock > 10]
    elif status == 'limited':
        products_list = [p for p in products_list if 0 < p.total_stock <= 10]
    elif status == 'out_of_stock':
        products_list = [p for p in products_list if p.total_stock == 0]

    paginator = Paginator(products_list, 6) 
    page = request.GET.get('page', 1)
    
    try:
        paginated_products = paginator.page(page)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)

    context = {
        'products': paginated_products,  
        'categories': categories,
        'total_products_count': len(products_list),
        'current_search': search_query,
        'current_category': category_id,
        'current_status': status,
        'current_sort': sort_by,
        'current_rarity': rarity,  
        'price_min': price_min,
        'price_max': price_max,
        'rarity_choices': [('', 'All Rarities')] + Product.RARITY_CHOICES,
}
    return render(request, 'products/collections.html', context)

@login_required
def product_detail(request, product_id):
    import json
    from django.shortcuts import get_object_or_404, render
    from django.db.models import Sum, Min
    from adminpanel.models import Product, ProductVariant
    from Products.models import Cart, Wishlist

    product = get_object_or_404(
        Product.objects.filter(is_deleted=False, is_active=True).annotate(
            variant_stock=Sum("variants__stock"),
            min_variant_price=Min("variants__price")
        ),
        id=product_id
    )

    variants = ProductVariant.objects.filter(
        product=product,
        is_active=True,
        is_deleted=False
    ).prefetch_related("images").order_by("id")

    variants_list = list(variants)

    for variant in variants_list:
        image_urls = [img.image.url for img in variant.images.all()]
        variant.image_urls_json = json.dumps(image_urls)

    first_variant = variants_list[0] if variants_list else None

    cart_count = Cart.objects.filter(user=request.user).count()
    wishlist_count = Wishlist.objects.filter(user=request.user).count()

    return render(request, "products/product_detail.html", {
        "product": product,
        "variants": variants_list,
        "first_variant": first_variant,
        "cart_count": cart_count,
        "wishlist_count": wishlist_count,
    })
    
    
@login_required
def add_to_cart(request):
    if request.method == "POST":
        variant_id = request.POST.get("variant_id")
        quantity = int(request.POST.get("quantity", 1))
        
        variant = get_object_or_404( ProductVariant,
        id=variant_id,
        is_active=True,
        is_deleted=False
    )
        product = variant.product

        if quantity > variant.stock:
            messages.error(request, "Stock unavailable.")
            return redirect("product_detail", product_id=product.id)

        if Cart.objects.filter(user=request.user, variant=variant).exists():
            messages.error(request, "This product is already added to cart.")
            return redirect("product_detail", product_id=product.id)

        Cart.objects.create(
            user=request.user,
            variant=variant,
            quantity=quantity
        )

        messages.success(request, "Product added to cart successfully.")
        return redirect("cart")

    return redirect("collections")


@login_required
def cart_view(request):

    cart_items = Cart.objects.filter(
        user=request.user,
        variant__is_active=True,
        variant__is_deleted=False
    )

    subtotal = sum(item.subtotal() for item in cart_items)

    discount = Decimal("0.00")
    shipping = Decimal("0.00")

    if subtotal > 0:
        shipping = Decimal("80.00")

    # Always calculate grand total
    grand_total = subtotal - discount + shipping

    context = {
        "cart_items": cart_items,
        "subtotal": subtotal,
        "discount": discount,
        "shipping": shipping,
        "grand_total": grand_total,
        "cart_count": cart_items.count(),
    }

    return render(request, "products/cart.html", context)

@login_required
def increase_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)

    if cart_item.quantity >= cart_item.variant.stock:
        messages.error(request, "Stock unavailable.")
    else:
        cart_item.quantity += 1
        cart_item.save()
        messages.success(request, "Cart updated successfully.")

    return redirect("cart")


@login_required
def decrease_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
        cart_item.save()
        messages.success(request, "Cart updated successfully.")

    return redirect("cart")


@login_required
def remove_cart_item(request, item_id):
    cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
    cart_item.delete()

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
def add_to_wishlist(request):
    if request.method == "POST":
        variant_id = request.POST.get("variant_id")

        if not variant_id:
            messages.error(request, "Variant not selected.")
            return redirect("collections")

        variant = get_object_or_404(
            ProductVariant, 
            id=variant_id,
            is_active=True,
            is_deleted=False
    )

        if Wishlist.objects.filter(user=request.user, variant=variant).exists():
            messages.error(request, "This product is already in your wishlist.")
            return redirect("product_detail", product_id=variant.product.id)

        Wishlist.objects.create(user=request.user, variant=variant)

        messages.success(request, "Product added to wishlist.")
        return redirect("wishlist")

    return redirect("collections")


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