from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from adminpanel.models import Product, Category, ProductVariant, ProductImage
from django.db.models import Count  
from django.contrib import messages
from django.views.decorators.http import require_POST
import uuid

def update_product_stock(product):
    from django.db.models import Sum
    total = product.variants.filter(is_deleted=False).aggregate(
        total=Sum('stock')
    )['total'] or 0
    product.total_stock = total
    product.save(update_fields=['total_stock'])

# 1. CATEGORY LIST VIEW
def category_list(request):
    # ഓരോ കാറ്റഗറിയിലുമുള്ള പ്രൊഡക്റ്റുകളുടെ എണ്ണം (Count) കൂടി ഒരുമിച്ച് എടുക്കുന്നു
    categories = Category.objects.filter(is_active=True).annotate(total_items=Count('products'))
    
    # Quick Sector Insights കണക്കുകൾ
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
        # ഇൻപുട്ട് ഫീൽഡിൽ നിന്നുള്ള ഡാറ്റ എടുക്കുന്നു (.strip() അനാവശ്യ സ്പേസുകൾ ഒഴിവാക്കും)
        name = request.POST.get('category_name', '').strip()
        description = request.POST.get('description', '')
        
        if name:
            # 1. ഈ പേരിൽ ഇതിനകം ഒരു കാറ്റഗറി ഡാറ്റാബേസിൽ ഉണ്ടോ എന്ന് പരിശോധിക്കുന്നു (Case-insensitive check)
            if Category.objects.filter(name__iexact=name).exists():
                # ഒരേ പേര് ഉണ്ടെങ്കിൽ അഡ്മിന് എറർ മെസ്സേജ് കാണിക്കുന്നു
                messages.error(request, f'"{name}" is already existing. Please choose a different name.')
                
                # നിലവിൽ ടൈപ്പ് ചെയ്ത ഡിസ്ക്രിപ്ഷൻ നഷ്ടപ്പെടാതെ തിരികെ ഫോമിലേക്ക് തന്നെ വിടുന്നു
                return render(request, 'adminpanel/admin_login/add_category.html', {
                    'description': description,
                })
            
            # 2. ഡ്യൂപ്ലിക്കേറ്റ് ഇല്ലെങ്കിൽ പുതിയ കാറ്റഗറി ഡാറ്റാബേസിൽ സേവ് ചെയ്യുന്നു
            Category.objects.create(name=name, description=description)
            
            # സേവ് ചെയ്തതിന് ശേഷം ലിസ്റ്റ് പേജിലേക്ക് റീഡയറക്ട് ചെയ്യുന്നു
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

