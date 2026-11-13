from crm.core.mail import LinkEmail


def invitation_email(invitation, token):
    name = invitation.organization.name
    return LinkEmail(
        to=invitation.email,
        subject=f"Приглашение в {name}",
        message=(
            f"Вас приглашают в компанию «{name}» в RehubPro CRM. "
            "Ссылка действует 7 дней."
        ),
        page="invite",
        params={"token": token},
    )
