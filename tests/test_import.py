import pytest
from unittest.mock import Mock, patch, mock_open
from users.models import User
from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter
from import_data import import_from_yaml
import tempfile
import yaml
from rest_framework.test import APIClient
from celery import current_app
from backend.tasks import do_import_task
import os


# ========== 1. НЕТ ПОЧТЫ ==========
def test_missing_owner_email():
    data = {'shop': 'Test', 'owner_email': None, 'categories': [], 'goods': []}
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('builtins.print') as mock_print:
                import_from_yaml('fake.yaml')
                mock_print.assert_any_call("ОШИБКА: Нет owner_email в файле")


# ========== 2. НЕТ ПОСТАВЩИКА ==========
def test_supplier_not_found():
    data = {'shop': 'Test', 'owner_email': 'test@example.com', 'categories': [], 'goods': []}
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get:
                mock_user_get.side_effect = User.DoesNotExist()
                with patch('builtins.print') as mock_print:
                    import_from_yaml('fake.yaml')
                    mock_print.assert_any_call("ОШИБКА: Поставщик 'test@example.com' не найден.")


# ========== 3. НЕТ МАГАЗИНА ==========
def test_shop_not_found():
    data = {'shop': 'Test', 'owner_email': 'test@example.com', 'categories': [], 'goods': []}
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get:
                mock_user_get.return_value = Mock()
                with patch('import_data.Shop.objects.get') as mock_shop_get:
                    mock_shop_get.side_effect = Shop.DoesNotExist()
                    with patch('builtins.print') as mock_print:
                        import_from_yaml('fake.yaml')
                        mock_print.assert_any_call("ОШИБКА: Магазин 'Test' не найден у этого поставщика.")


# ========== 4. НОВАЯ КАТЕГОРИЯ ==========
def test_create_new_category():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Category.objects.create') as mock_cat_create, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('import_data.ProductInfo.objects.create'), \
                    patch('import_data.Parameter.objects.get_or_create'), \
                    patch('import_data.ProductParameter.objects.create'), \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()
                mock_cat_get.side_effect = Category.DoesNotExist()
                mock_cat_create.return_value = Mock(id=1, name='Cat')
                mock_prod_get.return_value = (Mock(), True)
                mock_info_get.side_effect = ProductInfo.DoesNotExist

                import_from_yaml('fake.yaml')
                mock_print.assert_any_call("Создана новая категория: 'Cat' (ID: 1)")


# ========== 5. НЕТ ОПИСАНИЯ КАТЕГОРИИ ==========
def test_category_no_description():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 2, 'name': 'Books'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()
                # Мокаем get, чтобы он не падал, но логика YAML проверит отсутствие описания раньше
                mock_cat_get.return_value = Mock(name='Books')

                import_from_yaml('fake.yaml')
                assert any("ID 1: Нет описания" in str(call) for call in mock_print.call_args_list)


# ========== 6. НЕВЕРНОЕ НАЗВАНИЕ КАТЕГОРИИ ==========
def test_category_name_conflict():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Electronics'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()
                mock_cat_get.return_value = Mock(name='Wrong Name')

                import_from_yaml('fake.yaml')
                assert any("Конфликт имен" in str(call) for call in mock_print.call_args_list)


# ========== 7. УСПЕШНЫЙ ИМПОРТ ==========
def test_successful_import():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {'Color': 'Red'}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('import_data.ProductInfo.objects.create') as mock_info_create, \
                    patch('import_data.Parameter.objects.get_or_create') as mock_param_get, \
                    patch('import_data.ProductParameter.objects.create') as mock_pp_create, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                # ВАЖНО: Возвращаем объект категории с правильным именем
                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.return_value = (Mock(), True)
                mock_info_get.side_effect = ProductInfo.DoesNotExist
                mock_param_get.return_value = (Mock(), True)

                import_from_yaml('fake.yaml')
                mock_info_create.assert_called_once()
                assert mock_pp_create.call_count == 1


