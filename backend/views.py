from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserRegisterSerializer, ContactSerializer
from rest_framework.authtoken.models import Token
from .serializers import UserLoginSerializer
from rest_framework.generics import ListAPIView, RetrieveAPIView, ListCreateAPIView, DestroyAPIView
from .serializers import ProductInfoSerializer, FavoriteSerializer
from backend.models import Order, OrderItem, ProductInfo, Contact, PasswordResetToken, Favorite
from django.core.mail import send_mail
from django.conf import settings
import uuid
from users.models import User, EmailConfirmationToken
from rest_framework.permissions import IsAuthenticated
from import_data import import_from_yaml
from backend.models import Shop, STATE_CHOICES
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
import csv
from django.http import HttpResponse, FileResponse
from .tasks import send_email_task, do_import_task, do_export_orders_task, do_export_products_task
import time
import os
from drf_spectacular.utils import extend_schema, OpenApiResponse, OpenApiParameter, OpenApiRequest
from rest_framework.permissions import AllowAny


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=UserRegisterSerializer,
        responses={
            201: OpenApiResponse(description="Пользователь создан"),
            400: OpenApiResponse(description="Ошибка валидации")
        },
        description="Регистрация нового пользователя"
    )
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Пользователь создан"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        request=UserLoginSerializer,
        responses={
            200: OpenApiResponse(description="Токен авторизации"),
            400: OpenApiResponse(description="Неверные учетные данные")
        },
        description="Авторизация пользователя"
    )
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            token, _ = Token.objects.get_or_create(user=user)
            return Response({"token": token.key}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    parameters=[
        OpenApiParameter(name='shop', description='ID магазина', required=False, type=int),
        OpenApiParameter(name='product__category', description='ID категории', required=False, type=int),
        OpenApiParameter(name='search', description='Поиск по названию', required=False, type=str),
    ],
    responses={200: ProductInfoSerializer(many=True)},
    description="Список товаров с фильтрацией и поиском"
)
class ProductListView(ListAPIView):
    permission_classes = [AllowAny]
    queryset = ProductInfo.objects.all()
    serializer_class = ProductInfoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['shop', 'product__category']
    search_fields = ['product__name', 'name']


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Содержимое корзины и общая сумма")
        },
        description="Получение содержимого корзины текущего пользователя"
    )
    def get(self, request):
        user = request.user

        cart, _ = Order.objects.get_or_create(user=user, state='basket')
        items = cart.items.all()
        result = []
        for item in items:
            result.append({
                "id": item.id,
                "product_info_id": item.product_info.id,
                "product_name": item.product_info.product.name,
                "shop_name": item.product_info.shop.name,
                "quantity": item.quantity,
                "price": item.product_info.price,
                "total": item.quantity * item.product_info.price
            })

        total_sum = sum(item['total'] for item in result)
        return Response({"cart": result, "total_sum": total_sum}, status=status.HTTP_200_OK)

    @extend_schema(
        request=OpenApiRequest(
            request={
                "type": "object",
                "properties": {
                    "product_info_id": {"type": "integer", "description": "ID товара"},
                    "quantity": {"type": "integer", "description": "Количество", "default": 1}
                },
                "required": ["product_info_id"]
            }
        ),
        responses={
            200: OpenApiResponse(description="Товар добавлен в корзину"),
            400: OpenApiResponse(description="Ошибка валидации"),
            404: OpenApiResponse(description="Товар не найден")
        },
        description="Добавление товара в корзину"
    )
    def post(self, request):
        user = request.user

        product_info_id = request.data.get('product_info_id')
        try:
            quantity = int(request.data.get('quantity', 1))
        except ValueError:
            return Response({"error": "Количество должно быть числом"}, status=status.HTTP_400_BAD_REQUEST)
        if quantity <= 0:
            return Response({"error": "Количество должно быть больше 0"}, status=status.HTTP_400_BAD_REQUEST)

        if not product_info_id:
            return Response({"error": "Не указан товар"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product_info = ProductInfo.objects.get(id=product_info_id)
            if not product_info.shop.state:
                return Response({"error": "Магазин не принимает заказы"}, status=status.HTTP_400_BAD_REQUEST)
            if product_info.quantity <= 0:
                return Response({"error": "Товар отсутствует на складе"}, status=status.HTTP_400_BAD_REQUEST)
            # Проверка остатка
            if quantity > product_info.quantity:
                return Response({"error": "Недостаточно товара на складе"}, status=status.HTTP_400_BAD_REQUEST)
        except ProductInfo.DoesNotExist:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)

        cart, _ = Order.objects.get_or_create(user=user, state='basket')

        order_item, created = OrderItem.objects.get_or_create(
            order=cart,
            product_info=product_info,
            defaults={'quantity': quantity}
        )
        if not created:
            order_item.quantity += quantity
            order_item.save()

        return Response({"message": "Товар добавлен в корзину"}, status=status.HTTP_200_OK)

    @extend_schema(
        request=OpenApiRequest(
            request={
                "type": "object",
                "properties": {
                    "product_info_id": {"type": "integer", "description": "ID товара"}
                },
                "required": ["product_info_id"]
            }
        ),
        responses={
            200: OpenApiResponse(description="Товар удален из корзины"),
            400: OpenApiResponse(description="Не указан товар"),
            404: OpenApiResponse(description="Товар не найден в корзине")
        },
        description="Удаление товара из корзины"
    )
    def delete(self, request):
        user = request.user

        product_info_id = request.data.get('product_info_id')
        if not product_info_id:
            return Response({"error": "Не указан товар"}, status=status.HTTP_400_BAD_REQUEST)

        cart, _ = Order.objects.get_or_create(user=user, state='basket')
        if not cart.items.exists():
            return Response({"error": "Корзина пуста"}, status=status.HTTP_404_NOT_FOUND)

        try:
            item = OrderItem.objects.get(order=cart, product_info_id=product_info_id)
            item.delete()
            return Response({"message": "Товар удален из корзины"}, status=status.HTTP_200_OK)
        except OrderItem.DoesNotExist:
            return Response({"error": "Товар не найден в корзине"}, status=status.HTTP_404_NOT_FOUND)

    @extend_schema(
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'product_info_id': {'type': 'integer', 'description': 'ID товара'},
                    'quantity': {'type': 'integer', 'description': 'Новое количество товара'}
                },
                'required': ['product_info_id', 'quantity']
            }
        ),
        responses={
            200: OpenApiResponse(description="Количество обновлено или товар удален"),
            400: OpenApiResponse(description="Ошибка валидации данных или недостаток товара на складе"),
            404: OpenApiResponse(description="Корзина пуста или товар не найден")
        },
        description="Обновление количества товара в корзине"
    )
    def put(self, request):
        user = request.user

        product_info_id = request.data.get('product_info_id')
        quantity = request.data.get('quantity')

        if not product_info_id or quantity is None:
            return Response({"error": "Не указан товар или количество"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(quantity)
        except ValueError:
            return Response({"error": "Количество должно быть числом"}, status=status.HTTP_400_BAD_REQUEST)

        cart, _ = Order.objects.get_or_create(user=user, state='basket')
        if not cart.items.exists():
            return Response({"error": "Корзина пуста"}, status=status.HTTP_404_NOT_FOUND)

        try:
            order_item = OrderItem.objects.get(order=cart, product_info_id=product_info_id)
            if quantity > order_item.product_info.quantity:
                return Response({"error": "Недостаточно товара на складе"}, status=status.HTTP_400_BAD_REQUEST)
            if quantity <= 0:
                order_item.delete()
                return Response({"message": "Товар удален из корзины"}, status=status.HTTP_200_OK)
            else:
                order_item.quantity = quantity
                order_item.save()
                return Response({"message": "Количество обновлено"}, status=status.HTTP_200_OK)
        except OrderItem.DoesNotExist:
            return Response({"error": "Товар не найден в корзине"}, status=status.HTTP_404_NOT_FOUND)


class ContactView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ContactSerializer,
        responses={
            201: OpenApiResponse(description="Контакт успешно добавлен"),
            400: OpenApiResponse(description="Ошибка валидации или превышен лимит контактов")
        },
        description="Добавление нового контакта пользователя"
    )
    def post(self, request):
        user = request.user

        if Contact.objects.filter(user=user).count() >= 5:
            return Response({"error": "Нельзя добавить более 5 контактов"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Список контактов пользователя")
        },
        description="Получение списка всех контактов текущего пользователя"
    )
    def get(self, request):
        user = request.user

        contacts = Contact.objects.filter(user=user)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID контакта', required=True, type=int)
        ],
        responses={
            200: OpenApiResponse(description="Контакт удален"),
            404: OpenApiResponse(description="Контакт не найден")
        },
        description="Удаление контакта"
    )
    def delete(self, request, pk):
        user = request.user

        try:
            contact = Contact.objects.get(id=pk, user=user)
            contact.delete()
            return Response({"message": "Контакт удален"}, status=status.HTTP_200_OK)
        except Contact.DoesNotExist:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)


class OrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'contact_id': {'type': 'integer', 'description': 'ID контакта для доставки'}
                },
                'required': ['contact_id']
            }
        ),
        responses={
            200: OpenApiResponse(description="Заказ успешно оформлен"),
            400: OpenApiResponse(description="Ошибка валидации, пустая корзина или магазин не принимает заказы"),
            404: OpenApiResponse(description="Контакт не найден")
        },
        description="Оформление заказа из корзины"
    )
    def post(self, request):
        user = request.user

        contact_id = request.data.get('contact_id')
        if not contact_id:
            return Response({"error": "Не указан контакт"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            contact = Contact.objects.get(id=contact_id, user=user)
        except Contact.DoesNotExist:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)

        cart = Order.objects.filter(user=user, state='basket').first()
        if not cart or not cart.items.exists():
            return Response({"error": "Корзина пуста"}, status=status.HTTP_400_BAD_REQUEST)

        for item in cart.items.all():
            if not item.product_info.shop.state:
                return Response({"error": "Один из магазинов не принимает заказы"}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка остатков
        for item in cart.items.all():
            if item.quantity > item.product_info.quantity:
                return Response(
                    {"error": f"Недостаточно товара '{item.product_info.product.name}' на складе"},
                    status=status.HTTP_400_BAD_REQUEST
                )

        cart.state = 'new'
        cart.contact = contact
        cart.save()

        # Уменьшаем остатки товаров
        for item in cart.items.all():
            product_info = item.product_info
            product_info.quantity -= item.quantity
            product_info.save()

        # Подсчёт суммы
        total = sum(item.quantity * item.product_info.price for item in cart.items.all())

        # Письмо клиенту
        send_email_task.delay(
            subject='Заказ оформлен',
            message=f'Ваш заказ №{cart.id} на сумму {total} руб. оформлен.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

        # Письма поставщикам
        supplier_emails = set()
        for item in cart.items.all():
            supplier_emails.add(item.product_info.shop.user.email)

        for email in supplier_emails:
            send_email_task.delay(
                subject='Новый заказ',
                message=f'Поступил заказ №{cart.id}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )

        return Response({"message": "Заказ оформлен", "order_id": cart.id}, status=status.HTTP_200_OK)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Список заказов пользователя")
        },
        description="Получение списка всех заказов текущего пользователя (исключая корзину)"
    )
    def get(self, request):
        user = request.user

        orders = Order.objects.filter(user=user).exclude(state='basket')
        result = []
        for order in orders:
            result.append({
                "id": order.id,
                "dt": order.dt,
                "state": order.state,
                "contact": f"{order.contact.city}, {order.contact.street} {order.contact.house}" if order.contact else "",
                "total": sum(item.quantity * item.product_info.price for item in order.items.all())
            })
        return Response(result, status=status.HTTP_200_OK)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID заказа', required=True, type=int)
        ],
        responses={200: OpenApiResponse(description="Детали заказа")},
        description="Просмотр деталей заказа"
    )
    def get(self, request, pk):
        user = request.user

        try:
            order = Order.objects.get(id=pk, user=user)
        except Order.DoesNotExist:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        items = []
        for item in order.items.all():
            items.append({
                "product_name": item.product_info.product.name,
                "shop_name": item.product_info.shop.name,
                "quantity": item.quantity,
                "price": item.product_info.price,
                "total": item.quantity * item.product_info.price
            })

        result = {
            "id": order.id,
            "dt": order.dt,
            "state": order.state,
            "contact": f"{order.contact.city}, {order.contact.street} {order.contact.house}" if order.contact else "",
            "items": items,
            "total": sum(item['total'] for item in items)
        }
        return Response(result, status=status.HTTP_200_OK)


