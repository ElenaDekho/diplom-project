from rest_framework import serializers
from users.models import User, EmailConfirmationToken
from django.contrib.auth import authenticate
from backend.models import ProductInfo, ProductParameter, Contact
import re
from django.core.mail import send_mail
from django.conf import settings
import uuid
from .tasks import send_email_task


class UserRegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=30, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=30, required=False, allow_blank=True)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=6)

    def validate_email(self, value):
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', value):
            raise serializers.ValidationError("Некорректный email")
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            password=validated_data['password']
        )
        token = str(uuid.uuid4())
        EmailConfirmationToken.objects.create(user=user, token=token)
        send_email_task.delay(
            subject='Подтверждение регистрации',
            message=f'Перейдите по ссылке: http://127.0.0.1:8000/api/confirm-email/{token}/',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return user

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError("Неверные учетные данные")
        return user

class ProductParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductParameter
        fields = ['parameter', 'value']

class ProductInfoSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    parameters = ProductParameterSerializer(source='productparameter_set', many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = ['id', 'product_name', 'shop_name', 'price', 'price_rrc', 'quantity', 'parameters']


class ContactSerializer(serializers.ModelSerializer):
    city = serializers.CharField(required=True, error_messages={'blank': 'Укажите город'})
    street = serializers.CharField(required=True, error_messages={'blank': 'Укажите улицу'})
    house = serializers.CharField(required=True, error_messages={'blank': 'Укажите номер дома'})
    phone = serializers.CharField(required=True, error_messages={'blank': 'Укажите телефон'})

    class Meta:
        model = Contact
        fields = '__all__'
        read_only_fields = ('id',)
        extra_kwargs = {
            'user': {'required': False},
        }

    def validate_phone(self, value):
        if not re.match(r'^\+?\d+$', value):
            raise serializers.ValidationError("Телефон должен содержать только цифры и может начинаться с +")
        return value