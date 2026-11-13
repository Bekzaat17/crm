from crm.core.mail import LinkEmail


def registration_email(email, token):
    return LinkEmail(
        to=email,
        subject="Подтвердите регистрацию RehubPro CRM",
        message="Подтвердите почту, чтобы создать компанию. Ссылка действует 24 часа.",
        page="verify",
        params={"token": token},
    )


def password_reset_email(user, token):
    return LinkEmail(
        to=user.email,
        subject="Восстановление доступа RehubPro CRM",
        message="Задайте новый пароль. Ссылка действует один час.",
        page="reset",
        params={"uid": str(user.id), "token": token},
    )
