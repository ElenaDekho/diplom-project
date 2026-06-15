import os
import django
import yaml
from yaml.scanner import ScannerError

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from backend.models import Shop, Category, Product, ProductInfo, Parameter, ProductParameter
from users.models import User


def import_from_yaml(file_path):
    print(f"DEBUG: Начался импорт файла {file_path}")
    if not file_path:
        print(f"ОШИБКА: Не указан путь к файлу для магазина")
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
    except FileNotFoundError:
        print(f"ОШИБКА: Файл '{file_path}' не найден")
        return
    except yaml.scanner.ScannerError as e:
        print(f"ОШИБКА: Неверный синтаксис YAML: {e}")
        return
    except Exception as e:
        print(f"ОШИБКА при открытии или чтении файла: {e}")
        return

    try:
        shop_name = data['shop']
        owner_email = data.get('owner_email')
        categories = data['categories']
        goods = data['goods']
    except KeyError as e:
        print(f"ОШИБКА: В файле отсутствует обязательное поле: {e}")
        return

    shop_name = data['shop']
    owner_email = data.get('owner_email')

    # НЕТ ПОЧТЫ
    if not owner_email:
        print("ОШИБКА: Нет owner_email в файле")
        return

    # НЕТ ПОСТАВЩИКА
    try:
        owner = User.objects.get(email=owner_email, type='supplier')
    except User.DoesNotExist:
        print(f"ОШИБКА: Поставщик '{owner_email}' не найден.")
        return

    # НЕТ МАГАЗИНА
    try:
        shop = Shop.objects.get(name=shop_name, user=owner)
    except Shop.DoesNotExist:
        print(f"ОШИБКА: Магазин '{shop_name}' не найден у этого поставщика.")
        return

    print(f"Начинаем импорт для магазина '{shop_name}'...")

    # Проверка категорий
    used_cat_ids = set(item['category'] for item in data['goods'])
    valid_cats = {}
    bad_cats = []

    for cid in used_cat_ids:
        cat_name_in_file = None
        for c in data['categories']:
            if c['id'] == cid:
                cat_name_in_file = c['name']
                break

        # НЕТ ОПИСАНИЯ КАТЕГОРИИ
        if not cat_name_in_file:
            bad_cats.append(f"ID {cid}: Нет описания в файле YAML")
            continue

        try:
            db_cat = Category.objects.get(id=cid)
            # НЕВЕРНОЕ НАЗВАНИЕ КАТЕГОРИИ
            if db_cat.name != cat_name_in_file:
                bad_cats.append(f"ID {cid}: Конфликт имен. В базе: '{db_cat.name}', В файле: '{cat_name_in_file}'")
            else:
                valid_cats[cid] = db_cat
        except Category.DoesNotExist:
            # НОВАЯ КАТЕГОРИЯ
            new_cat = Category.objects.create(id=cid, name=cat_name_in_file)
            valid_cats[cid] = new_cat
            print(f"Создана новая категория: '{cat_name_in_file}' (ID: {cid})")

    if bad_cats:
        print("\n--- ОШИБКИ КАТЕГОРИЙ ---")
        for err in bad_cats:
            print(err)
        print("--------------------------\n")

    # Импорт товаров
    added = 0
    updated_price = 0
    skipped = 0
    rejected = 0

    for item in data['goods']:
        cid = item['category']

        if any(f"ID {cid}:" in err for err in bad_cats):
            rejected += 1
            continue

        if cid not in valid_cats:
            rejected += 1
            continue

        # ТОВАР БЕЗ НАЗВАНИЯ
        name = item.get('name')
        if not name or not str(name).strip():
            print(f"ОШИБКА: Товар в категории {cid} не имеет названия. Пропущено.")
            rejected += 1
            continue

        # ТОВАР БЕЗ ЦЕНЫ
        price = item.get('price')
        if price is None:
            print(f"ОШИБКА: Товар '{name}' не имеет цены. Пропущено.")
            rejected += 1
            continue

        # ТОВАР С НУЛЕВЫМ ИЛИ ОТРИЦАТЕЛЬНЫМ КОЛИЧЕСТВОМ
        quantity = item.get('quantity', 0)
        if quantity <= 0:
            print(f"ОШИБКА: Товар '{name}' пропущен. Количество должно быть больше 0, получено: {quantity}")
            rejected += 1
            continue

        category_obj = valid_cats[cid]

        # Уникальность товара
        params_dict = item.get('parameters', {})
        params_part = "-".join([f"{k}:{v}" for k, v in sorted(params_dict.items())])
        unique_name = name
        if params_part:
            unique_name += f" | {params_part}"
        if len(unique_name) > 200:
            unique_name = unique_name[:200]

        prod, created_prod = Product.objects.get_or_create(
            name=unique_name,
            defaults={'category': category_obj}
        )

        # Привязка к магазину
        try:
            info = ProductInfo.objects.get(product=prod, shop=shop)
            created_info = False
        except ProductInfo.DoesNotExist:
            info = ProductInfo.objects.create(
                product=prod,
                shop=shop,
                price=price,
                price_rrc=item.get('price_rrc', price),
                quantity=item.get('quantity', 0)
            )
            created_info = True

        if created_info:
            # УСПЕШНЫЙ ИМПОРТ / 8. ТОВАР БЕЗ ПАРАМЕТРОВ
            for pname, pval in params_dict.items():
                param, _ = Parameter.objects.get_or_create(name=pname)
                ProductParameter.objects.create(
                    product_info=info,
                    parameter=param,
                    value=str(pval)
                )
            added += 1
        else:
            # ТОВАР УЖЕ СУЩЕСТВУЕТ
            old_price = info.price
            old_quantity = info.quantity

            new_price = price
            new_quantity = item.get('quantity', 0)

            is_updated = False

            # ОБНОВЛЯЕТСЯ ЦЕНА (независимо от количества)
            if old_price != new_price:
                info.price = new_price
                info.price_rrc = item.get('price_rrc', new_price)
                print(f"ОБНОВЛЕНА ЦЕНА: {unique_name} в {shop.name}. Было: {old_price}, Стало: {new_price}")
                updated_price += 1
                is_updated = True

            # ОБНОВЛЯЕТСЯ КОЛИЧЕСТВО (независимо от цены)
            if old_quantity != new_quantity:
                info.quantity = new_quantity
                is_updated = True

            # ОБНОВИЛОСЬ И ТО, И ДРУГОЕ (логика выше покрывает это автоматически)
            if is_updated:
                info.save()
            else:
                skipped += 1

    print(f"\nИтог:")
    print(f"Добавлено новых товаров: {added}")
    print(f"Обновлено цен: {updated_price}")
    print(f"Пропущено (без изменений): {skipped}")
    print(f"Отклонено (ошибки данных/категорий): {rejected}")


if __name__ == '__main__':
    shops = Shop.objects.all()
    for shop in shops:
        if shop.yaml_file:
            print(f"\n--- Импорт для магазина: {shop.name} ---")
            try:
                import_from_yaml(shop.yaml_file)
            except FileNotFoundError:
                print(f"ОШИБКА: Файл '{shop.yaml_file}' не найден.")
        else:
            print(f"\n--- Пропуск магазина {shop.name}: не указан yaml_file ---")