class LogoutView(APIView):
    @extend_schema(
        responses={
            200: OpenApiResponse(description="Вы вышли из системы"),
            401: OpenApiResponse(description="Вы не авторизованы")
        },
        description="Выход из системы (удаление токена)"
    )
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Вы не авторизованы"}, status=status.HTTP_401_UNAUTHORIZED)
        request.auth.delete()
        return Response({"message": "Вы вышли из системы"}, status=status.HTTP_200_OK)


class ProductShopsView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        parameters=[
            OpenApiParameter(name='product_id', description='ID товара', required=True, type=int)
        ],
        responses={200: OpenApiResponse(description="Список магазинов для товара")},
        description="Просмотр магазинов, в которых есть товар"
    )
    def get(self, request, product_id):
        product_infos = ProductInfo.objects.filter(product_id=product_id)
        if not product_infos:
            return Response({"error": "Товар не найден"}, status=status.HTTP_404_NOT_FOUND)

        result = []
        for info in product_infos:
            result.append({
                "product_info_id": info.id,
                "shop_name": info.shop.name,
                "price": info.price,
                "price_rrc": info.price_rrc,
                "quantity": info.quantity,
            })
        return Response(result, status=status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'email': {'type': 'string', 'format': 'email', 'description': 'Email пользователя'}
                },
                'required': ['email']
            }
        ),
        responses={
            200: OpenApiResponse(description="Токен сброса пароля сгенерирован"),
            404: OpenApiResponse(description="Пользователь с таким email не найден")
        },
        description="Запрос на сброс пароля (генерация токена)"
    )
    def post(self, request):
        email = request.data.get('email')
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "Пользователь с таким email не найден"}, status=status.HTTP_404_NOT_FOUND)

        token = str(uuid.uuid4())
        PasswordResetToken.objects.create(user=user, token=token)

        # В реальном проекте здесь отправка email со ссылкой
        # Для теста просто возвращаем токен
        return Response({"reset_token": token}, status=status.HTTP_200_OK)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'token': {'type': 'string', 'description': 'Токен сброса пароля'},
                    'new_password': {'type': 'string', 'description': 'Новый пароль'}
                },
                'required': ['token', 'new_password']
            }
        ),
        responses={
            200: OpenApiResponse(description="Пароль успешно изменён"),
            400: OpenApiResponse(description="Неверный или истёкший токен")
        },
        description="Подтверждение сброса пароля и установка нового пароля"
    )
    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')

        try:
            reset = PasswordResetToken.objects.get(token=token)
        except PasswordResetToken.DoesNotExist:
            return Response({"error": "Неверный токен"}, status=status.HTTP_400_BAD_REQUEST)

        if not reset.is_valid():
            return Response({"error": "Токен истёк"}, status=status.HTTP_400_BAD_REQUEST)

        user = reset.user
        user.set_password(new_password)
        user.save()
        reset.delete()

        return Response({"message": "Пароль изменён"}, status=status.HTTP_200_OK)


