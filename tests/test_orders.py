import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo, Contact, Order
from unittest.mock import patch
from django.core import mail

# Тест: успешное оформление заказа
@pytest.mark.django_db
def test_create_order_success():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    shop = Shop.objects.create(name='Test Shop', user=user, state=True)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    response = client.post('/api/order/create/', {'contact_id': contact.id})
    assert response.status_code == 200
    assert response.data['message'] == 'Заказ оформлен'
    assert Order.objects.filter(user=user, state='new').exists()

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_create_order_unauthorized():
    client = APIClient()
    response = client.post('/api/order/create/', {'contact_id': 1})
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'

# Тест: не указан contact_id
@pytest.mark.django_db
def test_create_order_no_contact():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/order/create/', {})
    assert response.status_code == 400
    assert response.data['error'] == 'Не указан контакт'

# Тест: контакт не найден
@pytest.mark.django_db
def test_create_order_contact_not_found():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/order/create/', {'contact_id': 999})
    assert response.status_code == 404
    assert response.data['error'] == 'Контакт не найден'

# Тест: корзина пуста
@pytest.mark.django_db
def test_create_order_empty_cart():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/order/create/', {'contact_id': contact.id})
    assert response.status_code == 400
    assert response.data['error'] == 'Корзина пуста'

# Тест: магазин не принимает заказы
@pytest.mark.django_db
def test_create_order_shop_closed():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    shop = Shop.objects.create(name='Test Shop', user=user, state=True)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    # Добавляем товар при открытом магазине
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    # Закрываем магазин
    shop.state = False
    shop.save()
    # Пытаемся оформить заказ
    response = client.post('/api/order/create/', {'contact_id': contact.id})
    assert response.status_code == 400
    assert response.data['error'] == 'Один из магазинов не принимает заказы'

# Тест: успешное получение списка заказов
@pytest.mark.django_db
def test_get_orders_success():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    shop = Shop.objects.create(name='Shop', user=user, state=True)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    response = client.get('/api/orders/')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['state'] == 'new'

# Тест: заказов нет
@pytest.mark.django_db
def test_get_orders_empty():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/orders/')
    assert response.status_code == 200
    assert response.data == []

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_get_orders_unauthorized():
    client = APIClient()
    response = client.get('/api/orders/')
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'

# Тест: успешное получение деталей заказа
@pytest.mark.django_db
def test_order_detail_success():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    shop = Shop.objects.create(name='Shop', user=user, state=True)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=user, state='new').first()
    response = client.get(f'/api/orders/{order.id}/')
    assert response.status_code == 200
    assert response.data['id'] == order.id
    assert len(response.data['items']) == 1

# Тест: заказ не найден
@pytest.mark.django_db
def test_order_detail_not_found():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/orders/999/')
    assert response.status_code == 404
    assert response.data['error'] == 'Заказ не найден'

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_order_detail_unauthorized():
    client = APIClient()
    response = client.get('/api/orders/1/')
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'


# Тест: проверка отправки email при создании заказа
@pytest.mark.django_db
@patch('backend.views.send_mail')
def test_order_create_email_sent(mock_send_mail):
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    shop = Shop.objects.create(name='Shop', user=user, state=True)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})

    assert mock_send_mail.call_count == 2  # 1 письмо клиенту + 1 письмо поставщику


# Тест: проверка отправки email при отмене заказа
@pytest.mark.django_db
@patch('backend.views.send_mail')
def test_order_cancel_email_sent(mock_send_mail):
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    shop = Shop.objects.create(name='Shop', user=user, state=True)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=user, state='new').first()
    client.post(f'/api/orders/{order.id}/cancel/')

    assert mock_send_mail.call_count >= 1  # письмо об отмене


# Тест: заказ с товарами от разных поставщиков
@pytest.mark.django_db
def test_create_order_multiple_suppliers():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')

    # Поставщик 1
    shop1 = Shop.objects.create(name='Shop1', user=user, state=True)
    cat = Category.objects.create(name='Cat')
    product1 = Product.objects.create(name='Product1', category=cat)
    product_info1 = ProductInfo.objects.create(product=product1, shop=shop1, price=100, quantity=10)

    # Поставщик 2
    shop2 = Shop.objects.create(name='Shop2', user=user, state=True)
    product2 = Product.objects.create(name='Product2', category=cat)
    product_info2 = ProductInfo.objects.create(product=product2, shop=shop2, price=200, quantity=5)

    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)

    client.post('/api/cart/', {'product_info_id': product_info1.id, 'quantity': 1})
    client.post('/api/cart/', {'product_info_id': product_info2.id, 'quantity': 2})

    response = client.post('/api/order/create/', {'contact_id': contact.id})
    assert response.status_code == 200
    order = Order.objects.filter(user=user, state='new').first()
    assert order.items.count() == 2
    assert order.items.filter(product_info__shop=shop1).exists()
    assert order.items.filter(product_info__shop=shop2).exists()


# Тест: успешное получение заказов поставщика
@pytest.mark.django_db
def test_supplier_orders_success():
    supplier = User.objects.create_user(email='supplier@test.com', password='testpass', username='supplier',
                                        type='supplier')
    customer = User.objects.create_user(email='customer@test.com', password='testpass', username='customer',
                                        type='customer')

    shop = Shop.objects.create(name='Shop', user=supplier, state=True)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='Moscow', street='Tverskaya', house='1', phone='123')

    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})

    client.force_authenticate(user=supplier)
    response = client.get('/api/supplier/orders/')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['order_id'] == Order.objects.first().id

# Тест: заказов с товарами поставщика нет
@pytest.mark.django_db
def test_supplier_orders_empty():
    supplier = User.objects.create_user(email='supplier@test.com', password='testpass', username='supplier', type='supplier')
    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.get('/api/supplier/orders/')
    assert response.status_code == 200
    assert response.data == []

# Тест: доступ только для поставщика
@pytest.mark.django_db
def test_supplier_orders_forbidden():
    customer = User.objects.create_user(email='customer@test.com', password='testpass', username='customer', type='customer')
    client = APIClient()
    client.force_authenticate(user=customer)
    response = client.get('/api/supplier/orders/')
    assert response.status_code == 403
    assert response.data['error'] == 'Доступ только для поставщиков'


# Тест: отправка email клиенту при изменении статуса заказа поставщиком
@pytest.mark.django_db
@patch('backend.views.send_mail')
def test_order_status_change_email_sent(mock_send_mail):
    # Покупатель
    customer = User.objects.create_user(email='customer@test.com', password='testpass', username='customer',
                                        type='customer')
    # Поставщик
    supplier = User.objects.create_user(email='supplier@test.com', password='testpass', username='supplier',
                                        type='supplier')

    shop = Shop.objects.create(name='Shop', user=supplier, state=True)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='Moscow', street='Tverskaya', house='1', phone='123')

    client = APIClient()

    # Покупатель оформляет заказ
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()

    # Поставщик меняет статус
    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/orders/{order.id}/status/', {'state': 'confirmed'})

    assert response.status_code == 200
    mock_send_mail.assert_called()
    # Проверяем, что письмо ушло именно покупателю
    args, kwargs = mock_send_mail.call_args
    assert kwargs['recipient_list'] == [customer.email]