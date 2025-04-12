"""Admin configuration for the inventory app."""
from datetime import date  # standard lib

from django.shortcuts import render, redirect, get_object_or_404  # third-party
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum
from django.http import HttpResponseForbidden
from django.contrib import messages

from .models import Product, Order, Report  # local
from .forms import RegisterForm, ProductForm, OrderForm

# Home Dashboard (optional)
def dashboard(request):
    """Render the main dashboard view."""
    return render(request, 'inventory/dashboard.html')


def register_view(request):
    """
    Handle user registration.

    On POST: validate and save the form.
    On GET: display an empty registration form.
    """
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = RegisterForm()
    return render(request, 'inventory/register.html', {'form': form})


def login_view(request):
    """
    Handle user login with role-based redirection.

    - Superusers are redirected to the product list.
    - Regular users are redirected to the user dashboard.
    """
    if request.method == 'POST':
        uname = request.POST['username']
        pwd = request.POST['password']
        user = authenticate(request, username=uname, password=pwd)
        if user:
            login(request, user)
            if user.is_superuser:
                return redirect('product_list')
            return redirect('user_dashboard')
    return render(request, 'inventory/login.html')

def logout_view(request):
    """
    Log out the current user and redirect to login page.
    """
    logout(request)
    return redirect('login')


@login_required
def user_dashboard(request):
    """
    Display the regular user dashboard with product listings and order form.

    - Redirects superusers to the product list.
    - Allows regular users to create orders.
    """
    if request.user.is_superuser:
        return redirect('product_list')

    products = Product.objects.all()

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.user = request.user
            order.save()
            return redirect('user_dashboard')
        # Optionally handle invalid form here (e.g. pass errors to template)

    else:
        form = OrderForm()

    return render(request, 'inventory/user_dashboard.html', {
        'products': products,
        'form': form,
    })

@login_required
def product_list(request):
    """
    Display the list of all products for admin users only.
    Returns 403 if the user is not a superuser.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to view this page.")

    products = Product.objects.all()
    return render(request, 'inventory/product_list.html', {'products': products})


@login_required
def product_create(request):
    """
    Allow admin users to create a new product.
    Returns 403 if the user is not a superuser.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to perform this action.")

    form = ProductForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'inventory/product_form.html', {'form': form})

# ✅ Admin-only Update Product
@login_required
def product_update(request, pk):
    """
    Allow admin users to update an existing product.
    Returns 403 if the user is not a superuser.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to perform this action.")

    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)

    if form.is_valid():
        form.save()
        return redirect('product_list')

    return render(request, 'inventory/product_form.html', {'form': form})


# ✅ Admin-only Delete Product
@login_required
def product_delete(request, pk):
    """
    Allow admin users to delete an existing product.
    Returns 403 if the user is not a superuser.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to perform this action.")

    product = get_object_or_404(Product, pk=pk)
    product.delete()
    return redirect('product_list')

# ✅ Create Order - For Logged-in Users
@login_required
def order_create(request):
    """
    Handles order creation by checking product stock and updating quantity.
    Prevents orders that exceed available inventory.
    """
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            product = order.product
            quantity_requested = order.quantity

            # Check if product is out of stock
            if product.quantity == 0:
                messages.error(request, f"'{product.name}' is out of stock.")

            # Check if requested quantity is available
            elif quantity_requested > product.quantity:
                messages.error(request, f"Only {product.quantity} units of '{product.name}' are available.")

            else:
                # Deduct ordered quantity from stock and save order
                product.quantity -= quantity_requested
                product.save()
                order.user = request.user  # Assign the user placing the order
                order.save()
                messages.success(request, "Order placed successfully.")
                return redirect('user_dashboard')
    else:
        form = OrderForm()

    return render(request, 'inventory/order_form.html', {'form': form})

# ✅ Admin-only Stock Alerts
@login_required
def stock_alerts(request):
    """
    Displays products where stock is less than or equal to their low stock threshold.
    Visible only to admins.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to view this page.")

    alerts = Product.objects.filter(quantity__lte=F('low_stock_threshold'))
    return render(request, 'inventory/alert_list.html', {'alerts': alerts})


# ✅ Admin-only Daily Sales Report
@login_required
def generate_report(request):
    """
    Generates a report for today: total number of orders and total sales.
    Saves the report and displays it to admin.
    """
    if not request.user.is_superuser:
        return HttpResponseForbidden("You are not authorized to view this page.")

    today = date.today()

    # Count today's orders
    total_orders = Order.objects.filter(order_date__date=today).count()

    # Calculate today's total sales: sum of quantity * product price
    total_sales = Order.objects.filter(order_date__date=today).aggregate(
        total=Sum(F('quantity') * F('product__price'))
    )['total'] or 0

    # Save the report
    Report.objects.create(
        report_date=today,
        total_orders=total_orders,
        total_sales=total_sales
    )

    return render(request, 'inventory/report.html', {
        'date': today,
        'orders': total_orders,
        'sales': total_sales
    })
