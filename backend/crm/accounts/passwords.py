from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from crm.core.errors import ApiError

from .models import User


def check_password(value, email, name):
    if not isinstance(value, str) or len(value) > 128:
        raise ApiError("Пароль должен содержать от 10 до 128 символов.")
    try:
        validate_password(value, User(email=email, name=name, first_name=name))
    except ValidationError as exc:
        raise ApiError(" ".join(exc.messages))
    return value