class ImportPriceView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'shop_id': {'type': 'integer', 'description': 'ID магазина'}
                },
                'required': ['shop_id']
            }
        ),
        responses={
            200: OpenApiResponse(description="Задача импорта запущена"),
            400: OpenApiResponse(description="Не указан shop_id или не указан yaml_file"),
            403: OpenApiResponse(description="Доступ запрещен (не поставщик)"),
            404: OpenApiResponse(description="Магазин не найден"),
            500: OpenApiResponse(description="Ошибка сервера")
        },
        description="Запуск асинхронного импорта цен из YAML-файла для магазина поставщика"
    )
    def post(self, request):
        user = request.user
        if user.type != 'supplier':
            return Response({"error": "Доступ только для поставщиков"}, status=status.HTTP_403_FORBIDDEN)

        shop_id = request.data.get('shop_id')
        if not shop_id:
            return Response({"error": "Не указан shop_id"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            shop = Shop.objects.get(id=shop_id, user=user)
        except Shop.DoesNotExist:
            return Response({"error": "Магазин не найден или не принадлежит вам"}, status=status.HTTP_404_NOT_FOUND)

        if not shop.yaml_file:
            return Response({"error": "Для магазина не указан yaml_file"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            do_import_task.delay(shop.yaml_file)
            return Response({"message": f"Задача импорта для магазина {shop.name} запущена"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SupplierOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Список новых заказов для поставщика"),
            403: OpenApiResponse(description="Доступ запрещен (не поставщик)")
        },
        description="Получение списка новых заказов, содержащих товары из магазинов текущего поставщика"
    )
    def get(self, request):
        user = request.user
        if user.type != 'supplier':
            return Response({"error": "Доступ только для поставщиков"}, status=status.HTTP_403_FORBIDDEN)

        shops = Shop.objects.filter(user=user)
        orders = Order.objects.filter(items__product_info__shop__in=shops, state='new').distinct()

        result = []
        for order in orders:
            result.append({
                "order_id": order.id,
                "contact": f"{order.contact.city}, {order.contact.street} {order.contact.house}",
                "total": sum(item.quantity * item.product_info.price for item in order.items.all())
            })
        return Response(result, status=status.HTTP_200_OK)


class ProductDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    queryset = ProductInfo.objects.all()
    serializer_class = ProductInfoSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID товара (ProductInfo)', required=True, type=int)
        ],
        responses={200: ProductInfoSerializer},
        description="Получение детальной информации о товаре"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class OrderStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID заказа', required=True, type=int)
        ],
        request=OpenApiRequest(
            request={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Новый статус (опционально)"}
                }
            }
        ),
        responses={
            200: OpenApiResponse(description="Статус обновлён"),
            400: OpenApiResponse(description="В заказе нет ваших товаров или ошибка валидации"),
            403: OpenApiResponse(description="Доступ только для поставщиков"),
            404: OpenApiResponse(description="Заказ не найден")
        },
        description="Подтверждение заказа поставщиком (частичное или полное)"
    )
    def patch(self, request, pk):
        user = request.user
        if user.type != 'supplier':
            return Response({"error": "Доступ только для поставщиков"}, status=status.HTTP_403_FORBIDDEN)

        try:
            order = Order.objects.get(id=pk)
        except Order.DoesNotExist:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        # Найти магазины поставщика в этом заказе
        supplier_shops = Shop.objects.filter(user=user)
        order_items = order.items.filter(product_info__shop__in=supplier_shops)
        if not order_items.exists():
            return Response({"error": "В заказе нет ваших товаров"}, status=status.HTTP_400_BAD_REQUEST)

        # Добавить ID магазинов поставщика в список подтверждённых
        confirmed = set(order.confirmed_shops.split(',') if order.confirmed_shops else [])
        for shop in supplier_shops:
            confirmed.add(str(shop.id))
        order.confirmed_shops = ','.join(confirmed)

        # Получить все уникальные магазины в заказе
        all_shops = set(str(item.product_info.shop.id) for item in order.items.all())
        if all_shops.issubset(confirmed):
            order.state = 'confirmed'
            # Отправка письма клиенту (только когда заказ полностью подтверждён)
            send_email_task.delay(
                subject='Статус заказа изменён',
                message=f'Ваш заказ №{order.id} теперь в статусе {dict(STATE_CHOICES)[order.state]}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.user.email],
                fail_silently=True,
            )

        order.save()
        return Response({"message": "Статус обновлён"}, status=status.HTTP_200_OK)


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID заказа', required=True, type=int)
        ],
        responses={
            200: OpenApiResponse(description="Заказ отменён"),
            400: OpenApiResponse(description="Заказ уже отменён"),
            404: OpenApiResponse(description="Заказ не найден")
        },
        description="Отмена заказа покупателем"
    )
    def post(self, request, pk):
        user = request.user

        try:
            order = Order.objects.get(id=pk, user=user)
        except Order.DoesNotExist:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        if order.state == 'canceled':
            return Response({"error": "Заказ уже отменён"}, status=status.HTTP_400_BAD_REQUEST)

        order.state = 'canceled'
        order.save()
        send_email_task.delay(
            subject='Заказ отменён',
            message=f'Ваш заказ №{order.id} был отменён.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
        return Response({"message": "Заказ отменён"}, status=status.HTTP_200_OK)


class ConfirmEmailView(APIView):
    permission_classes = [AllowAny]
    @extend_schema(
        parameters=[
            OpenApiParameter(name='token', description='Токен подтверждения email', required=True, type=str)
        ],
        responses={
            200: OpenApiResponse(description="Email подтверждён"),
            400: OpenApiResponse(description="Неверный или истекший токен")
        },
        description="Подтверждение email при регистрации"
    )
    def get(self, request, token):
        try:
            confirm_token = EmailConfirmationToken.objects.get(token=token)
        except EmailConfirmationToken.DoesNotExist:
            return Response({"error": "Неверный токен"}, status=status.HTTP_400_BAD_REQUEST)

        if not confirm_token.is_valid():
            return Response({"error": "Токен истёк"}, status=status.HTTP_400_BAD_REQUEST)

        user = confirm_token.user
        user.is_active = True
        user.save()
        confirm_token.delete()
        return Response({"message": "Email подтверждён"}, status=status.HTTP_200_OK)


class StorekeeperOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='status', description='Статус заказа (можно передать несколько)', required=False,
                             type=str, many=True),
            OpenApiParameter(name='date_from', description='Дата от (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='date_to', description='Дата до (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='shop', description='ID магазина', required=False, type=int),
        ],
        responses={
            200: OpenApiResponse(description="Список заказов для кладовщика"),
            403: OpenApiResponse(description="Доступ только для кладовщиков")
        },
        description="Просмотр заказов для кладовщика с фильтрацией"
    )
    def get(self, request):
        user = request.user
        if user.type != 'storekeeper':
            return Response({"error": "Доступ только для кладовщиков"}, status=status.HTTP_403_FORBIDDEN)

        # Фильтр по статусу
        statuses = request.query_params.getlist('status')
        if not statuses:
            statuses = ['confirmed', 'assembled', 'sent']

        orders = Order.objects.filter(state__in=statuses)

        # Фильтр по дате (пример: ?date_from=2024-01-01&date_to=2024-12-31)
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            orders = orders.filter(dt__date__gte=date_from)
        if date_to:
            orders = orders.filter(dt__date__lte=date_to)

        # Фильтр по магазину (через товары в заказе)
        shop_id = request.query_params.get('shop')
        if shop_id:
            orders = orders.filter(items__product_info__shop_id=shop_id).distinct()

        orders = orders.order_by('-dt')

        result = []
        for order in orders:
            result.append({
                "id": order.id,
                "dt": order.dt,
                "state": order.state,
                "contact": f"{order.contact.city}, {order.contact.street} {order.contact.house}" if order.contact else '',
                "total": sum(item.quantity * item.product_info.price for item in order.items.all())
            })
        return Response(result, status=status.HTTP_200_OK)


class StorekeeperOrderStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID заказа', required=True, type=int)
        ],
        request=OpenApiRequest(
            request={
                "type": "object",
                "properties": {
                    "state": {"type": "string", "description": "Новый статус (assembled, sent, delivered)"}
                },
                "required": ["state"]
            }
        ),
        responses={
            200: OpenApiResponse(description="Статус изменён"),
            400: OpenApiResponse(description="Недопустимый статус или нарушена последовательность"),
            403: OpenApiResponse(description="Доступ только для кладовщиков"),
            404: OpenApiResponse(description="Заказ не найден")
        },
        description="Изменение статуса заказа кладовщиком (с проверкой последовательности)"
    )
    def patch(self, request, pk):
        user = request.user
        if user.type != 'storekeeper':
            return Response({"error": "Доступ только для кладовщиков"}, status=status.HTTP_403_FORBIDDEN)

        try:
            order = Order.objects.get(id=pk)
        except Order.DoesNotExist:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        # Проверка последовательности статусов
        allowed_transitions = {
            'new': ['confirmed'],
            'confirmed': ['assembled'],
            'assembled': ['sent'],
            'sent': ['delivered'],
            'delivered': [],
            'canceled': []
        }

        new_status = request.data.get('state')
        if new_status not in allowed_transitions.get(order.state, []):
            return Response({"error": f"Нельзя изменить статус с {order.state} на {new_status}"},
                            status=status.HTTP_400_BAD_REQUEST)

        order.state = new_status
        order.save()

        # Отправка уведомления клиенту
        state_display = dict(STATE_CHOICES)[order.state]
        send_email_task.delay(
            subject='Статус заказа изменён',
            message=f'Ваш заказ №{order.id} теперь в статусе {state_display}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=True,
        )

        return Response({"message": f"Статус заказа изменён на {new_status}"}, status=status.HTTP_200_OK)


class StorekeeperExportOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='status', description='Статус заказа (можно несколько)', required=False, type=str,
                             many=True),
            OpenApiParameter(name='date_from', description='Дата от (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='date_to', description='Дата до (YYYY-MM-DD)', required=False, type=str),
            OpenApiParameter(name='shop', description='ID магазина', required=False, type=int),
        ],
        responses={
            200: OpenApiResponse(description="CSV-файл с заказами"),
            403: OpenApiResponse(description="Доступ только для кладовщиков"),
            404: OpenApiResponse(description="Файл не найден"),
            500: OpenApiResponse(description="Ошибка выполнения экспорта")
        },
        description="Асинхронный экспорт заказов в CSV (кладовщик)"
    )
    def get(self, request):
        # 1. Проверка прав доступа
        user = request.user
        if user.type != 'storekeeper':
            return Response({"error": "Доступ только для кладовщиков"}, status=status.HTTP_403_FORBIDDEN)

        # 2. Подготовка параметров фильтрации
        filters = {
            'status': request.query_params.getlist('status'),
            'date_from': request.query_params.get('date_from'),
            'date_to': request.query_params.get('date_to'),
            'shop': request.query_params.get('shop')
        }

        # 3. Запуск Celery-задачи и получение ID
        task = do_export_orders_task.delay(user.id, filters)

        # 4. Ожидание результата
        try:
            # timeout=60 — ждём до 60 секунд, иначе вернём ошибку
            file_path = task.get(timeout=60)
        except Exception as e:
            return Response({"error": f"Ошибка при выполнении экспорта: {e}"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # 5. Отдача файла пользователю
        if os.path.exists(file_path):
            return FileResponse(
                open(file_path, 'rb'),
                as_attachment=True,
                filename=os.path.basename(file_path),
                content_type='text/csv; charset=utf-8-sig'
            )
        else:
            return Response({"error": "Файл не найден"}, status=status.HTTP_404_NOT_FOUND)


class ExportProductsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='shop', description='ID магазина', required=False, type=int),
            OpenApiParameter(name='category', description='ID категории', required=False, type=int),
            OpenApiParameter(name='min_quantity', description='Минимальное количество на складе', required=False,
                             type=int),
        ],
        responses={
            200: OpenApiResponse(description="CSV-файл с товарами"),
            403: OpenApiResponse(description="Доступ запрещён (только для кладовщика, поставщика, администратора)"),
            404: OpenApiResponse(description="Файл не найден"),
            500: OpenApiResponse(description="Ошибка экспорта")
        },
        description="Асинхронный экспорт товаров в CSV с фильтрацией"
    )
    def get(self, request):
        user = request.user
        if user.type not in ['storekeeper', 'supplier', 'admin']:
            return Response({"error": "Доступ запрещён"}, status=status.HTTP_403_FORBIDDEN)

        filters = {
            'shop': request.query_params.get('shop'),
            'category': request.query_params.get('category'),
            'min_quantity': request.query_params.get('min_quantity')
        }

        # Запускаем асинхронную задачу
        task = do_export_products_task.delay(user.id, filters)

        # Ждём результат
        try:
            file_path = task.get(timeout=60)
        except Exception as e:
            return Response({"error": f"Ошибка экспорта: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Отдаём файл
        if os.path.exists(file_path):
            return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=os.path.basename(file_path))
        else:
            return Response({"error": "Файл не найден"}, status=status.HTTP_404_NOT_FOUND)


class FavoriteListView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = FavoriteSerializer

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Favorite.objects.none()
        return Favorite.objects.filter(user=self.request.user)

    @extend_schema(
        responses={200: FavoriteSerializer(many=True)},
        description="Список избранных товаров пользователя"
    )
    def get(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=FavoriteSerializer,
        responses={
            201: OpenApiResponse(description="Товар добавлен в избранное"),
            400: OpenApiResponse(description="Ошибка валидации")
        },
        description="Добавление товара в избранное"
    )
    def post(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class FavoriteDeleteView(DestroyAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Favorite.objects.all()
    serializer_class = FavoriteSerializer

    def get_queryset(self):
        return Favorite.objects.filter(user=self.request.user)

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID записи в избранном', required=True, type=int)
        ],
        responses={
            204: OpenApiResponse(description="Товар удалён из избранного"),
            404: OpenApiResponse(description="Запись не найдена")
        },
        description="Удаление товара из избранного"
    )
    def delete(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class MoveToCartView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID записи в избранном', required=True, type=int)
        ],
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'quantity': {'type': 'integer', 'description': 'Количество товара (по умолчанию 1)'}
                }
            }
        ),
        responses={
            200: OpenApiResponse(description="Товар добавлен в корзину"),
            400: OpenApiResponse(description="Ошибка валидации, недостаток товара или магазин не принимает заказы"),
            404: OpenApiResponse(description="Товар не найден в избранном")
        },
        description="Перемещение товара из избранного в корзину"
    )
    def post(self, request, pk):
        user = request.user

        try:
            favorite = Favorite.objects.get(id=pk, user=user)
        except Favorite.DoesNotExist:
            return Response({"error": "Товар не найден в избранном"}, status=status.HTTP_404_NOT_FOUND)

        # Проверка, принимает ли магазин заказы
        if not favorite.product_info.shop.state:
            return Response({"error": "Магазин не принимает заказы"}, status=status.HTTP_400_BAD_REQUEST)

        quantity = request.data.get('quantity', 1)
        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            return Response({"error": "Количество должно быть положительным числом"}, status=status.HTTP_400_BAD_REQUEST)

        # Проверка остатка
        if quantity > favorite.product_info.quantity:
            return Response({"error": "Недостаточно товара на складе"}, status=status.HTTP_400_BAD_REQUEST)

        cart, _ = Order.objects.get_or_create(user=user, state='basket')
        order_item, created = OrderItem.objects.get_or_create(
            order=cart,
            product_info=favorite.product_info,
            defaults={'quantity': quantity}
        )
        if not created:
            order_item.quantity += quantity
            order_item.save()

        return Response({"message": "Товар добавлен в корзину"}, status=status.HTTP_200_OK)


