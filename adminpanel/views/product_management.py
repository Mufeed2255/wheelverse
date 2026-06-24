from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from adminpanel.models import Product, Category, ProductVariant, ProductVariantImage
from django.db.models import Count  
from django.contrib import messages
from django.views.decorators.http import require_POST
import uuid
import re
from django.db.models import Min 


def update_product_stock(product):
    from django.db.models import Sum
    total = product.variants.filter(is_deleted=False).aggregate(
        total=Sum('stock')
    )['total'] or 0
    product.total_stock = total
    product.save(update_fields=['total_stock'])

def category_list(request):
    categories = Category.objects.filter(is_active=True).annotate(total_items=Count('products'))
    
    total_assets = Product.objects.filter(category__is_active=True).count()
    active_categories_count = categories.count()

    context = {
        'categories': categories,
        'total_assets': total_assets,
        'active_categories_count': active_categories_count
    }
    return render(request, 'adminpanel/admin_login/admin_category.html', context)


def add_category(request):
    if request.method == 'POST':
        name = request.POST.get('category_name', '').strip()
        description = request.POST.get('description', '')
        
        if name:
            if Category.objects.filter(name__iexact=name).exists():
                messages.error(request, f'"{name}" is already existing. Please choose a different name.')
                
                return render(request, 'adminpanel/admin_login/add_category.html', {
                    'description': description,
                })
            
            Category.objects.create(name=name, description=description)
            
            return redirect('admin_category')
            
    return render(request, 'adminpanel/admin_login/add_category.html')

# 3. EDIT CATEGORY VIEW
def edit_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        category.name = request.POST.get('category_name')
        category.description = request.POST.get('description')
        category.save()
        return redirect('admin_category')
        
    return render(request, 'adminpanel/admin_login/edit_category.html', {'category': category})

def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    category.is_active = False
    category.save()
    return redirect('admin_category')


def product_management(request):
    search_query = request.GET.get('search', '').strip()
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    rarity_filter = request.GET.get('rarity', '') 
    sort_by = request.GET.get('sort_by', '') 
    
    products_queryset = Product.objects.filter(is_deleted=False)
    categories = Category.objects.filter(is_active=True)
    
    products_queryset = products_queryset.annotate(min_price=Min('variants__price'))
    
    if search_query:
        products_queryset = products_queryset.filter(name__icontains=search_query)
        
    if category_id:
        products_queryset = products_queryset.filter(category_id=category_id)
        
    if rarity_filter:
        products_queryset = products_queryset.filter(rarity__iexact=rarity_filter)
    
    if sort_by == 'Oldest':
        products_queryset = products_queryset.order_by('id')
    elif sort_by == 'a-z':
        products_queryset = products_queryset.order_by('name')          
    elif sort_by == 'z-a':
        products_queryset = products_queryset.order_by('-name')          
    elif sort_by == 'price-low':
        products_queryset = products_queryset.order_by('min_price')
    elif sort_by == 'price-high': 
        products_queryset = products_queryset.order_by('-min_price')
        
    else:
        products_queryset = products_queryset.order_by('-id')  # Default Newest

    products_list = list(products_queryset)
        
    if status == 'in_stock':
        products_list = [p for p in products_list if p.total_stock > 10]
    elif status == 'limited':
        products_list = [p for p in products_list if 0 < p.total_stock <= 10]
    elif status == 'out_of_stock':
        products_list = [p for p in products_list if p.total_stock == 0]

    context = {
        'products': products_list,
        'categories': categories,
        'total_products_count': len(products_list), 
        'current_search': search_query,
        'current_category': category_id,
        'current_status': status,
        'current_rarity': rarity_filter, 
        'current_sort': sort_by,                                     
    }
    return render(request, 'adminpanel/admin_login/admin_products.html', context)


def delete_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        product.is_deleted = True  
        product.save()
        return HttpResponse(status=200)
    return HttpResponse(status=400)


