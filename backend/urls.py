from django.urls import path
from .views import RegisterView, LoginView, ProductListView, CartView, ContactView, ContactDetailView
from .views import OrderCreateView, OrderListView, OrderDetailView, LogoutView, ProductShopsView
from .views import PasswordResetRequestView, PasswordResetConfirmView, ImportPriceView, SupplierOrdersView
from .views import ProductDetailView, OrderStatusUpdateView, CancelOrderView, ConfirmEmailView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('products/', ProductListView.as_view(), name='products'),
    path('cart/', CartView.as_view(), name='cart'),
    path('contacts/', ContactView.as_view(), name='contacts'),
    path('contacts/<int:pk>/', ContactDetailView.as_view(), name='contact_detail'),
    path('order/create/', OrderCreateView.as_view(), name='order_create'),
    path('orders/', OrderListView.as_view(), name='orders'),
    path('orders/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('products/<int:product_id>/shops/', ProductShopsView.as_view(), name='product_shops'),
    path('password-reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('import/', ImportPriceView.as_view(), name='import'),
    path('supplier/orders/', SupplierOrdersView.as_view(), name='supplier_orders'),
    path('products/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('orders/<int:pk>/status/', OrderStatusUpdateView.as_view(), name='order_status'),
    path('orders/<int:pk>/cancel/', CancelOrderView.as_view(), name='order_cancel'),
    path('confirm-email/<str:token>/', ConfirmEmailView.as_view(), name='confirm_email'),
]