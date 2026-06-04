import pytest
from rest_framework.test import APIClient
from users.models import User, EmailConfirmationToken
from unittest.mock import patch

# Тест: успешный логин
@pytest.mark.django_db
def test_login_success():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    response = client.post('/api/login/', {'email': 'test@test.com', 'password': 'testpass'})
    assert response.status_code == 200
    assert 'token' in response.data

# Тест: пользователь не найден
@pytest.mark.django_db
def test_login_user_not_found():
    client = APIClient()
    response = client.post('/api/login/', {'email': 'unknown@test.com', 'password': 'testpass'})
    assert response.status_code == 400
    assert response.data['non_field_errors'][0] == 'Неверные учетные данные'

# Тест: неверный пароль
@pytest.mark.django_db
def test_login_wrong_password():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    response = client.post('/api/login/', {'email': 'test@test.com', 'password': 'wrongpass'})
    assert response.status_code == 400
    assert response.data['non_field_errors'][0] == 'Неверные учетные данные'

# Тест: успешный выход
@pytest.mark.django_db
def test_logout_success():
    user = User.objects.create_user(email='test@test.com', password='testpass', username='testuser')
    client = APIClient()
    # Получаем токен
    response = client.post('/api/login/', {'email': 'test@test.com', 'password': 'testpass'})
    token = response.data['token']
    # Выход
    client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
    response = client.post('/api/logout/')
    assert response.status_code == 200
    assert response.data['message'] == 'Вы вышли из системы'

# Тест: выход без авторизации
@pytest.mark.django_db
def test_logout_unauthorized():
    client = APIClient()
    response = client.post('/api/logout/')
    assert response.status_code == 401
    assert response.data['error'] == 'Вы не авторизованы'

# Тест: успешная регистрация
@pytest.mark.django_db
def test_register_success():
    client = APIClient()
    response = client.post('/api/register/', {
        'email': 'newuser@test.com',
        'password': 'testpass',
        'first_name': 'Test',
        'last_name': 'User'
    })
    assert response.status_code == 201
    assert response.data['message'] == 'Пользователь создан'
    assert User.objects.filter(email='newuser@test.com').exists()

# Тест: регистрация с существующим email
@pytest.mark.django_db
def test_register_duplicate_email():
    User.objects.create_user(email='existing@test.com', password='testpass', username='existing')
    client = APIClient()
    response = client.post('/api/register/', {
        'email': 'existing@test.com',
        'password': 'testpass'
    })
    assert response.status_code == 400
    assert 'email' in response.data

# Тест: регистрация с некорректным email
@pytest.mark.django_db
def test_register_invalid_email():
    client = APIClient()
    response = client.post('/api/register/', {
        'email': 'not-an-email',
        'password': 'testpass'
    })
    assert response.status_code == 400


# Тест: запрос сброса пароля (получение токена)
@pytest.mark.django_db
def test_password_reset_request():
    user = User.objects.create_user(email='test@test.com', password='oldpass', username='testuser')
    client = APIClient()
    response = client.post('/api/password-reset/', {'email': 'test@test.com'})
    assert response.status_code == 200
    assert 'reset_token' in response.data


# Тест: запрос сброса для несуществующего email
@pytest.mark.django_db
def test_password_reset_request_email_not_found():
    client = APIClient()
    response = client.post('/api/password-reset/', {'email': 'unknown@test.com'})
    assert response.status_code == 404
    assert response.data['error'] == 'Пользователь с таким email не найден'


# Тест: подтверждение сброса пароля
@pytest.mark.django_db
def test_password_reset_confirm():
    user = User.objects.create_user(email='test@test.com', password='oldpass', username='testuser')
    client = APIClient()
    reset_response = client.post('/api/password-reset/', {'email': 'test@test.com'})
    token = reset_response.data['reset_token']

    response = client.post('/api/password-reset/confirm/', {
        'token': token,
        'new_password': 'newpass123'
    })
    assert response.status_code == 200
    assert response.data['message'] == 'Пароль изменён'

    # Проверяем, что новый пароль работает
    login_response = client.post('/api/login/', {'email': 'test@test.com', 'password': 'newpass123'})
    assert login_response.status_code == 200


# Тест: подтверждение регистрации по email
@pytest.mark.django_db
@patch('backend.serializers.send_mail')
def test_email_confirmation_flow(mock_send_mail):
    # Регистрация
    client = APIClient()
    response = client.post('/api/register/', {
        'email': 'confirm@test.com',
        'password': 'testpass'
    })
    assert response.status_code == 201

    # Получаем токен из базы
    token_obj = EmailConfirmationToken.objects.get(user__email='confirm@test.com')
    token = token_obj.token

    # Подтверждение
    response = client.get(f'/api/confirm-email/{token}/')
    assert response.status_code == 200
    assert response.data['message'] == 'Email подтверждён'

    # Проверяем, что пользователь активен
    user = User.objects.get(email='confirm@test.com')
    assert user.is_active == True

    # Повторное использование токена должно дать ошибку
    response = client.get(f'/api/confirm-email/{token}/')
    assert response.status_code == 400
    assert response.data['error'] == 'Неверный токен'

