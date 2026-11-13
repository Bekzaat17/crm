from crm.core.mail import LinkEmail


def password_reset_email(user, token):
    return LinkEmail(
        to=user.email,
        subject="Восстановление доступа RehubPro CRM",
        message="Задайте новый пароль. Ссылка действует один час.",
        page="reset",
        params={"uid": str(user.id), "token": token},
        key=f"password-reset:{user.id}",
    )
