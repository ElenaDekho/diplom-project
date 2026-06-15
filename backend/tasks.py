from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from import_data import import_from_yaml
from django.utils import timezone
import csv
from io import StringIO
import os

print("!!! ЗАДАЧИ ЗАГРУЖЕНЫ !!!")

@shared_task
def send_email_task(subject, message, recipient_list, from_email=None, fail_silently=False):
    send_mail(
        subject=subject,
        message=message,
        from_email=from_email or settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipient_list,
        fail_silently=fail_silently,
    )
    return f"Email sent to {recipient_list}"

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def do_import_task(self, file_path):
    print(f"Задача начала выполнение для {file_path}")
    try:
        import_from_yaml(file_path)
        return f"Import from {file_path} completed"
    except Exception as e:
        print(f"Ошибка: {e}")
        if self.request.retries < self.max_retries:
            self.retry(exc=e)
        else:
            raise e  # после всех попыток выбрасываем ошибку


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def do_export_orders_task(self, user_id, filters=None):
    from django.contrib.auth import get_user_model
    from backend.models import Order

    try:
        User = get_user_model()
        user = User.objects.get(id=user_id)

        # Фильтрация
        statuses = filters.get('status') if filters else None
        if not statuses:
            statuses = ['confirmed', 'assembled', 'sent']

        orders = Order.objects.filter(state__in=statuses)

        date_from = filters.get('date_from') if filters else None
        date_to = filters.get('date_to') if filters else None
        if date_from:
            orders = orders.filter(dt__date__gte=date_from)
        if date_to:
            orders = orders.filter(dt__date__lte=date_to)

        shop_id = filters.get('shop') if filters else None
        if shop_id:
            orders = orders.filter(items__product_info__shop_id=shop_id).distinct()

        orders = orders.order_by('-dt')

        # Генерация CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID заказа', 'Дата', 'Статус', 'Клиент', 'Телефон', 'Адрес', 'Сумма', 'Товары'])

        for order in orders:
            contact = order.contact
            items_list = []
            for item in order.items.all():
                items_list.append(
                    f"{item.product_info.product.name} ({item.product_info.shop.name}) x{item.quantity} = "
                    f"{item.quantity * item.product_info.price}р"
                )
            items_str = '; '.join(items_list)
            writer.writerow([
                order.id,
                order.dt.strftime('%Y-%m-%d %H:%M'),
                order.state,
                order.user.email,
                contact.phone if contact else 'Не указан',
                f"{contact.city}, {contact.street} {contact.house}" if contact else 'Не указан',
                sum(item.quantity * item.product_info.price for item in order.items.all()),
                items_str
            ])

        # Сохраняем CSV в файл
        filename = f'orders_export_{user_id}_{timezone.now().timestamp()}.csv'
        filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(output.getvalue())

        return filepath
    except Exception as e:
        if self.request.retries < self.max_retries:
            self.retry(exc=e)
        else:
            raise e

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def do_export_products_task(self, user_id, filters=None):
    from django.contrib.auth import get_user_model
    from backend.models import ProductInfo

    try:
        User = get_user_model()
        user = User.objects.get(id=user_id)

        queryset = ProductInfo.objects.all()
        if user.type == 'supplier':
            queryset = queryset.filter(shop__user=user)

        # Фильтрация
        shop_id = filters.get('shop') if filters else None
        category_id = filters.get('category') if filters else None
        min_quantity = filters.get('min_quantity') if filters else None

        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        if min_quantity:
            queryset = queryset.filter(quantity__gte=min_quantity)

        # Генерация CSV
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'Название товара', 'Магазин', 'Цена', 'Количество', 'Параметры'])

        for product_info in queryset:
            params = '; '.join([f"{p.parameter.name}: {p.value}" for p in product_info.parameters.all()])
            writer.writerow([
                product_info.id,
                product_info.product.name,
                product_info.shop.name,
                product_info.price,
                product_info.quantity,
                params
            ])

        # Сохраняем CSV в файл
        filename = f'products_export_{user_id}_{timezone.now().timestamp()}.csv'
        filepath = os.path.join(settings.MEDIA_ROOT, 'exports', filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8-sig') as f:
            f.write(output.getvalue())

        return filepath
    except Exception as e:
        if self.request.retries < self.max_retries:
            self.retry(exc=e)
        else:
            raise e