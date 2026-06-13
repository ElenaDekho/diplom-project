from django.contrib import admin
from .models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter, Contact, Order, OrderItem

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    pass

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    pass

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    pass

@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    pass

@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    pass

@admin.register(ProductParameter)
class ProductParameterAdmin(admin.ModelAdmin):
    pass

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    pass

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    pass

@admin.action(description='Запустить асинхронный импорт для выбранных магазинов')
def run_import(modeladmin, request, queryset):
    from .tasks import do_import_task
    for shop in queryset:
        if shop.yaml_file:
            do_import_task.delay(shop.yaml_file)
        else:
            modeladmin.message_user(request, f'Магазин "{shop.name}" не имеет файла импорта', level='ERROR')

# Если модель уже зарегистрирована, сначала удалим
try:
    admin.site.unregister(Shop)
except admin.sites.NotRegistered:
    pass

@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    actions = [run_import]
    list_display = ('name', 'user', 'yaml_file')
