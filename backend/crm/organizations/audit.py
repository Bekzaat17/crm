from .models import AuditEvent

LABELS = {
    "organization.created": "Создана компания",
    "invitation.created": "Отправлено приглашение",
    "invitation.accepted": "Сотрудник принял приглашение",
    "invitation.revoked": "Приглашение отозвано",
    "membership.deactivated": "Отключён доступ сотрудника",
    "membership.role_changed": "Изменена роль сотрудника",
    "ownership.transferred": "Передано владение компанией",
    "branch.created": "Добавлен филиал",
    "branch.updated": "Переименован филиал",
    "branch.archived": "Филиал архивирован",
    "branch.restored": "Филиал восстановлен",
    "contact.updated": "Изменено контактное лицо",
    "contact.deleted": "Удалено контактное лицо",
    "stage.created": "Добавлен этап воронки",
    "stage.updated": "Изменён этап воронки",
    "stage.reordered": "Изменён порядок этапов",
    "stage.archived": "Этап воронки архивирован",
    "stage.restored": "Этап воронки восстановлен",
    "client.created": "Создана карточка клиента",
    "client.updated": "Изменена карточка клиента",
    "extension_token.created": "Выдан ключ расширения браузера",
    "extension_token.revoked": "Отозван ключ расширения браузера",
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
