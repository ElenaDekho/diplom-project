import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo

# Тест: получение списка товаров
@pytest.mark.django_db
def test_product_list():
    client = APIClient()
    response = client.get('/api/products/')
    assert response.status_code == 200

# Тест: фильтрация по магазину
@pytest.mark.django_db
def test_product_list_filter_by_shop():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    shop1 = Shop.objects.create(name='Shop1', user=user)
    shop2 = Shop.objects.create(name='Shop2', user=user)
    cat = Category.objects.create(name='Cat')
    prod = Product.objects.create(name='Prod', category=cat)
    ProductInfo.objects.create(product=prod, shop=shop1, price=100)
    ProductInfo.objects.create(product=prod, shop=shop2, price=200)

    client = APIClient()
    response = client.get('/api/products/?shop=1')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['shop_name'] == 'Shop1'

# Тест: фильтрация по категории
@pytest.mark.django_db
def test_product_list_filter_by_category():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    shop = Shop.objects.create(name='Shop', user=user)
    cat1 = Category.objects.create(name='Cat1')
    cat2 = Category.objects.create(name='Cat2')
    prod1 = Product.objects.create(name='Prod1', category=cat1)
    prod2 = Product.objects.create(name='Prod2', category=cat2)
    ProductInfo.objects.create(product=prod1, shop=shop, price=100)
    ProductInfo.objects.create(product=prod2, shop=shop, price=200)

    client = APIClient()
    response = client.get('/api/products/?product__category=1')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['product_name'] == 'Prod1'

# Тест: поиск по названию
@pytest.mark.django_db
def test_product_list_search():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    shop = Shop.objects.create(name='Shop', user=user)
    cat = Category.objects.create(name='Cat')
    prod1 = Product.objects.create(name='Laptop', category=cat)
    prod2 = Product.objects.create(name='Phone', category=cat)
    ProductInfo.objects.create(product=prod1, shop=shop, price=100)
    ProductInfo.objects.create(product=prod2, shop=shop, price=200)

    client = APIClient()
    response = client.get('/api/products/?search=Laptop')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['product_name'] == 'Laptop'

# Тест: успешное получение товара
@pytest.mark.django_db
def test_product_detail_success():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    shop = Shop.objects.create(name='Test Shop', user=user)
    cat = Category.objects.create(name='Test Cat')
    prod = Product.objects.create(name='Test Product', category=cat)
    product_info = ProductInfo.objects.create(product=prod, shop=shop, price=100)
    client = APIClient()
    response = client.get(f'/api/products/{product_info.id}/')
    assert response.status_code == 200
    assert response.data['id'] == product_info.id
    assert response.data['product_name'] == 'Test Product'

# Тест: товар не найден
@pytest.mark.django_db
def test_product_detail_not_found():
    client = APIClient()
    response = client.get('/api/products/999/')
    assert response.status_code == 404


# Тест: получение списка магазинов для товара
@pytest.mark.django_db
def test_product_shops_list():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    cat = Category.objects.create(name='Cat')
    product = Product.objects.create(name='Product', category=cat)

    shop1 = Shop.objects.create(name='Shop1', user=user, state=True)
    shop2 = Shop.objects.create(name='Shop2', user=user, state=True)

    ProductInfo.objects.create(product=product, shop=shop1, price=100, quantity=10)
    ProductInfo.objects.create(product=product, shop=shop2, price=150, quantity=5)

    client = APIClient()
    response = client.get(f'/api/products/{product.id}/shops/')

    assert response.status_code == 200
    assert len(response.data) == 2
    assert response.data[0]['shop_name'] == 'Shop1'
    assert response.data[0]['price'] == 100
    assert response.data[0]['quantity'] == 10
    assert response.data[1]['shop_name'] == 'Shop2'
    assert response.data[1]['price'] == 150
    assert response.data[1]['quantity'] == 5