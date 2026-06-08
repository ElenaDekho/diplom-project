import pytest
from rest_framework.test import APIClient
from users.models import User
from backend.models import Contact

# Тест: успешное создание контакта
@pytest.mark.django_db
def test_create_contact_success():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/contacts/', {
        'city': 'Moscow',
        'street': 'Tverskaya',
        'house': '1',
        'phone': '+79991234567'
    })
    assert response.status_code == 201
    assert response.data['city'] == 'Moscow'
    assert Contact.objects.count() == 1

# Тест: создание контакта без авторизации
@pytest.mark.django_db
def test_create_contact_unauthorized():
    client = APIClient()
    response = client.post('/api/contacts/', {
        'city': 'Moscow',
        'street': 'Tverskaya',
        'house': '1',
        'phone': '+79991234567'
    })
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'

# Тест: создание контакта при превышении лимита (5)
@pytest.mark.django_db
def test_create_contact_limit_exceeded():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    for i in range(5):
        Contact.objects.create(user=user, city=f'City{i}', street='Street', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/contacts/', {
        'city': 'Moscow',
        'street': 'Tverskaya',
        'house': '1',
        'phone': '+79991234567'
    })
    assert response.status_code == 400
    assert response.data['error'] == 'Нельзя добавить более 5 контактов'

# Тест: пустые поля контакта → русские сообщения
@pytest.mark.django_db
def test_create_contact_blank_fields():
    user = User.objects.create_user(email='test@test.com', password='pass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/contacts/', {
        'city': '',
        'street': '',
        'house': '',
        'phone': ''
    })
    assert response.status_code == 400
    assert response.data['city'][0] == 'Укажите город'
    assert response.data['street'][0] == 'Укажите улицу'
    assert response.data['house'][0] == 'Укажите номер дома'
    assert response.data['phone'][0] == 'Укажите телефон'

# Тест: неверный формат телефона
@pytest.mark.django_db
def test_create_contact_invalid_phone():
    user = User.objects.create_user(email='test@test.com', password='pass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/contacts/', {
        'city': 'Moscow',
        'street': 'Tverskaya',
        'house': '1',
        'phone': 'abc123'
    })
    assert response.status_code == 400
    assert 'Телефон должен содержать только цифры и может начинаться с +' in response.data['phone'][0]

# Тест: отсутствие обязательного поля city
@pytest.mark.django_db
def test_create_contact_missing_city():
    user = User.objects.create_user(email='test@test.com', password='pass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/contacts/', {
        'street': 'Tverskaya',
        'house': '1',
        'phone': '+79161234567'
    })
    assert response.status_code == 400
    assert 'city' in response.data

# Тест: успешное создание контакта
@pytest.mark.django_db
def test_create_contact_success():
    user = User.objects.create_user(email='test@test.com', password='pass', username='testuser')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/contacts/', {
        'city': 'Moscow',
        'street': 'Tverskaya',
        'house': '15',
        'phone': '+79161234567'
    })
    assert response.status_code == 201
    assert response.data['city'] == 'Moscow'
    assert Contact.objects.filter(user=user, phone='+79161234567').exists()

# Тест: успешное получение списка контактов
@pytest.mark.django_db
def test_get_contacts_success():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/contacts/')
    assert response.status_code == 200
    assert len(response.data) == 1
    assert response.data[0]['city'] == 'Moscow'

# Тест: получение контактов без авторизации
@pytest.mark.django_db
def test_get_contacts_unauthorized():
    client = APIClient()
    response = client.get('/api/contacts/')
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'

# Тест: у пользователя нет контактов
@pytest.mark.django_db
def test_get_contacts_empty():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get('/api/contacts/')
    assert response.status_code == 200
    assert response.data == []

# Тест: успешное удаление контакта
@pytest.mark.django_db
def test_delete_contact_success():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    contact = Contact.objects.create(user=user, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete(f'/api/contacts/{contact.id}/')
    assert response.status_code == 200
    assert response.data['message'] == 'Контакт удален'
    assert Contact.objects.count() == 0

# Тест: удаление чужого контакта
@pytest.mark.django_db
def test_delete_contact_foreign():
    user1 = User.objects.create_user(email='test1@test.com', password='testpass', username='user1')
    user2 = User.objects.create_user(email='test2@test.com', password='testpass', username='user2')
    contact = Contact.objects.create(user=user1, city='Moscow', street='Tverskaya', house='1', phone='123')
    client = APIClient()
    client.force_authenticate(user=user2)
    response = client.delete(f'/api/contacts/{contact.id}/')
    assert response.status_code == 404
    assert response.data['error'] == 'Контакт не найден'

# Тест: удаление несуществующего контакта
@pytest.mark.django_db
def test_delete_contact_not_found():
    user = User.objects.create_user(email='test@test.com', password='testpass')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.delete('/api/contacts/999/')
    assert response.status_code == 404
    assert response.data['error'] == 'Контакт не найден'

# Тест: удаление без авторизации
@pytest.mark.django_db
def test_delete_contact_unauthorized():
    client = APIClient()
    response = client.delete('/api/contacts/1/')
    assert response.status_code == 401
    assert response.data['error'] == 'Необходимо авторизоваться'