import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from backend.admin import run_import
from backend.models import Shop
from users.models import User
from unittest.mock import patch


@pytest.mark.django_db
def test_admin_import_action():
    # Создаём пользователя-администратора с правами
    admin_user = User.objects.create_superuser(email='admin@test.com', password='pass', username='admin')
    shop = Shop.objects.create(name='Test Shop', user=admin_user, yaml_file='test.yaml')

    # Мокаем задачу Celery
    with patch('backend.tasks.do_import_task.delay') as mock_delay:
        # Создаём запрос к админке
        request = type('Request', (), {'user': admin_user})()
        # Вызываем действие, передавая queryset с магазином
        queryset = Shop.objects.filter(id=shop.id)
        run_import(None, request, queryset)

        # Проверяем, что задача запущена ровно один раз
        mock_delay.assert_called_once_with(shop.yaml_file)