class ShopStateView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[
            OpenApiParameter(name='pk', description='ID магазина', required=True, type=int)
        ],
        request=OpenApiRequest(
            request={
                'type': 'object',
                'properties': {
                    'state': {
                        'type': 'string',
                        'enum': ['true', 'false'],
                        'description': 'Статус магазина ("true" - открыт, "false" - закрыт)'
                    }
                },
                'required': ['state']
            }
        ),
        responses={
            200: OpenApiResponse(description="Статус магазина обновлен"),
            400: OpenApiResponse(description="Ошибка валидации статуса"),
            403: OpenApiResponse(description="Доступ запрещен (не поставщик)"),
            404: OpenApiResponse(description="Магазин не найден")
        },
        description="Изменение статуса активности магазина (открыт/закрыт)"
    )
    def patch(self, request, pk):
        user = request.user
        if user.type != 'supplier':
            return Response({"error": "Доступ только для поставщиков"}, status=status.HTTP_403_FORBIDDEN)

        try:
            shop = Shop.objects.get(id=pk, user=user)
        except Shop.DoesNotExist:
            return Response({"error": "Магазин не найден или не принадлежит вам"}, status=status.HTTP_404_NOT_FOUND)

        state = request.data.get('state')
        if state is None:
            return Response({"error": "Укажите state"}, status=status.HTTP_400_BAD_REQUEST)

        # Преобразуем строку в булево значение
        if isinstance(state, str):
            if state.lower() == 'true':
                state = True
            elif state.lower() == 'false':
                state = False
            else:
                return Response({"error": "state должен быть true или false"}, status=status.HTTP_400_BAD_REQUEST)
        elif not isinstance(state, bool):
            return Response({"error": "state должен быть true или false"}, status=status.HTTP_400_BAD_REQUEST)

        shop.state = state
        shop.save()
        return Response({"message": f"Магазин {shop.name} {'открыт' if state else 'закрыт'}"}, status=status.HTTP_200_OK)