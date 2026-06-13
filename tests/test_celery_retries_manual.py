import pytest
from unittest.mock import patch
from celery import current_app
from backend.tasks import do_import_task, do_export_orders_task, do_export_products_task
from backend.models import Shop
from users.models import User


# Тест проверяет, что при сбое базы данных задача импорта товаров делает 3 повторные попытки (retry)
@pytest.mark.django_db
def test_do_import_task_retries_3_times():
    # Включаем синхронный режим и убираем задержку для скорости теста
    current_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)
    current_app.conf.update(CELERY_TASK_EAGER_PROPAGATES=False)

    user = User.objects.create_user(email='test@test.com', password='pass', username='test', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=user, yaml_file='test.yaml')

    with patch('backend.tasks.import_from_yaml') as mock_import_func:
        # Заставляем функцию всегда падать с ошибкой
        mock_import_func.side_effect = Exception("Сбой импорта")

        # Запускаем задачу
        result = do_import_task.apply(args=[shop.yaml_file])

        # Проверяем, что задача упала
        assert result.failed()

        # Проверяем, что функцию вызвали 4 раза (1 попытка + 3 retry)
        assert mock_import_func.call_count == 4


# Тест проверяет, что при сбое базы данных задача экспорта заказов делает 3 повторные попытки (retry)
@pytest.mark.django_db
def test_do_export_orders_task_retries_3_times():
    # Включаем синхронный режим и убираем задержку для скорости теста
    current_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)
    current_app.conf.update(CELERY_TASK_EAGER_PROPAGATES=False)

    user = User.objects.create_user(email='test@test.com', password='pass', username='test', type='storekeeper')

    with patch('backend.models.Order.objects.filter') as mock_filter:
        # Заставляем метод filter всегда падать с ошибкой
        mock_filter.side_effect = Exception("Сбой базы данных")

        # Запускаем задачу
        result = do_export_orders_task.apply(args=[user.id, {}])

        # Проверяем, что задача упала
        assert result.failed()

        # Проверяем, что метод filter был вызван 4 раза (1 попытка + 3 retry)
        assert mock_filter.call_count == 4


# Тест проверяет, что при сбое базы данных задача экспорта товаров делает 3 повторные попытки (retry)
@pytest.mark.django_db
def test_do_export_products_task_retries_3_times():
    # Включаем синхронный режим и убираем задержку для скорости теста
    current_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)
    current_app.conf.update(CELERY_TASK_EAGER_PROPAGATES=False)

    user = User.objects.create_user(email='test@test.com', password='pass', username='test', type='storekeeper')

    with patch('backend.models.ProductInfo.objects.all') as mock_all:
        # Заставляем метод all всегда падать с ошибкой
        mock_all.side_effect = Exception("Сбой базы данных")

        # Запускаем задачу
        result = do_export_products_task.apply(args=[user.id, {}])

        # Проверяем, что задача упала
        assert result.failed()

        # Проверяем, что метод all был вызван 4 раза (1 попытка + 3 retry)
        assert mock_all.call_count == 4