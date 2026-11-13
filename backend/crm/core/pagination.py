from .errors import ApiError

PAGE_SIZE = 50


def page(queryset, value, size=PAGE_SIZE):
    """Страница выборки: (строки, всего, есть ли ещё)."""
    try:
        number = int(value)
        if number < 1 or number > 100000:
            raise ValueError
    except (ValueError, TypeError):
        raise ApiError("Некорректный номер страницы.")
    total = queryset.count()
    start = (number - 1) * size
    return list(queryset[start : start + size]), total, number * size < total