@require_POST
def toggle_product_status(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    product.is_active = not product.is_active
    product.save()
    
    return JsonResponse({
        'status': 'success',
        'is_active': product.is_active
    })
def add_product(request):
    categories = Category.objects.filter(is_active=True)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        rarity = request.POST.get('rarity', 'LEGENDARY').upper()
        is_visible_raw = request.POST.get('is_visible')
        is_visible = is_visible_raw in ['true', 'on']

        allowed_rarities = [choice[0] for choice in Product.RARITY_CHOICES]
        name_pattern = r"^[A-Za-z0-9\s\-'&]+$"

        if not name:
            messages.error(request, "Product name is required.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if len(name) < 3:
            messages.error(request, "Product name must contain at least 3 characters.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if len(name) > 50:
            messages.error(request, "Product name cannot exceed 20 characters.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if not re.match(name_pattern, name):
            messages.error(request, "Invalid product name format.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if Product.objects.filter(name__iexact=name, is_deleted=False).exists():
            messages.error(request, "This product already exists.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if not category_id:
            messages.error(request, "Please select a category.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        category = Category.objects.filter(id=category_id, is_active=True).first()

        if not category:
            messages.error(request, "Selected category is invalid.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if not rarity:
            messages.error(request, "Please select rarity.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if rarity not in allowed_rarities:
            messages.error(request, "Invalid rarity selected.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if not description:
            messages.error(request, "Description is required.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if len(description) < 20:
            messages.error(request, "Description must contain at least 20 characters.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        if len(description) > 2000:
            messages.error(request, "Description cannot exceed 2000 characters.")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        try:
            Product.objects.create(
                category=category,
                name=name,
                description=description,
                sku=f"WV-{uuid.uuid4().hex[:8].upper()}",
                rarity=rarity,
                is_active=is_visible
            )

            messages.success(request, "Product added successfully.")
            return redirect('admin_products')

        except Exception as e:
            messages.error(request, f"Error creating product: {str(e)}")
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

    return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})


def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    categories = Category.objects.filter(is_active=True)

    if request.method == 'POST':

        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        rarity = request.POST.get('rarity', 'LEGENDARY').upper()

        is_visible_raw = request.POST.get('is_visible')
        is_visible = is_visible_raw in ['true', 'on']

        allowed_rarities = [choice[0] for choice in Product.RARITY_CHOICES]
        name_pattern = r"^[A-Za-z0-9\s\-'&]+$"

        if not name:
            messages.error(request, "Product name is required.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if len(name) < 3:
            messages.error(request, "Product name must contain at least 3 characters.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if len(name) > 50:
            messages.error(request, "Product name cannot exceed 50 characters.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if not re.match(name_pattern, name):
            messages.error(request, "Invalid product name format.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if Product.objects.filter(
            name__iexact=name,
            is_deleted=False
        ).exclude(id=product.id).exists():

            messages.error(request, "This product already exists.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if not category_id:
            messages.error(request, "Please select a category.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        category = Category.objects.filter(
            id=category_id,
            is_active=True
        ).first()

        if not category:
            messages.error(request, "Selected category is invalid.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if rarity not in allowed_rarities:
            messages.error(request, "Invalid rarity selected.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if not description:
            messages.error(request, "Description is required.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if len(description) < 20:
            messages.error(request, "Description must contain at least 20 characters.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        if len(description) > 2000:
            messages.error(request, "Description cannot exceed 2000 characters.")
            return render(request, 'adminpanel/admin_login/edit_product.html', {
                'product': product,
                'categories': categories
            })

        try:
            product.name = name
            product.description = description
            product.category = category
            product.rarity = rarity
            product.is_active = is_visible

            product.save()

            messages.success(request, "Product updated successfully.")
            return redirect('admin_products')

        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")

    context = {
        'product': product,
        'categories': categories
    }

    return render(
        request,
        'adminpanel/admin_login/edit_product.html',
        context
    )


def manage_variants(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = (
        product.variants
        .filter(is_deleted=False)
        .prefetch_related('images')
    )
    first_variant = variants.first()
    
    return render(request, 'adminpanel/admin_login/manage_variants.html', {
        'product': product,
        'variants': variants,
        "first_variant": first_variant,
    })


def add_variant(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":
        price = request.POST.get("price")
        stock = request.POST.get("stock")
        size = request.POST.get("size", "").strip()
        color = request.POST.get("color", "").strip()
        images = request.FILES.getlist("variant_images")

        if not price or not stock or not size or not color:
            messages.error(request, "All fields are required.")
            return redirect("add_variant", product_id=product.id)

        if len(images) != 3:
            messages.error(request, "Please upload exactly 3 images.")
            return redirect("add_variant", product_id=product.id)

        variant = ProductVariant.objects.create(
            product=product,
            price=price,
            stock=stock,
            size=size,
            color=color,
            image=images[0]
        )

        for index, image in enumerate(images):
            ProductVariantImage.objects.create(
                variant=variant,
                image=image,
                is_primary=(index == 0)
            )

        update_product_stock(product)
        messages.success(request, "Variant added successfully.")
        return redirect("manage_variants", product_id=product.id)

    return render(request, "adminpanel/admin_login/add_variant.html", {
        "product": product
    })
    
def edit_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    product = variant.product

    if request.method == "POST":
        variant.price = request.POST.get("price")
        variant.stock = request.POST.get("stock")
        variant.size = request.POST.get("size", "").strip()
        variant.color = request.POST.get("color", "").strip()

        images = request.FILES.getlist("variant_images")
        changed_slots = request.POST.get("changed_slots", "")

        changed_slots = [int(i) for i in changed_slots.split(",") if i != ""]

        existing_images = list(variant.images.all().order_by("id"))

        for slot, image in zip(changed_slots, images):
            if slot < len(existing_images):
                existing_images[slot].image = image
                existing_images[slot].is_primary = slot == 0
                existing_images[slot].save()
            else:
                ProductVariantImage.objects.create(
                    variant=variant,
                    image=image,
                    is_primary=(slot == 0)
                )

        all_images = list(variant.images.all().order_by("id"))

        for index, img in enumerate(all_images):
            img.is_primary = index == 0
            img.save()

        first_image = variant.images.filter(is_primary=True).first()
        if first_image:
            variant.image = first_image.image

        variant.save()
        update_product_stock(product)

        messages.success(request, "Variant updated successfully.")
        return redirect("manage_variants", product_id=product.id)

    return render(request, "adminpanel/admin_login/edit_variant.html", {
        "variant": variant,
        "product": product
    })
    
@require_POST
def toggle_variant_status(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)    
    variant.is_active = not variant.is_active
    variant.save()
    
    return JsonResponse({
        'status': 'success',
        'is_active': variant.is_active
    })


def delete_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    product = variant.product

    if request.method == 'POST':
        variant.is_deleted = True
        variant.save()

        update_product_stock(product)

        messages.success(request, "Variant removed successfully.")

    return redirect('manage_variants', product_id=product.id)