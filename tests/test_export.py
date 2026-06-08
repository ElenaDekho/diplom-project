import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo, Contact, Order, OrderItem, Parameter, ProductParameter
from django.utils import timezone
from datetime import timedelta
import csv
from io import StringIO

# Helper для парсинга CSV из ответа
def parse_csv_response(response):
    return list(csv.DictReader(StringIO(response.content.decode('utf-8-sig'))))


# 1. Экспорт заказов с фильтрацией по дате
@pytest.mark.django_db
def test_export_orders_filter_by_date():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')

    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order1 = Order.objects.filter(user=customer, state='new').first()
    order1.state = 'confirmed'
    order1.save()
    order1.dt = timezone.now() - timedelta(days=1)
    order1.save()

    # Очищаем корзину и создаём второй заказ
    OrderItem.objects.filter(order__user=customer, order__state='basket').delete()
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order2 = Order.objects.filter(user=customer, state='new').first()
    order2.state = 'confirmed'
    order2.save()
    order2.dt = timezone.now()
    order2.save()

    client.force_authenticate(user=storekeeper)
    today = timezone.now().date().isoformat()
    response = client.get('/api/storekeeper/orders/export/', {'date_from': today, 'date_to': today})
    assert response.status_code == 200
    data = parse_csv_response(response)
    assert len(data) == 1
    assert int(data[0]['ID заказа']) == order2.id


