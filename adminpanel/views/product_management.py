from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from adminpanel.models import Product, Category, ProductVariant, ProductImage
from django.db.models import Count  
from django.contrib import messages
from django.views.decorators.http import require_POST
import uuid
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
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '')
        category_id = request.POST.get('category')
        rarity = request.POST.get('rarity', 'LEGENDARY').upper()
        is_visible_raw = request.POST.get('is_visible')
        is_visible = is_visible_raw in ['true', 'on']

        if not name or not category_id:
            messages.error(request, "Product name and category are required!")
            categories = Category.objects.filter(is_active=True)
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

        try:
            category = get_object_or_404(Category, id=category_id)
            
            Product.objects.create(
                category=category,
                name=name,
                description=description,
                sku=f"WV-{uuid.uuid4().hex[:8].upper()}",
                rarity=rarity, 
                is_active=is_visible  
            )
            messages.success(request, f"Product '{name}' added successfully!")
            return redirect('admin_products')
            
        except Exception as e:
            messages.error(request, f"Error creating product: {str(e)}")
            categories = Category.objects.filter(is_active=True)
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

    categories = Category.objects.filter(is_active=True)
    return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})


def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        category_id = request.POST.get('category')
        rarity = request.POST.get('rarity', 'legendary')
        is_visible = request.POST.get('is_visible') == 'true'

        category = get_object_or_404(Category, id=category_id)
        
        product.name = name
        product.description = description
        product.category = category
        product.rarity = rarity
        product.is_active = is_visible  
        product.save()
        return redirect('admin_products')

    categories = Category.objects.filter(is_active=True)
    context = {
        'product': product,
        'categories': categories
    }
    return render(request, 'adminpanel/admin_login/edit_product.html', context)



def manage_variants(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    variants = product.variants.filter(is_deleted=False)
    
    return render(request, 'adminpanel/admin_login/manage_variants.html', {
        'product': product,
        'variants': variants
    })


# 2. ADD NEW VARIANT
def add_variant(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        price = request.POST.get('price')
        stock = request.POST.get('stock')
        size = request.POST.get('size', '').strip()
        color = request.POST.get('color', '').strip()
        image = request.FILES.get('variant_image')

        if not price or not stock or not size or not color:
            messages.error(request, "All specification fields are required.")
            return redirect('add_variant', product_id=product.id)

        try:
            ProductVariant.objects.create(
                product=product,
                price=price,
                stock=stock,
                size=size,
                color=color,
                image=image
            )
            update_product_stock(product)
            messages.success(request, f"Variant '{size} ({color})' successfully deployed into matrix!")
            return redirect('manage_variants', product_id=product.id)
        except Exception as e:
            messages.error(request, f"Initialization Failed: {str(e)}")
            
    return render(request, 'adminpanel/admin_login/add_variant.html', {'product': product})


# 3. EDIT EXISTING VARIANT
def edit_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    product = variant.product
    
    if request.method == 'POST':
        variant.price = request.POST.get('price')
        variant.stock = request.POST.get('stock')
        variant.size = request.POST.get('size', '').strip()
        variant.color = request.POST.get('color', '').strip()
        
        if request.FILES.get('variant_image'):
            variant.image = request.FILES.get('variant_image')
            
        try:
            variant.save()
            update_product_stock(product)
            messages.success(request, f"Variant updates compiled successfully!")
            return redirect('manage_variants', product_id=product.id)
        except Exception as e:
            messages.error(request, f"Compilation Error: {str(e)}")
            
    return render(request, 'adminpanel/admin_login/edit_variant.html', {'variant': variant, 'product': product})


@require_POST
def toggle_variant_status(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)    
    variant.is_active = not variant.is_active
    variant.save()
    
    return JsonResponse({
        'status': 'success',
        'is_active': variant.is_active
    })



# 4. DELETE VARIANT (SOFT DELETE)
def delete_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    product_id = variant.product.id
    
    if request.method == 'POST':
        variant.is_deleted = True  
        variant.save()
        update_product_stock(product_id)
        messages.success(request, "Variant telemetry terminated successfully from inventory.")
    return redirect('manage_variants', product_id=product_id)
