from django.db import models
from users.models import User  # Импортируем нашу кастомную модель
from django.utils import timezone

# Статусы заказа
STATE_CHOICES = (
    ('basket', 'Корзина'),
    ('new', 'Новый заказ'),
    ('confirmed', 'Подтвержден'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)


class Shop(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название магазина')
    url = models.URLField(verbose_name='Ссылка на магазин', null=True, blank=True)
    # Связь с пользователем-владельцем магазина (поставщиком)
    user = models.ForeignKey(User, verbose_name='Владелец',
                             on_delete=models.CASCADE,
                             related_name='shops',
                             limit_choices_to={'type': 'supplier'})
    state = models.BooleanField(verbose_name='Принимает заказы', default=True)
    yaml_file = models.CharField(max_length=255, verbose_name="Путь к файлу импорта", blank=True, null=True)

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = "Список магазинов"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название категории')
    shops = models.ManyToManyField(Shop, verbose_name='Магазины', related_name='categories', blank=True)

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = "Список категорий"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название товара')
    category = models.ForeignKey(Category, verbose_name='Категория', related_name='products', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = "Список товаров"
        ordering = ('-name',)

    def __str__(self):
        return self.name


class ProductInfo(models.Model):
    product = models.ForeignKey(Product, verbose_name='Товар', related_name='product_infos', on_delete=models.CASCADE)
    shop = models.ForeignKey(Shop, verbose_name='Магазин', related_name='product_infos', on_delete=models.CASCADE)

    name = models.CharField(max_length=100, verbose_name='Название позиции',
                            blank=True)  # Может отличаться от общего названия
    model = models.CharField(max_length=100, verbose_name='Модель/Артикул', blank=True)
    external_id = models.PositiveIntegerField(verbose_name='Внешний ID', null=True, blank=True)
    quantity = models.PositiveIntegerField(default=0, verbose_name="Количество на складе")
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Рекомендуемая цена', null=True, blank=True)

    class Meta:
        verbose_name = 'Информация о товаре'
        verbose_name_plural = "Информация о товарах"
        constraints = [
            models.UniqueConstraint(fields=['product', 'shop'], name='unique_product_shop'),
        ]

    def __str__(self):
        return f'{self.product.name} - {self.shop.name}'


class Parameter(models.Model):
    name = models.CharField(max_length=50, verbose_name='Название параметра')

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = "Список параметров"

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    product_info = models.ForeignKey(ProductInfo, verbose_name='Товар', related_name='parameters',
                                     on_delete=models.CASCADE)
    parameter = models.ForeignKey(Parameter, verbose_name='Имя параметра', related_name='values',
                                  on_delete=models.CASCADE)
    value = models.CharField(verbose_name='Значение', max_length=100)

    class Meta:
        verbose_name = 'Характеристика товара'
        verbose_name_plural = "Характеристики товаров"
        constraints = [
            models.UniqueConstraint(fields=['product_info', 'parameter'], name='unique_product_parameter'),
        ]

    def __str__(self):
        return f'{self.parameter.name}: {self.value}'


class Contact(models.Model):
    user = models.ForeignKey(User, verbose_name='Пользователь', related_name='contacts', on_delete=models.CASCADE)

    city = models.CharField(max_length=50, verbose_name='Город')
    street = models.CharField(max_length=100, verbose_name='Улица')
    house = models.CharField(max_length=15, verbose_name='Дом', blank=True)
    structure = models.CharField(max_length=15, verbose_name='Строение', blank=True)
    building = models.CharField(max_length=15, verbose_name='Корпус', blank=True)
    apartment = models.CharField(max_length=15, verbose_name='Квартира', blank=True)
    phone = models.CharField(max_length=20, verbose_name='Телефон')

    class Meta:
        verbose_name = 'Контактные данные'
        verbose_name_plural = "Список контактов"

    def __str__(self):
        return f'{self.city}, {self.street} {self.house}'


class Order(models.Model):
    user = models.ForeignKey(User, verbose_name='Покупатель', related_name='orders', on_delete=models.CASCADE)
    dt = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    state = models.CharField(verbose_name='Статус', choices=STATE_CHOICES, max_length=15, default='basket')
    contact = models.ForeignKey(Contact, verbose_name='Контакт доставки', null=True, blank=True,
                                on_delete=models.SET_NULL)
    confirmed_shops = models.TextField(default='', blank=True, verbose_name='ID подтверждённых магазинов')

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = "Список заказов"
        ordering = ('-dt',)

    def __str__(self):
        return f'Заказ №{self.id} от {self.dt.strftime("%Y-%m-%d")}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, verbose_name='Заказ', related_name='items', on_delete=models.CASCADE)
    product_info = models.ForeignKey(ProductInfo, verbose_name='Товар', related_name='order_items',
                                     on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(verbose_name='Количество')

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = "Позиции заказов"

    def __str__(self):
        return f'{self.product_info.product.name} x {self.quantity}'


class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return (timezone.now() - self.created_at).seconds < 3600  # 1 час


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    product_info = models.ForeignKey(ProductInfo, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product_info')
        verbose_name = 'Избранное'
        verbose_name_plural = 'Избранное'