# 4. DELETE CATEGORY VIEW (Soft Delete/Hard Delete)
def delete_category(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    # ഡാറ്റാബേസിൽ നിന്ന് പൂർണ്ണമായി ഒഴിവാക്കാൻ category.delete() ഉപയോഗിക്കാം. 
    # ഇവിടെ നമ്മൾ സുരക്ഷിതത്വത്തിനായി Soft Delete (is_active=False) ചെയ്യുന്നു.
    category.is_active = False
    category.save()
    return redirect('admin_category')

# def product_management(request):
#     search_query = request.GET.get('search', '').strip()
#     category_id = request.GET.get('category', '')
#     status = request.GET.get('status', '')
#     sort_by = request.GET.get('sort_by', '') 
    
#     # 1. അടിസ്ഥാനപരമായി ആക്ടീവ് ആയ എല്ലാ പ്രൊഡക്റ്റുകളും എടുക്കുന്നു
#     products = Product.objects.filter(is_active=True)
#     categories = Category.objects.filter(is_active=True)
    
#     # സെർച്ച് ലോജിക്
#     if search_query:
#         # നിങ്ങളുടെ മോഡലിൽ sku ഫീൽഡ് ഉണ്ടെന്ന് ഉറപ്പാക്കുക, ഇല്ലെങ്കിൽ sku ഫിൽട്ടർ ഒഴിവാക്കാം
#         products = products.filter(name__icontains=search_query)
        
#     # കാറ്റഗറി ഫിൽട്ടർ
#     if category_id:
#         products = products.filter(category_id=category_id)
        
#     # സ്റ്റാറ്റസ് ഫിൽട്ടർ (ഹസ്പിറ്റാലിറ്റി ഉറപ്പാക്കുന്നു, ഒരു ഫിൽട്ടറും സെലക്ട് ചെയ്തിട്ടില്ലെങ്കിൽ എല്ലാം കാണിക്കും)
#     if status == 'in_stock':
#         products = products.filter(total_stock__gt=10)
#     elif status == 'limited':
#         products = products.filter(total_stock__lte=10, total_stock__gt=0)
#     elif status == 'out_of_stock':
#         products = products.filter(total_stock=0)
        
#     # FIX: സോർട്ടിങ് ലോജിക് കൃത്യമാക്കുന്നു
#     if sort_by == 'a-z':
#         products = products.order_by('name')          
#     elif sort_by == 'z-a':
#         products = products.order_by('-name')         
#     elif sort_by == 'newest':
#         products = products.order_by('-id')  # ഒരൊറ്റ ഓർഡർ മാത്രം നിലനിർത്തുക (പുതിയത് ആദ്യം)          
#     else:
#         products = products.order_by('-id')  # ബൈ ഡീഫോൾട്ട് ആയി പുതിയ പ്രൊഡക്റ്റുകൾ മുകളിൽ കാണിക്കും

#     context = {
#         'products': products,
#         'categories': categories,
#         'total_products_count': products.count(),
#         'current_search': search_query,
#         'current_category': category_id,
#         'current_status': status,
#         'current_sort': sort_by,                                     
#     }
#     return render(request, 'adminpanel/admin_login/admin_products.html', context)


def product_management(request):
    search_query = request.GET.get('search', '').strip()
    category_id = request.GET.get('category', '')
    status = request.GET.get('status', '')
    sort_by = request.GET.get('sort_by', '') 
    
   # product_management വ്യൂവിന്റെ തുടക്കം ഇങ്ങനെ മാറ്റുക:
    products = Product.objects.filter(is_deleted=False).order_by('-id')
    categories = Category.objects.filter(is_active=True)
    
    # സെർച്ച് ലോജിക്
    if search_query:
        products = products.filter(name__icontains=search_query)
        
    # കാറ്റഗറി ഫിൽട്ടർ
    if category_id:
        products = products.filter(category_id=category_id)
        
    # സ്റ്റാറ്റസ് ഫിൽട്ടർ 
    if status == 'in_stock':
        products = products.filter(total_stock__gt=10)
    elif status == 'limited':
        products = products.filter(total_stock__lte=10, total_stock__gt=0)
    elif status == 'out_of_stock':
        products = products.filter(total_stock=0)
        
    # సోర్టింగ్ ലോജിക്
    if sort_by == 'a-z':
        products = products.order_by('name')          
    elif sort_by == 'z-a':
        products = products.order_by('-name')         
    elif sort_by == 'newest':
        products = products.order_by('-id')          
    else:
        products = products.order_by('-id')  # ബൈ ഡീഫോൾട്ട് പുതിയ പ്രൊഡക്റ്റുകൾ മുകളിൽ കാണിക്കും

    context = {
        'products': products,
        'categories': categories,
        'total_products_count': products.count(),
        'current_search': search_query,
        'current_category': category_id,
        'current_status': status,
        'current_sort': sort_by,                                     
    }
    return render(request, 'adminpanel/admin_login/admin_products.html', context)


def delete_product(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        product.is_deleted = True  # Soft Delete
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
        rarity = request.POST.get('rarity', 'legendary')
        
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
                is_active=is_visible  
            )
            messages.success(request, f"Product '{name}' added successfully!")
            return redirect('admin_products')
            
        except Exception as e:
            # 🆕 ഇവിടെ എറർ വന്നാൽ ആ പേജ് തന്നെ വീണ്ടും റിട്ടേൺ ചെയ്യണം!
            messages.error(request, f"Error creating product: {str(e)}")
            categories = Category.objects.filter(is_active=True)
            return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})

    # GET റിക്വസ്റ്റ് ആണെങ്കിൽ ആക്ടീവ് ആയ കാറ്റഗറികൾ ഫോമിലേക്ക് പാസ്സ് ചെയ്യുന്നു
    categories = Category.objects.filter(is_active=True)
    return render(request, 'adminpanel/admin_login/add_product.html', {'categories': categories})


