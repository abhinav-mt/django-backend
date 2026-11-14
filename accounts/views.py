from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import UserToken
from .serializers import LoginSerializer


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(
                {'detail': 'Invalid credentials.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data['user']
        token = UserToken.objects.create(user=user)

        return Response(
            {
                'token': token.key,
                'role': user.role,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if isinstance(request.auth, UserToken):
            request.auth.delete()
        elif hasattr(request.auth, 'delete'):
            request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