# ========== 8. ТОВАР БЕЗ ПАРАМЕТРОВ ==========
def test_product_without_params():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Simple', 'price': 100, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('import_data.ProductInfo.objects.create') as mock_info_create, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.return_value = (Mock(), True)
                mock_info_get.side_effect = ProductInfo.DoesNotExist

                import_from_yaml('fake.yaml')
                mock_info_create.assert_called_once()


# ========== 9. ТОВАР БЕЗ НАЗВАНИЯ ==========
def test_product_without_name():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': '', 'price': 100, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                import_from_yaml('fake.yaml')
                assert any("не имеет названия" in str(call) for call in mock_print.call_args_list)


# ========== 10. ТОВАР БЕЗ ЦЕНЫ ==========
def test_product_without_price():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': None, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                import_from_yaml('fake.yaml')
                assert any("не имеет цены" in str(call) for call in mock_print.call_args_list)


# ========== 11. ТОВАР УЖЕ СУЩЕСТВУЕТ (ПРОПУСК) ==========
def test_product_exists_skip():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.return_value = (Mock(), False)

                mock_info = Mock()
                mock_info.price = 100
                mock_info.quantity = 1
                mock_info.save = Mock()
                mock_info_get.return_value = mock_info

                import_from_yaml('fake.yaml')
                assert any("Пропущено (без изменений)" in str(call) for call in mock_print.call_args_list)


