from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import UserRegisterSerializer, ContactSerializer
from rest_framework.authtoken.models import Token
from .serializers import UserLoginSerializer
from rest_framework.generics import ListAPIView
from .serializers import ProductInfoSerializer
from backend.models import Order, OrderItem, ProductInfo, Contact, PasswordResetToken
from django.core.mail import send_mail
from django.conf import settings
import uuid
from users.models import User, EmailConfirmationToken
from import_data import import_from_yaml
from backend.models import Shop, STATE_CHOICES
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.generics import RetrieveAPIView
import csv
from django.http import HttpResponse


class RegisterView(APIView):
    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Пользователь создан"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data
            token, _ = Token.objects.get_or_create(user=user)
            return Response({"token": token.key}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductListView(ListAPIView):
    queryset = ProductInfo.objects.all()
    serializer_class = ProductInfoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['shop', 'product__category']
    search_fields = ['product__name', 'name']


class CartView(APIView):
    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

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

    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

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

    def delete(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

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

    def put(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

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
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

        if Contact.objects.filter(user=user).count() >= 5:
            return Response({"error": "Нельзя добавить более 5 контактов"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ContactSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

        contacts = Contact.objects.filter(user=user)
        serializer = ContactSerializer(contacts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ContactDetailView(APIView):
    def delete(self, request, pk):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            contact = Contact.objects.get(id=pk, user=user)
            contact.delete()
            return Response({"message": "Контакт удален"}, status=status.HTTP_200_OK)
        except Contact.DoesNotExist:
            return Response({"error": "Контакт не найден"}, status=status.HTTP_404_NOT_FOUND)


class OrderCreateView(APIView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

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

        cart.state = 'new'
        cart.contact = contact
        cart.save()

        # Подсчёт суммы
        total = sum(item.quantity * item.product_info.price for item in cart.items.all())

        # Письмо клиенту
        send_mail(
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
            send_mail(
                subject='Новый заказ',
                message=f'Поступил заказ №{cart.id}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=True,
            )

        return Response({"message": "Заказ оформлен", "order_id": cart.id}, status=status.HTTP_200_OK)


class OrderListView(APIView):
    def get(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

        orders = Order.objects.filter(user=user).exclude(state='basket')
        result = []
        for order in orders:
            result.append({
                "id": order.id,
                "dt": order.dt,
                "state": order.state,
                "contact": f"{order.contact.city}, {order.contact.street} {order.contact.house}",
                "total": sum(item.quantity * item.product_info.price for item in order.items.all())
            })
        return Response(result, status=status.HTTP_200_OK)


class OrderDetailView(APIView):
    def get(self, request, pk):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

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
            "contact": f"{order.contact.city}, {order.contact.street} {order.contact.house}",
            "items": items,
            "total": sum(item['total'] for item in items)
        }
        return Response(result, status=status.HTTP_200_OK)


class LogoutView(APIView):
    def post(self, request):
        if not request.user.is_authenticated:
            return Response({"error": "Вы не авторизованы"}, status=status.HTTP_401_UNAUTHORIZED)
        request.auth.delete()
        return Response({"message": "Вы вышли из системы"}, status=status.HTTP_200_OK)


class ProductShopsView(APIView):
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
            import_from_yaml(shop.yaml_file)
            return Response({"message": f"Импорт для магазина {shop.name} выполнен"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SupplierOrdersView(APIView):
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
    queryset = ProductInfo.objects.all()
    serializer_class = ProductInfoSerializer


class OrderStatusUpdateView(APIView):
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
            send_mail(
                subject='Статус заказа изменён',
                message=f'Ваш заказ №{order.id} теперь в статусе {order.state}.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[order.user.email],
                fail_silently=True,
            )

        order.save()
        return Response({"message": "Статус обновлён"}, status=status.HTTP_200_OK)


class CancelOrderView(APIView):
    def post(self, request, pk):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Необходимо авторизоваться"}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            order = Order.objects.get(id=pk, user=user)
        except Order.DoesNotExist:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        if order.state == 'canceled':
            return Response({"error": "Заказ уже отменён"}, status=status.HTTP_400_BAD_REQUEST)

        order.state = 'canceled'
        order.save()
        send_mail(
            subject='Заказ отменён',
            message=f'Ваш заказ №{order.id} был отменён.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=True,
        )
        return Response({"message": "Заказ отменён"}, status=status.HTTP_200_OK)


class ConfirmEmailView(APIView):
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
    def patch(self, request, pk):
        user = request.user
        if user.type != 'storekeeper':
            return Response({"error": "Доступ только для кладовщиков"}, status=status.HTTP_403_FORBIDDEN)

        try:
            order = Order.objects.get(id=pk)
        except Order.DoesNotExist:
            return Response({"error": "Заказ не найден"}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('state')
        allowed_statuses = ['assembled', 'sent', 'delivered']
        if new_status not in allowed_statuses:
            return Response({"error": f"Недопустимый статус. Разрешены: {', '.join(allowed_statuses)}"},
                            status=status.HTTP_400_BAD_REQUEST)

        order.state = new_status
        order.save()

        # Отправка уведомления клиенту
        state_display = dict(STATE_CHOICES)[order.state]
        send_mail(
            subject='Статус заказа изменён',
            message=f'Ваш заказ №{order.id} теперь в статусе {state_display}.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[order.user.email],
            fail_silently=True,
        )

        return Response({"message": f"Статус заказа изменён на {new_status}"}, status=status.HTTP_200_OK)


class StorekeeperExportOrdersView(APIView):
    def get(self, request):
        user = request.user
        if user.type != 'storekeeper':
            return Response({"error": "Доступ только для кладовщиков"}, status=status.HTTP_403_FORBIDDEN)

        # Фильтрация
        statuses = request.query_params.getlist('status')
        if not statuses:
            statuses = ['confirmed', 'assembled', 'sent']

        orders = Order.objects.filter(state__in=statuses)

        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            orders = orders.filter(dt__date__gte=date_from)
        if date_to:
            orders = orders.filter(dt__date__lte=date_to)

        shop_id = request.query_params.get('shop')
        if shop_id:
            orders = orders.filter(items__product_info__shop_id=shop_id).distinct()

        orders = orders.order_by('-dt')

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'

        writer = csv.writer(response)
        writer.writerow(['ID заказа', 'Дата', 'Статус', 'Клиент', 'Телефон', 'Адрес', 'Сумма', 'Товары'])

        for order in orders:
            contact = order.contact
            items_list = []
            for item in order.items.all():
                items_list.append(
                    f"{item.product_info.product.name} ({item.product_info.shop.name}) x{item.quantity} = "
                    f"{item.quantity * item.product_info.price}р"
                )
            items_str = '; '.join(items_list)

            writer.writerow([
                order.id,
                order.dt.strftime('%Y-%m-%d %H:%M'),
                dict(STATE_CHOICES)[order.state],
                order.user.email,
                contact.phone if contact else 'Не указан',
                f"{contact.city}, {contact.street} {contact.house}" if contact else 'Не указан',
                sum(item.quantity * item.product_info.price for item in order.items.all()),
                items_str
            ])

        return response