# 2. Экспорт заказов с фильтрацией по магазину
@pytest.mark.django_db
def test_export_orders_filter_by_shop():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop1 = Shop.objects.create(name='Shop1', user=storekeeper)
    shop2 = Shop.objects.create(name='Shop2', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product1 = Product.objects.create(name='Product1', category=cat)
    product2 = Product.objects.create(name='Product2', category=cat)
    product_info1 = ProductInfo.objects.create(product=product1, shop=shop1, price=100, quantity=10)
    product_info2 = ProductInfo.objects.create(product=product2, shop=shop2, price=200, quantity=5)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)

    client.post('/api/cart/', {'product_info_id': product_info1.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order1 = Order.objects.filter(user=customer, state='new').first()
    order1.state = 'confirmed'
    order1.save()

    OrderItem.objects.filter(order__user=customer, order__state='basket').delete()
    client.post('/api/cart/', {'product_info_id': product_info2.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order2 = Order.objects.filter(user=customer, state='new').first()
    order2.state = 'confirmed'
    order2.save()

    client.force_authenticate(user=storekeeper)
    response = client.get('/api/storekeeper/orders/export/', {'shop': shop1.id})
    data = parse_csv_response(response)
    assert len(data) == 1
    assert int(data[0]['ID заказа']) == order1.id


# 3. Экспорт заказа с товарами от двух магазинов
@pytest.mark.django_db
def test_export_order_with_two_shops():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop1 = Shop.objects.create(name='Shop1', user=storekeeper)
    shop2 = Shop.objects.create(name='Shop2', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product1 = Product.objects.create(name='Product1', category=cat)
    product2 = Product.objects.create(name='Product2', category=cat)
    product_info1 = ProductInfo.objects.create(product=product1, shop=shop1, price=100, quantity=10)
    product_info2 = ProductInfo.objects.create(product=product2, shop=shop2, price=200, quantity=5)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info1.id, 'quantity': 1})
    client.post('/api/cart/', {'product_info_id': product_info2.id, 'quantity': 2})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()
    order.state = 'confirmed'
    order.save()

    client.force_authenticate(user=storekeeper)
    response = client.get('/api/storekeeper/orders/export/')
    data = parse_csv_response(response)
    assert len(data) == 1
    items = data[0]['Товары']
    assert 'Product1 (Shop1) x1 = 100р' in items
    assert 'Product2 (Shop2) x2 = 400р' in items


# 4. Экспорт заказов: доступ запрещён для покупателя
@pytest.mark.django_db
def test_export_orders_forbidden_for_customer():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    client = APIClient()
    client.force_authenticate(user=customer)
    response = client.get('/api/storekeeper/orders/export/')
    assert response.status_code == 403
    assert response.data['error'] == 'Доступ только для кладовщиков'


# 5. Список заказов кладовщика возвращает по умолчанию confirmed, assembled, sent
@pytest.mark.django_db
def test_storekeeper_orders_list_default_statuses():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order_new = Order.objects.filter(user=customer, state='new').first()
    order_confirmed = Order.objects.create(user=customer, state='confirmed', contact=contact, dt=timezone.now())
    order_assembled = Order.objects.create(user=customer, state='assembled', contact=contact, dt=timezone.now())
    order_sent = Order.objects.create(user=customer, state='sent', contact=contact, dt=timezone.now())
    order_delivered = Order.objects.create(user=customer, state='delivered', contact=contact, dt=timezone.now())
    for o in [order_confirmed, order_assembled, order_sent, order_delivered, order_new]:
        OrderItem.objects.create(order=o, product_info=product_info, quantity=1)

    client.force_authenticate(user=storekeeper)
    response = client.get('/api/storekeeper/orders/')
    assert response.status_code == 200
    returned_ids = [item['id'] for item in response.data]
    assert order_confirmed.id in returned_ids
    assert order_assembled.id in returned_ids
    assert order_sent.id in returned_ids
    assert order_new.id not in returned_ids
    assert order_delivered.id not in returned_ids


# 6. Список заказов кладовщика с параметром status
@pytest.mark.django_db
def test_storekeeper_orders_list_with_status_param():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order_new = Order.objects.filter(user=customer, state='new').first()
    order_confirmed = Order.objects.create(user=customer, state='confirmed', contact=contact, dt=timezone.now())
    for o in [order_new, order_confirmed]:
        OrderItem.objects.create(order=o, product_info=product_info, quantity=1)

    client.force_authenticate(user=storekeeper)
    response = client.get('/api/storekeeper/orders/', {'status': 'new'})
    assert response.status_code == 200
    returned_ids = [item['id'] for item in response.data]
    assert order_new.id in returned_ids
    assert order_confirmed.id not in returned_ids


# 7. Экспорт заказов по умолчанию возвращает confirmed, assembled, sent
@pytest.mark.django_db
def test_export_orders_default_statuses():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order_new = Order.objects.filter(user=customer, state='new').first()
    order_confirmed = Order.objects.create(user=customer, state='confirmed', contact=contact, dt=timezone.now())
    order_assembled = Order.objects.create(user=customer, state='assembled', contact=contact, dt=timezone.now())
    order_sent = Order.objects.create(user=customer, state='sent', contact=contact, dt=timezone.now())
    order_delivered = Order.objects.create(user=customer, state='delivered', contact=contact, dt=timezone.now())
    for o in [order_confirmed, order_assembled, order_sent, order_delivered, order_new]:
        OrderItem.objects.create(order=o, product_info=product_info, quantity=1)

    client.force_authenticate(user=storekeeper)
    response = client.get('/api/storekeeper/orders/export/')
    data = parse_csv_response(response)
    returned_ids = [int(row['ID заказа']) for row in data]
    assert order_confirmed.id in returned_ids
    assert order_assembled.id in returned_ids
    assert order_sent.id in returned_ids
    assert order_new.id not in returned_ids
    assert order_delivered.id not in returned_ids


# 8. Экспорт заказов с явным указанием status=new
@pytest.mark.django_db
def test_export_orders_with_status_new():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order_new = Order.objects.filter(user=customer, state='new').first()
    order_confirmed = Order.objects.create(user=customer, state='confirmed', contact=contact, dt=timezone.now())
    for o in [order_new, order_confirmed]:
        OrderItem.objects.create(order=o, product_info=product_info, quantity=1)

    client.force_authenticate(user=storekeeper)
    response = client.get('/api/storekeeper/orders/export/', {'status': 'new'})
    data = parse_csv_response(response)
    returned_ids = [int(row['ID заказа']) for row in data]
    assert order_new.id in returned_ids
    assert order_confirmed.id not in returned_ids


### ЭКСПОРТ ТОВАРОВ

# 1. Доступ для кладовщика
@pytest.mark.django_db
def test_export_products_storekeeper_access():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    param = Parameter.objects.create(name='Color')
    ProductParameter.objects.create(product_info=product_info, parameter=param, value='Red')

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/')
    assert response.status_code == 200
    data = parse_csv_response(response)
    assert len(data) == 1
    assert data[0]['Название товара'] == 'Product'
    assert 'Color: Red' in data[0]['Параметры']

# 2. Доступ поставщика (только свои товары)
@pytest.mark.django_db
def test_export_products_supplier_only_own():
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    other_supplier = User.objects.create_user(email='other@test.com', password='pass', username='other', type='supplier')
    shop_own = Shop.objects.create(name='Own Shop', user=supplier)
    shop_other = Shop.objects.create(name='Other Shop', user=other_supplier)
    cat = Category.objects.create(name='Cat')
    product_own = Product.objects.create(name='Product Own', category=cat)
    product_other = Product.objects.create(name='Product Other', category=cat)
    ProductInfo.objects.create(product=product_own, shop=shop_own, price=100, quantity=10)
    ProductInfo.objects.create(product=product_other, shop=shop_other, price=200, quantity=5)

    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.get('/api/export/products/')
    data = parse_csv_response(response)
    assert len(data) == 1
    assert data[0]['Название товара'] == 'Product Own'

# 3. Доступ администратора (все товары)
@pytest.mark.django_db
def test_export_products_admin_all():
    admin = User.objects.create_user(email='admin@test.com', password='pass', username='admin', type='admin', is_superuser=True)
    shop = Shop.objects.create(name='Shop', user=admin)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)

    client = APIClient()
    client.force_authenticate(user=admin)
    response = client.get('/api/export/products/')
    data = parse_csv_response(response)
    assert len(data) >= 1

# 4. Фильтрация по shop
@pytest.mark.django_db
def test_export_products_filter_by_shop():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop1 = Shop.objects.create(name='Shop1', user=storekeeper)
    shop2 = Shop.objects.create(name='Shop2', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product1 = Product.objects.create(name='Product1', category=cat)
    product2 = Product.objects.create(name='Product2', category=cat)
    ProductInfo.objects.create(product=product1, shop=shop1, price=100, quantity=10)
    ProductInfo.objects.create(product=product2, shop=shop2, price=200, quantity=5)

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/', {'shop': shop1.id})
    data = parse_csv_response(response)
    assert len(data) == 1
    assert data[0]['Название товара'] == 'Product1'

# 5. Фильтрация по category
@pytest.mark.django_db
def test_export_products_filter_by_category():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat1 = Category.objects.create(name='Cat1')
    cat2 = Category.objects.create(name='Cat2')
    product1 = Product.objects.create(name='Product1', category=cat1)
    product2 = Product.objects.create(name='Product2', category=cat2)
    ProductInfo.objects.create(product=product1, shop=shop, price=100, quantity=10)
    ProductInfo.objects.create(product=product2, shop=shop, price=200, quantity=5)

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/', {'category': cat1.id})
    data = parse_csv_response(response)
    assert len(data) == 1
    assert data[0]['Название товара'] == 'Product1'

# 6. Фильтрация по min_quantity
@pytest.mark.django_db
def test_export_products_filter_by_min_quantity():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product1 = Product.objects.create(name='Product1', category=cat)
    product2 = Product.objects.create(name='Product2', category=cat)
    ProductInfo.objects.create(product=product1, shop=shop, price=100, quantity=10)
    ProductInfo.objects.create(product=product2, shop=shop, price=200, quantity=5)

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/', {'min_quantity': 7})
    data = parse_csv_response(response)
    assert len(data) == 1
    assert data[0]['Название товара'] == 'Product1'

# 7. Комбинация фильтров (shop + min_quantity)
@pytest.mark.django_db
def test_export_products_filter_combination():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product1 = Product.objects.create(name='Product1', category=cat)
    product2 = Product.objects.create(name='Product2', category=cat)
    ProductInfo.objects.create(product=product1, shop=shop, price=100, quantity=10)
    ProductInfo.objects.create(product=product2, shop=shop, price=200, quantity=5)

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/', {'shop': shop.id, 'min_quantity': 7})
    data = parse_csv_response(response)
    assert len(data) == 1
    assert data[0]['Название товара'] == 'Product1'

# 8. Проверка формата CSV (заголовки, колонки)
@pytest.mark.django_db
def test_export_products_csv_format():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/')
    data = parse_csv_response(response)
    assert list(data[0].keys()) == ['ID', 'Название товара', 'Магазин', 'Цена', 'Количество', 'Параметры']

# 9. Пустой результат (нет товаров под фильтр)
@pytest.mark.django_db
def test_export_products_empty_result():
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper', type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)

    client = APIClient()
    client.force_authenticate(user=storekeeper)
    response = client.get('/api/export/products/', {'min_quantity': 100})
    data = parse_csv_response(response)
    assert len(data) == 0

# 10. Необходимо авторизоваться
@pytest.mark.django_db
def test_export_products_unauthorized():
    client = APIClient()
    response = client.get('/api/export/products/')
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'

# 11. Поставщик пытается экспортировать чужой магазин
@pytest.mark.django_db
def test_export_products_supplier_foreign_shop():
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    other_supplier = User.objects.create_user(email='other@test.com', password='pass', username='other', type='supplier')
    shop_own = Shop.objects.create(name='Own Shop', user=supplier)
    shop_other = Shop.objects.create(name='Other Shop', user=other_supplier)
    cat = Category.objects.create(name='Cat')
    product_own = Product.objects.create(name='Product Own', category=cat)
    product_other = Product.objects.create(name='Product Other', category=cat)
    ProductInfo.objects.create(product=product_own, shop=shop_own, price=100, quantity=10)
    ProductInfo.objects.create(product=product_other, shop=shop_other, price=200, quantity=5)

    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.get('/api/export/products/', {'shop': shop_other.id})
    data = parse_csv_response(response)
    assert len(data) == 0