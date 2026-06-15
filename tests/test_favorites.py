import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo, Favorite

@pytest.mark.django_db
def test_add_to_favorites():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/favorites/', {'product_info': product_info.id})
    assert response.status_code == 201
    assert Favorite.objects.filter(user=user, product_info=product_info).exists()

@pytest.mark.django_db
def test_list_favorites():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    Favorite.objects.create(user=user, product_info=product_info)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/favorites/')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['product_info'] == product_info.id

@pytest.mark.django_db
def test_delete_from_favorites():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    favorite = Favorite.objects.create(user=user, product_info=product_info)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete(f'/api/favorites/{favorite.id}/')
    assert response.status_code == 204
    assert not Favorite.objects.filter(id=favorite.id).exists()

@pytest.mark.django_db
def test_move_to_cart():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    favorite = Favorite.objects.create(user=user, product_info=product_info)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(f'/api/favorites/{favorite.id}/move_to_cart/', {'quantity': 2})
    assert response.status_code == 200
    from backend.models import Order, OrderItem
    cart = Order.objects.get(user=user, state='basket')
    assert OrderItem.objects.filter(order=cart, product_info=product_info, quantity=2).exists()

# Повторное добавление товара в избранное
@pytest.mark.django_db
def test_add_to_favorites_duplicate():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)

    client = APIClient()
    client.force_authenticate(user=user)
    # Первое добавление
    client.post('/api/favorites/', {'product_info': product_info.id})
    # Второе добавление
    response = client.post('/api/favorites/', {'product_info': product_info.id})
    assert response.status_code == 400
    assert response.data['non_field_errors'][0] == "Товар уже в избранном"

# Неавторизованный пользователь пытается добавить товар в избранное
@pytest.mark.django_db
def test_add_to_favorites_unauthorized():
    client = APIClient()
    response = client.post('/api/favorites/', {'product_info': 1})
    assert response.status_code == 401
    # Проверяем, что в ответе есть сообщение об ошибке (стандартное DRF)
    assert 'detail' in response.data

# Попытка удалить товар, которого нет в избранном
@pytest.mark.django_db
def test_delete_from_favorites_not_found():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete('/api/favorites/999/')
    assert response.status_code == 404

# Неавторизованный пользователь пытается удалить товар из избранного
@pytest.mark.django_db
def test_delete_from_favorites_unauthorized():
    client = APIClient()
    response = client.delete('/api/favorites/1/')
    assert response.status_code == 401

# Тест: перемещение в корзину с количеством больше остатка
@pytest.mark.django_db
def test_move_to_cart_insufficient_stock():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=5)
    favorite = Favorite.objects.create(user=user, product_info=product_info)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(f'/api/favorites/{favorite.id}/move_to_cart/', {'quantity': 10})
    assert response.status_code == 400
    assert response.data['error'] == 'Недостаточно товара на складе'

# Тест: перемещение, когда магазин не принимает заказы
@pytest.mark.django_db
def test_move_to_cart_shop_closed():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    shop = Shop.objects.create(name='Shop', user=user, state=False)
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)
    product_info = ProductInfo.objects.create(product=product, shop=shop, price=100, quantity=10)
    favorite = Favorite.objects.create(user=user, product_info=product_info)

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(f'/api/favorites/{favorite.id}/move_to_cart/', {'quantity': 1})
    assert response.status_code == 400
    assert response.data['error'] == 'Магазин не принимает заказы'

# Тест: неавторизованный пользователь
@pytest.mark.django_db
def test_move_to_cart_unauthorized():
    client = APIClient()
    response = client.post('/api/favorites/1/move_to_cart/', {'quantity': 1})
    assert response.status_code == 401

# Тест: товар не найден в избранном
@pytest.mark.django_db
def test_move_to_cart_not_found():
    user = User.objects.create_user(email='test@test.com', password='pass', username='test')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/favorites/999/move_to_cart/', {'quantity': 1})
    assert response.status_code == 404
    assert response.data['error'] == 'Товар не найден в избранном'
