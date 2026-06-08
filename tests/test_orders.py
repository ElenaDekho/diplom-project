import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo, Contact, Order, OrderItem
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


# Тест: уведомление клиенту при подтверждении заказа поставщиком
@pytest.mark.django_db
@patch('backend.views.send_mail')
def test_notification_on_order_status_change_by_supplier(mock_send_mail):
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Shop', user=supplier)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()

    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/orders/{order.id}/status/', {'state': 'confirmed'})
    assert response.status_code == 200
    mock_send_mail.assert_called()
    assert mock_send_mail.call_args[1]['recipient_list'] == [customer.email]

# Тест: уведомление клиенту при изменении статуса заказа кладовщиком (assembled)
@pytest.mark.django_db
@patch('backend.views.send_mail')
def test_notification_on_order_status_change_by_storekeeper(mock_send_mail):
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
    order = Order.objects.filter(user=customer, state='new').first()
    # Сначала подтверждаем заказ
    order.state = 'confirmed'
    order.save()

    client.force_authenticate(user=storekeeper)
    response = client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'assembled'})
    assert response.status_code == 200
    mock_send_mail.assert_called()
    assert mock_send_mail.call_args[1]['recipient_list'] == [customer.email]


# Тест: кладовщик успешно меняет статус confirmed -> assembled
@pytest.mark.django_db
def test_storekeeper_change_status_confirmed_to_assembled():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer',
                                        type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper',
                                           type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()
    order.state = 'confirmed'
    order.save()

    client.force_authenticate(user=storekeeper)
    response = client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'assembled'})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == 'assembled'


# Тест: кладовщик успешно меняет статус assembled -> sent
@pytest.mark.django_db
def test_storekeeper_change_status_assembled_to_sent():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer',
                                        type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper',
                                           type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()
    order.state = 'confirmed'
    order.save()
    client.force_authenticate(user=storekeeper)
    client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'assembled'})

    response = client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'sent'})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == 'sent'


# Тест: кладовщик успешно меняет статус sent -> delivered
@pytest.mark.django_db
def test_storekeeper_change_status_sent_to_delivered():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer',
                                        type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper',
                                           type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()
    order.state = 'confirmed'
    order.save()
    client.force_authenticate(user=storekeeper)
    client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'assembled'})
    client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'sent'})

    response = client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'delivered'})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == 'delivered'


# Тест: ошибка при неправильной последовательности (new -> assembled)
@pytest.mark.django_db
def test_storekeeper_change_status_invalid_sequence():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer',
                                        type='customer')
    storekeeper = User.objects.create_user(email='storekeeper@test.com', password='pass', username='storekeeper',
                                           type='storekeeper')
    shop = Shop.objects.create(name='Shop', user=storekeeper)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()

    client.force_authenticate(user=storekeeper)
    response = client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'assembled'})
    assert response.status_code == 400
    assert response.data['error'] == 'Нельзя изменить статус с new на assembled'


# Тест: доступ запрещён для покупателя
@pytest.mark.django_db
def test_storekeeper_change_status_forbidden_for_customer():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer',
                                        type='customer')
    shop = Shop.objects.create(name='Shop', user=customer)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()
    order.state = 'confirmed'
    order.save()

    response = client.patch(f'/api/storekeeper/orders/{order.id}/status/', {'state': 'assembled'})
    assert response.status_code == 403
    assert response.data['error'] == 'Доступ только для кладовщиков'

# Тест: оформление заказа без контакта и с неверным контактом
@pytest.mark.django_db
def test_create_order_missing_contact():
    user = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    client = APIClient()
    client.force_authenticate(user=user)

    # Без поля contact_id
    response = client.post('/api/order/create/', {})
    assert response.status_code == 400
    assert response.data['error'] == 'Не указан контакт'

    # С несуществующим contact_id
    response = client.post('/api/order/create/', {'contact_id': 9999})
    assert response.status_code == 404
    assert response.data['error'] == 'Контакт не найден'


# Сценарий 1: Один поставщик, заказ подтверждается сразу
@pytest.mark.django_db
def test_partial_confirmation_one_supplier():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Shop', user=supplier)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    contact = Contact.objects.create(user=customer, city='City', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=customer)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    client.post('/api/order/create/', {'contact_id': contact.id})
    order = Order.objects.filter(user=customer, state='new').first()

    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/orders/{order.id}/status/', {})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == 'confirmed'
    assert order.confirmed_shops == str(shop.id)

# Сценарий 2: Два поставщика, заказ подтверждается только после подтверждения обоими
@pytest.mark.django_db
def test_partial_confirmation_two_suppliers():
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    supplier1 = User.objects.create_user(email='supplier1@test.com', password='pass', username='supplier1', type='supplier')
    supplier2 = User.objects.create_user(email='supplier2@test.com', password='pass', username='supplier2', type='supplier')
    shop1 = Shop.objects.create(name='Shop1', user=supplier1)
    shop2 = Shop.objects.create(name='Shop2', user=supplier2)
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

    # Подтверждение первого поставщика
    client.force_authenticate(user=supplier1)
    response = client.patch(f'/api/orders/{order.id}/status/', {})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == 'new'  # Статус ещё не confirmed
    assert shop1.id in [int(i) for i in order.confirmed_shops.split(',')]

    # Подтверждение второго поставщика
    client.force_authenticate(user=supplier2)
    response = client.patch(f'/api/orders/{order.id}/status/', {})
    assert response.status_code == 200
    order.refresh_from_db()
    assert order.state == 'confirmed'
    assert shop1.id in [int(i) for i in order.confirmed_shops.split(',')]
    assert shop2.id in [int(i) for i in order.confirmed_shops.split(',')]

# Частичное подтверждение: письмо отправляется только после подтверждения всеми поставщиками
@pytest.mark.django_db
@patch('backend.views.send_mail')
def test_partial_confirmation_two_suppliers_email_sent_only_once(mock_send_mail):
    customer = User.objects.create_user(email='customer@test.com', password='pass', username='customer', type='customer')
    supplier1 = User.objects.create_user(email='supplier1@test.com', password='pass', username='supplier1', type='supplier')
    supplier2 = User.objects.create_user(email='supplier2@test.com', password='pass', username='supplier2', type='supplier')
    shop1 = Shop.objects.create(name='Shop1', user=supplier1)
    shop2 = Shop.objects.create(name='Shop2', user=supplier2)
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

    # Сброс счётчика вызовов send_mail (игнорируем письмо при создании заказа)
    mock_send_mail.reset_mock()

    # Подтверждение первого поставщика (письмо не должно отправиться)
    client.force_authenticate(user=supplier1)
    response1 = client.patch(f'/api/orders/{order.id}/status/', {})
    assert response1.status_code == 200
    order.refresh_from_db()
    assert order.state == 'new'
    assert mock_send_mail.call_count == 0

    # Подтверждение второго поставщика (письмо должно отправиться один раз)
    client.force_authenticate(user=supplier2)
    response2 = client.patch(f'/api/orders/{order.id}/status/', {})
    assert response2.status_code == 200
    order.refresh_from_db()
    assert order.state == 'confirmed'
    assert mock_send_mail.call_count == 1
    # Проверяем, что письмо ушло покупателю
    args, kwargs = mock_send_mail.call_args
    assert kwargs['recipient_list'] == [customer.email]