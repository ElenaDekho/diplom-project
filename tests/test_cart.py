import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo, Contact, Order

# Тест: Добавление товара в корзину
@pytest.mark.django_db
def test_add_to_cart():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 2})
    assert response.status_code == 200
    assert Order.objects.filter(user=user, state='basket').exists()

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_add_to_cart_unauthorized():
    client = APIClient()
    response = client.post('/api/cart/', {'product_info_id': 1, 'quantity': 1})
    assert response.status_code == 401
    assert 'detail' in response.data

# Тест: количество не число
@pytest.mark.django_db
def test_add_to_cart_invalid_quantity():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': 1, 'quantity': 'abc'})
    assert response.status_code == 400
    assert response.data['error'] == 'Количество должно быть числом'

# Тест: количество <= 0
@pytest.mark.django_db
def test_add_to_cart_zero_quantity():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': 1, 'quantity': 0})
    assert response.status_code == 400
    assert response.data['error'] == 'Количество должно быть больше 0'

# Тест: не указан товар
@pytest.mark.django_db
def test_add_to_cart_no_product_id():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'quantity': 1})
    assert response.status_code == 400
    assert response.data['error'] == 'Не указан товар'

# Тест: товар не найден
@pytest.mark.django_db
def test_add_to_cart_product_not_found():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': 999, 'quantity': 1})
    assert response.status_code == 404
    assert response.data['error'] == 'Товар не найден'

# Тест: магазин не принимает заказы
@pytest.mark.django_db
def test_add_to_cart_shop_closed():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Closed Shop', user=user, state=False)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    assert response.status_code == 400
    assert response.data['error'] == 'Магазин не принимает заказы'

# Тест: товар отсутствует на складе
@pytest.mark.django_db
def test_add_to_cart_out_of_stock():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Shop', user=user, state=True)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=0)
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    assert response.status_code == 400
    assert response.data['error'] == 'Товар отсутствует на складе'

# Тест: просмотр корзины авторизованным пользователем
@pytest.mark.django_db
def test_get_cart_authenticated():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 2})
    response = client.get('/api/cart/')
    assert response.status_code == 200
    assert response.data['total_sum'] == 200

# Тест: просмотр корзины неавторизованным пользователем
@pytest.mark.django_db
def test_get_cart_unauthorized():
    client = APIClient()
    response = client.get('/api/cart/')
    assert response.status_code == 401
    assert 'detail' in response.data

# Тест: успешное удаление товара из корзины
@pytest.mark.django_db
def test_delete_cart_item_success():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 2})
    response = client.delete('/api/cart/', {'product_info_id': product_info.id})
    assert response.status_code == 200
    assert response.data['message'] == 'Товар удален из корзины'

# Тест: попытка удалить несуществующий товар (корзина не пуста)
@pytest.mark.django_db
def test_delete_cart_item_not_found():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})  # добавляем товар
    response = client.delete('/api/cart/', {'product_info_id': 999})  # удаляем другой товар
    assert response.status_code == 404
    assert response.data['error'] == 'Товар не найден в корзине'

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_delete_cart_item_unauthorized():
    client = APIClient()
    response = client.delete('/api/cart/', {'product_info_id': 1})
    assert response.status_code == 401
    assert 'detail' in response.data

# Тест: не указан товар
@pytest.mark.django_db
def test_delete_cart_item_no_product_id():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete('/api/cart/', {})
    assert response.status_code == 400
    assert response.data['error'] == 'Не указан товар'

# Тест: корзина пуста
@pytest.mark.django_db
def test_delete_cart_item_empty_cart():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete('/api/cart/', {'product_info_id': 1})
    assert response.status_code == 404
    assert response.data['error'] == 'Корзина пуста'

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_update_cart_unauthorized():
    client = APIClient()
    response = client.put('/api/cart/', {'product_info_id': 1, 'quantity': 2})
    assert response.status_code == 401
    assert 'detail' in response.data

# Тест: не указан товар или количество
@pytest.mark.django_db
def test_update_cart_missing_fields():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.put('/api/cart/', {'product_info_id': 1})
    assert response.status_code == 400
    assert response.data['error'] == 'Не указан товар или количество'

# Тест: корзина пуста
@pytest.mark.django_db
def test_update_cart_empty_cart():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.put('/api/cart/', {'product_info_id': 1, 'quantity': 2})
    assert response.status_code == 404
    assert response.data['error'] == 'Корзина пуста'

# Тест: товар не найден в корзине
@pytest.mark.django_db
def test_update_cart_item_not_found():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    response = client.put('/api/cart/', {'product_info_id': 999, 'quantity': 2})
    assert response.status_code == 404
    assert response.data['error'] == 'Товар не найден в корзине'

# Тест: успешное обновление количества
@pytest.mark.django_db
def test_update_cart_success():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    response = client.put('/api/cart/', {'product_info_id': product_info.id, 'quantity': 3})
    assert response.status_code == 200
    assert response.data['message'] == 'Количество обновлено'

# Тест: удаление товара при quantity=0
@pytest.mark.django_db
def test_update_cart_delete_when_zero():
    user = User.objects.create_user(email='test@test.com', password='test')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    product = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    client = APIClient()
    client.force_authenticate(user=user)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 1})
    response = client.put('/api/cart/', {'product_info_id': product_info.id, 'quantity': 0})
    assert response.status_code == 200
    assert response.data['message'] == 'Товар удален из корзины'

# Тест: количество не число
@pytest.mark.django_db
def test_update_cart_invalid_quantity():
    user = User.objects.create_user(email='test@test.com', password='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.put('/api/cart/', {'product_info_id': 1, 'quantity': 'abc'})
    assert response.status_code == 400
    assert response.data['error'] == 'Количество должно быть числом'

# Тест: добавление в корзину с количеством больше остатка
@pytest.mark.django_db
def test_add_to_cart_insufficient_stock():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=5)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 10})
    assert response.status_code == 400
    assert response.data['error'] == 'Недостаточно товара на складе'

# Тест: изменение количества в корзине на значение больше остатка
@pytest.mark.django_db
def test_update_cart_insufficient_stock():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=5)

    client = APIClient()
    client.force_authenticate(user=user)
    # Сначала добавляем товар в корзину (количество 2, остаток 5 — допустимо)
    client.post('/api/cart/', {'product_info_id': product_info.id, 'quantity': 2})
    # Пытаемся изменить количество на 10 (больше остатка)
    response = client.put('/api/cart/', {'product_info_id': product_info.id, 'quantity': 10})
    assert response.status_code == 400
    assert response.data['error'] == 'Недостаточно товара на складе'