def edit_product(request, product_id):
    # അപ്ഡേറ്റ് ചെയ്യേണ്ട പ്രൊഡക്റ്റ് ഒബ്ജക്റ്റ് ഡാറ്റാബേസിൽ നിന്ന് എടുക്കുന്നു
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        category_id = request.POST.get('category')
        rarity = request.POST.get('rarity', 'legendary')
        is_visible = request.POST.get('is_visible') == 'true'

        # കാറ്റഗറി ഒബ്ജക്റ്റ് എടുക്കുന്നു
        category = get_object_or_404(Category, id=category_id)
        
        # നിലവിലുള്ള പ്രൊഡക്റ്റിന്റെ വാല്യൂസ് അപ്ഡേറ്റ് ചെയ്യുന്നു
        product.name = name
        product.description = description
        product.category = category
        product.rarity = rarity
        product.is_active = is_visible  # നിങ്ങളുടെ മോഡലിലെ ഫീൽഡ് നെയിം അനുസരിച്ച് മാറ്റുക
        # മാറ്റങ്ങൾ ഡാറ്റാബേസിൽ സേവ് ചെയ്യുന്നു
        product.save()

        # അപ്ഡേറ്റിന് ശേഷം പ്രൊഡക്റ്റ് ലിസ്റ്റ് പേജിലേക്ക് റീഡയറക്ട് ചെയ്യുന്നു
        return redirect('admin_products')

    # GET റിക്വസ്റ്റ് ആണെങ്കിൽ കറന്റ് പ്രൊഡക്റ്റ് ഡാറ്റയും കാറ്റഗറികളും ടെംപ്ലേറ്റിലേക്ക് പാസ്സ് ചെയ്യുന്നു
    categories = Category.objects.filter(is_active=True)
    context = {
        'product': product,
        'categories': categories
    }
    return render(request, 'adminpanel/admin_login/edit_product.html', context)



def manage_variants(request, product_id):
    # യുആർഎല്ലിൽ നിന്ന് വരുന്ന product_id വെച്ച് പ്രൊഡക്റ്റ് എടുക്കുന്നു
    product = get_object_or_404(Product, id=product_id)
    
    # ആ പ്രൊഡക്റ്റിന്റെ വേരിയന്റുകൾ മാത്രം എടുക്കുന്നു
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
    # വേരിയന്റ് ഉണ്ടോ എന്ന് നോക്കുന്നു, ഇല്ലെങ്കിൽ 404 എറർ അടിക്കും
    variant = get_object_or_404(ProductVariant, id=variant_id)
    
    # നിലവിലുള്ള സ്റ്റാറ്റസ് തിരിച്ചിടുന്നു (True ആണെങ്കിൽ False, False ആണെങ്കിൽ True)
    variant.is_active = not variant.is_active
    variant.save()
    
    # വിജയകരമായി മാറി എന്ന് ഫ്രണ്ട്-എൻഡിനെ അറിയിക്കാൻ JSON റിട്ടേൺ ചെയ്യുന്നു
    return JsonResponse({
        'status': 'success',
        'is_active': variant.is_active
    })

# 4. DELETE VARIANT (SOFT DELETE)
def delete_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    product_id = variant.product.id
    
    if request.method == 'POST':
        variant.is_deleted = True  # Soft delete
        variant.save()
        update_product_stock(product)
        messages.success(request, "Variant telemetry terminated successfully from inventory.")
    return redirect('manage_variants', product_id=product_id)

