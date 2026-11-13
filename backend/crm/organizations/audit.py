from .models import AuditEvent

LABELS = {
    "organization.created": "Создана компания",
    "invitation.created": "Отправлено приглашение",
    "invitation.accepted": "Сотрудник принял приглашение",
    "invitation.revoked": "Приглашение отозвано",
    "membership.deactivated": "Отключён доступ сотрудника",
    "center.created": "Добавлен центр",
    "center.updated": "Изменён центр",
    "transfer.retried": "Повторена передача",
}


def record(organization_id, actor, action, target=""):
    return AuditEvent.objects.create(
        organization_id=organization_id,
        actor=actor,
        action=action,
        target_id=str(target),
    )


def label(action):
    return LABELS.get(action, action)
