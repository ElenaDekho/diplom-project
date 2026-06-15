import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Shop

# Тест: поставщик закрывает свой магазин
@pytest.mark.django_db
def test_supplier_close_shop():
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=supplier, state=True)

    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/shops/{shop.id}/state/', {'state': False})
    assert response.status_code == 200
    shop.refresh_from_db()
    assert shop.state is False

# Тест: поставщик открывает свой магазин
@pytest.mark.django_db
def test_supplier_open_shop():
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=supplier, state=False)

    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/shops/{shop.id}/state/', {'state': True})
    assert response.status_code == 200
    shop.refresh_from_db()
    assert shop.state is True

# Тест: попытка закрыть чужой магазин
@pytest.mark.django_db
def test_supplier_close_other_shop():
    supplier1 = User.objects.create_user(email='supplier1@test.com', password='pass', username='supplier1', type='supplier')
    supplier2 = User.objects.create_user(email='supplier2@test.com', password='pass', username='supplier2', type='supplier')
    shop = Shop.objects.create(name='Other Shop', user=supplier2, state=True)

    client = APIClient()
    client.force_authenticate(user=supplier1)
    response = client.patch(f'/api/shops/{shop.id}/state/', {'state': False})
    assert response.status_code == 404
    assert response.data['error'] == 'Магазин не найден или не принадлежит вам'

# Тест: неавторизованный доступ
@pytest.mark.django_db
def test_shop_state_unauthorized():
    client = APIClient()
    response = client.patch('/api/shops/1/state/', {'state': False})
    assert response.status_code == 401
    assert 'detail' in response.data

# Тест: неверный параметр state
@pytest.mark.django_db
def test_shop_state_invalid_param():
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=supplier, state=True)

    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/shops/{shop.id}/state/', {'state': 'wrong'})
    assert response.status_code == 400
    assert response.data['error'] == 'state должен быть true или false'

# Тест: не указан параметр state
@pytest.mark.django_db
def test_shop_state_missing_param():
    supplier = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=supplier, state=True)

    client = APIClient()
    client.force_authenticate(user=supplier)
    response = client.patch(f'/api/shops/{shop.id}/state/', {})
    assert response.status_code == 400
    assert response.data['error'] == 'Укажите state'