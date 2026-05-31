# API Документация

Базовый URL: `http://127.0.0.1:8000/api/`

## Аутентификация
Токен передаётся в заголовке: `Authorization: Token <token>`

---

## Регистрация
**POST** `/register/`

**Тело запроса:**

json
{
    "first_name": "Иван",
    "last_name": "Иванов",
    "email": "user@example.com",
    "password": "123456"
}

**Ответ:**

json
{
    "message": "Пользователь создан"
}

## Вход (логин)

POST /login/

**Тело запроса:**

json
{
    "username": "user@example.com",
    "password": "123456"
}

**Ответ:**

json
{
    "token": "ваш_токен"
}

## Выход (логаут)

POST /logout/

Требуется токен

**Ответ:**

json
{
    "message": "Вы вышли из системы"
}

## Восстановление пароля
POST /password-reset/

**Тело запроса:**

json
{
    "email": "user@example.com"
}

**Ответ:**

json
{
    "reset_token": "токен_сброса"
}

## Подтверждение сброса пароля
POST /password-reset/confirm/

**Тело запроса:**

json
{
    "token": "токен_сброса",
    "new_password": "новый_пароль"
}

**Ответ:**

json
{
    "message": "Пароль изменён"
}

## Список товаров (с фильтрацией и поиском)
GET /products/

**Параметры фильтрации:**

- ?shop=1 — по магазину
- ?product__category=5 — по категории
- ?search=doll — поиск по названию

**Ответ:**

json
[
    {
        "id": 66,
        "product_name": "Название товара",
        "shop_name": "Магазин",
        "price": 120,
        "price_rrc": 150
    }
]

## Детали одного товара

GET /products/id/

**Ответ:**

как у списка, но один объект

## Список магазинов для товара

GET /products/<product_id>/shops/

**Ответ:**

json
[
    {
        "product_info_id": 66,
        "shop_name": "Магазин",
        "price": 120,
        "price_rrc": 150,
        "quantity": 10
    }
]

## Корзина

GET /cart/ — просмотр

POST /cart/ — добавить

PUT /cart/ — изменить количество

DELETE /cart/ — удалить товар

Требуется токен

**Тело POST / PUT:**

json
{
    "product_info_id": 66,
    "quantity": 2
}

**Ответ GET:**

{
    "cart": [
        {
            "id": 7,
            "product_name": "Товар",
            "shop_name": "Магазин",
            "quantity": 2,
            "price": 120,
            "total": 240
        }
    ],
    "total_sum": 240
}

## Контакты

GET /contacts/ — список

POST /contacts/ — добавить

DELETE /contacts/<id>/ — удалить

Требуется токен

**Тело POST:**

json
{
    "city": "Москва",
    "street": "Тверская",
    "house": "1",
    "phone": "+79991234567"
}

**Ответ:**

json
{
    "id": 2,
    "city": "Москва",
    "street": "Тверская",
    "house": "1",
    "phone": "+79991234567",
    "user": 4
}

## Оформление заказа

POST /order/create/

Требуется токен

**Тело запроса:**

json
{
    "contact_id": 2
}

**Ответ:**

json
{
    "message": "Заказ оформлен",
    "order_id": 3
}

## Список заказов пользователя

GET /orders/

Требуется токен

**Ответ:**

json
[
    {
        "id": 3,
        "dt": "2026-05-31T...",
        "state": "new",
        "contact": "Москва, Тверская 1",
        "total": 240
    }
]

## Детали заказа

GET /orders/id/

Требуется токен

**Ответ:**

включает список товаров с ценами и магазинами

## Отмена заказа (покупатель)

POST /orders/id/cancel/

Требуется токен

**Ответ:**

json
{
    "message": "Заказ отменён"
}

## Изменение статуса заказа (поставщик)

PATCH /orders/id/status/

Требуется токен поставщика

**Тело запроса:**

json
{
    "state": "confirmed"
}

**Ответ:**

json
{
    "message": "Статус заказа изменён на confirmed"
}

## Заказы поставщика

GET /supplier/orders/

Требуется токен поставщика

**Ответ:**

список заказов, содержащих товары поставщика

## Импорт прайса (поставщик)

POST /import/

Требуется токен поставщика

**Тело запроса:**

json
{
    "shop_id": 2
}

**Ответ:**

json
{
    "message": "Импорт для магазина ЗооМир-2 выполнен"
}

## Документация Swagger

- JSON схема: /api/schema/
- UI: /api/docs/



