# ========== 12. ТОВАР С ДРУГИМИ ПАРАМЕТРАМИ = НОВЫЙ ==========
def test_different_params_new_product():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [
            {'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {'A': '1'}},
            {'category': 1, 'name': 'Item', 'price': 100, 'quantity': 1, 'parameters': {'A': '2'}}
        ]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('import_data.ProductInfo.objects.create'), \
                    patch('import_data.Parameter.objects.get_or_create') as mock_param_get, \
                    patch('import_data.ProductParameter.objects.create'), \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.side_effect = [(Mock(), True), (Mock(), True)]
                mock_info_get.side_effect = ProductInfo.DoesNotExist
                mock_param_get.return_value = (Mock(), True)

                import_from_yaml('fake.yaml')
                assert mock_prod_get.call_count == 2


# ========== 13. ОБНОВЛЯЕТСЯ ТОЛЬКО ЦЕНА ==========
def test_update_only_price():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 90, 'quantity': 1, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.return_value = (Mock(), False)

                mock_info = Mock()
                mock_info.price = 100  # Старая цена
                mock_info.quantity = 1  # Количество то же
                mock_info.save = Mock()
                mock_info_get.return_value = mock_info

                import_from_yaml('fake.yaml')

                assert mock_info.save.called
                assert mock_info.price == 90
                assert mock_info.quantity == 1
                assert any("ОБНОВЛЕНА ЦЕНА" in str(c) for c in mock_print.call_args_list)


# ========== 14. ОБНОВЛЯЕТСЯ ТОЛЬКО КОЛИЧЕСТВО ==========
def test_update_only_quantity():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 100, 'quantity': 5, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.return_value = (Mock(), False)

                mock_info = Mock()
                mock_info.price = 100  # Цена та же
                mock_info.quantity = 1  # Старое количество
                mock_info.save = Mock()
                mock_info_get.return_value = mock_info

                import_from_yaml('fake.yaml')

                assert mock_info.save.called
                assert mock_info.price == 100
                assert mock_info.quantity == 5
                assert not any("ОБНОВЛЕНА ЦЕНА" in str(c) for c in mock_print.call_args_list)


# ========== 15. ОБНОВЛЯЮТСЯ И ЦЕНА, И КОЛИЧЕСТВО ==========
def test_update_both_price_and_quantity():
    data = {
        'shop': 'Test', 'owner_email': 'test@example.com',
        'categories': [{'id': 1, 'name': 'Cat'}],
        'goods': [{'category': 1, 'name': 'Item', 'price': 90, 'quantity': 5, 'parameters': {}}]
    }
    with patch('builtins.open', mock_open(read_data=str(data))):
        with patch('yaml.safe_load', return_value=data):
            with patch('import_data.User.objects.get') as mock_user_get, \
                    patch('import_data.Shop.objects.get') as mock_shop_get, \
                    patch('import_data.Category.objects.get') as mock_cat_get, \
                    patch('import_data.Product.objects.get_or_create') as mock_prod_get, \
                    patch('import_data.ProductInfo.objects.get') as mock_info_get, \
                    patch('builtins.print') as mock_print:
                mock_user_get.return_value = Mock()
                mock_shop_get.return_value = Mock()

                mock_cat = Mock()
                mock_cat.name = 'Cat'
                mock_cat_get.return_value = mock_cat

                mock_prod_get.return_value = (Mock(), False)

                mock_info = Mock()
                mock_info.price = 100  # Старая цена
                mock_info.quantity = 1  # Старое количество
                mock_info.save = Mock()
                mock_info_get.return_value = mock_info

                import_from_yaml('fake.yaml')

                assert mock_info.save.called
                assert mock_info.price == 90
                assert mock_info.quantity == 5
                assert any("ОБНОВЛЕНА ЦЕНА" in str(c) for c in mock_print.call_args_list)

#=======================================================#
### ИМПОРТ ПОСТАВЩИКОМ ###
#=======================================================#

# Тест: успешный импорт прайса (асинхронный)
@pytest.mark.django_db
def test_import_price_success():
    current_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)
    user = User.objects.create_user(email='supplier@test.com', password='testpass', username='supplier',
                                    type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=user, yaml_file='temp_import.yaml')

    # Создаём временный YAML-файл
    data = {
        'shop': 'Test Shop',
        'owner_email': 'supplier@test.com',
        'categories': [{'id': 1, 'name': 'Electronics'}],
        'goods': [{
            'category': 1,
            'name': 'Laptop',
            'price': 1000,
            'price_rrc': 1200,
            'quantity': 10,  # <-- добавить
            'parameters': {}
        }]
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(data, f)
        temp_path = f.name

    shop.yaml_file = temp_path
    shop.save()

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/import/', {'shop_id': shop.id})

    assert response.status_code == 200
    assert response.data['message'] == f'Задача импорта для магазина {shop.name} запущена'
    assert ProductInfo.objects.filter(product__name='Laptop').exists()

    # Удаляем временный файл
    import os
    os.unlink(temp_path)


# Тест: импорт с неверным shop_id
@pytest.mark.django_db
def test_import_price_wrong_shop():
    user = User.objects.create_user(email='supplier@test.com', password='testpass', username='supplier',
                                    type='supplier')
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/import/', {'shop_id': 999})
    assert response.status_code == 404
    assert response.data['error'] == 'Магазин не найден или не принадлежит вам'


# Тест на обработку ошибки импорта
@pytest.mark.django_db
def test_import_task_handles_exception():
    current_app.conf.update(CELERY_TASK_ALWAYS_EAGER=True)

    user = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=user, yaml_file='dummy.yaml')

    with patch('backend.tasks.import_from_yaml') as mock_import:
        mock_import.side_effect = Exception("Network error")

        result = do_import_task.apply(args=[shop.yaml_file])

        assert result.failed()
        assert isinstance(result.result, Exception)


# Тест: импорт отклоняет товар с количеством 0
@pytest.mark.django_db
def test_import_skip_zero_quantity():
    user = User.objects.create_user(email='supplier@test.com', password='pass', username='supplier', type='supplier')
    shop = Shop.objects.create(name='Test Shop', user=user, yaml_file='temp_import.yaml')

    data = {
        'shop': 'Test Shop',
        'owner_email': 'supplier@test.com',
        'categories': [{'id': 1, 'name': 'Electronics'}],
        'goods': [{'category': 1, 'name': 'Laptop', 'price': 1000, 'price_rrc': 1200, 'quantity': 0, 'parameters': {}}]
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(data, f)
        temp_path = f.name

    shop.yaml_file = temp_path
    shop.save()

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post('/api/import/', {'shop_id': shop.id})

    assert response.status_code == 200
    assert not ProductInfo.objects.filter(product__name='Laptop').exists()

    os.unlink(temp_path)
