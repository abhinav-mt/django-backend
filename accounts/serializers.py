from django.contrib.auth import authenticate
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
    )
    password = serializers.CharField(
        required=False,
        allow_blank=True,
        write_only=True,
        style={'input_type': 'password'},
        trim_whitespace=False,
    )

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if not username or not password:
            raise serializers.ValidationError('Invalid credentials.')

        user = authenticate(
            request=self.context.get('request'),
            username=username,
            password=password,
        )

        if not user or not user.is_active:
            raise serializers.ValidationError('Invalid credentials.')

        attrs['user'] = user
        return attrs
