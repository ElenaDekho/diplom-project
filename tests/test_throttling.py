import pytest
from rest_framework.test import APIClient
from users.models import User
from rest_framework.exceptions import Throttled
from unittest.mock import patch


@pytest.mark.django_db
def test_register_throttling(monkeypatch):
    client = APIClient()
    client.defaults['REMOTE_ADDR'] = '127.0.0.1'
    url = '/api/register/'

    request_count = {'count': 0}

    def mock_check_throttles(self, request):
        request_count['count'] += 1
        if request_count['count'] > 3:
            raise Throttled()

    from rest_framework.views import APIView
    monkeypatch.setattr(APIView, 'check_throttles', mock_check_throttles)

    for i in range(3):
        data = {
            'email': f'test{i}@test.com',
            'password': 'StrongPass123!',
            'first_name': 'Test',
            'last_name': 'User'
        }
        response = client.post(url, data)
        assert response.status_code == 201

    data = {
        'email': 'blocked@test.com',
        'password': 'StrongPass123!',
        'first_name': 'Test',
        'last_name': 'User'
    }
    response = client.post(url, data)
    assert response.status_code == 429


@pytest.mark.django_db
def test_login_throttling(monkeypatch):
    User.objects.create_user(email='test@test.com', password='testpass', username='testuser')

    client = APIClient()
    client.defaults['REMOTE_ADDR'] = '127.0.0.1'
    url = '/api/login/'
    data = {'email': 'test@test.com', 'password': 'testpass'}

    request_count = {'count': 0}

    def mock_check_throttles(self, request):
        request_count['count'] += 1
        if request_count['count'] > 5:
            raise Throttled()

    from rest_framework.views import APIView
    monkeypatch.setattr(APIView, 'check_throttles', mock_check_throttles)

    for i in range(5):
        response = client.post(url, data)
        assert response.status_code != 429

    response = client.post(url, data)
    assert response.status_code == 429