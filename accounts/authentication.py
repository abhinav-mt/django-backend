from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import UserToken


class TokenAuthentication(BaseAuthentication):
    keyword = 'Token'

    def authenticate(self, request):
        auth = get_authorization_header(request).split()

        if not auth or auth[0].lower() != self.keyword.lower().encode():
            return None

        if len(auth) == 1:
            raise AuthenticationFailed('Invalid token header. No credentials provided.')
        elif len(auth) > 2:
            raise AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        try:
            token_key = auth[1].decode()
        except UnicodeError:
            raise AuthenticationFailed('Invalid token header. Token string should not contain invalid characters.')

        return self.authenticate_credentials(token_key)

    def authenticate_credentials(self, key):
        try:
            token = UserToken.objects.select_related('user').get(key=key)
        except UserToken.DoesNotExist:
            raise AuthenticationFailed('Invalid token.')

        if not token.user.is_active:
            raise AuthenticationFailed('User inactive or deleted.')

        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword
