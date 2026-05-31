from rest_framework import serializers
from users.models import User
from django.contrib.auth import authenticate
from backend.models import ProductInfo, ProductParameter, Contact
import re


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
    class Meta:
        model = Contact
        fields = '__all__'
        read_only_fields = ('id',)
        extra_kwargs = {'user': {'required': False}}

    def validate_phone(self, value):
        if not re.match(r'^\+?\d+$', value):
            raise serializers.ValidationError("Телефон должен содержать только цифры и может начинаться с +")
        return value

    def validate_city(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Город не может быть пустым")
        return value

    def validate_street(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Улица не может быть пустой")
        return value

    def validate_house(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Дом не может быть пустым")
        return value