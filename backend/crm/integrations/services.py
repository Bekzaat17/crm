import uuid

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from crm.core.errors import ApiError
from crm.core.validation import clean_text, identifier
from crm.organizations import audit
from crm.organizations.context import get_membership
from crm.organizations.permissions import Perm
from crm.sales.models import LeadActivity
from crm.sales.selectors import find_lead
from crm.sales.services import require_version

from .address import normalize_domain
from .models import AdmissionTransfer, RehubCenter
from .secrets import decrypt, encrypt
from .selectors import find_center
from .transport import HTTPSClient, Transport


@transaction.atomic
def create_center(actor, company_id, data):
    get_membership(actor, company_id, Perm.MANAGE_CENTERS)
    center = RehubCenter.objects.create(
        organization_id=company_id,
        name=clean_text(data.get("name"), "Название центра", 160),
        domain=normalize_domain(data.get("address")),
    )
    audit.record(company_id, actor, "center.created", center.id)
    return center


@transaction.atomic
def update_center(actor, company_id, center_id, data):
    get_membership(actor, company_id, Perm.MANAGE_CENTERS)
    center = find_center(company_id, center_id, lock=True)
    require_version(center, data, "Центр изменился. Обновите список.")
    if "address" in data and normalize_domain(data["address"]) != center.domain:
        if center.admissiontransfer_set.exists():
            raise ApiError(
                "У центра уже есть передачи. Для другого домена создайте новый центр.",
                409,
            )
        center.domain = normalize_domain(data["address"])
        center.encrypted_key = ""
        center.verified_at = None
    if "name" in data:
        center.name = clean_text(data["name"], "Название центра", 160)
    if "key" in data:
        key = clean_text(data["key"], "Ключ подключения", 256)
        if any(c.isspace() for c in key):
            raise ApiError("Ключ не должен содержать пробелы.")
        center.encrypted_key = encrypt(key)
        center.verified_at = None
    if "is_active" in data:
        if not isinstance(data["is_active"], bool):
            raise ApiError("Некорректное состояние центра.")
        center.is_active = data["is_active"]
    center.version += 1
    center.save()
    audit.record(company_id, actor, "center.updated", center.id)
    return center


def verify_center(actor, company_id, center_id, transport: Transport | None = None):
    get_membership(actor, company_id, Perm.MANAGE_CENTERS)
    center = find_center(company_id, center_id)
    if not center.is_active or not center.encrypted_key:
        raise ApiError("Сначала сохраните ключ активного центра.")
    try:
        reply = (transport or HTTPSClient()).request(
            center.domain, decrypt(center.encrypted_key), "/crm/health"
        )
    except (OSError, ValueError):
        raise ApiError("Не удалось установить безопасное соединение с центром.", 502)
    if (
        reply.status != 200
        or reply.data.get("schema_version") != 1
        or reply.data.get("company_id") != str(company_id)
        or reply.data.get("connection_id") != str(center.id)
    ):
        raise ApiError(
            "Центр не подтвердил подключение. Проверьте ключ, API и сетевой доступ.",
            400,
        )
    updated = RehubCenter.objects.filter(
        pk=center.id, version=center.version, is_active=True
    ).update(verified_at=timezone.now())
    if not updated:
        raise ApiError(
            "Подключение изменилось во время проверки. Повторите проверку.", 409
        )
    center.refresh_from_db()
    return center


def admission_payload(lead, operation_id, data):
    birthday = lead.client.date_of_birth
    try:
        admission = parse_date(data.get("date_of_admission", ""))
    except (ValueError, TypeError):
        admission = None
    if not admission or admission > timezone.localdate():
        raise ApiError(
            "Подтвердите фактическую дату поступления, не позднее сегодняшней."
        )
    if data.get("confirmed") is not True:
        raise ApiError("Необходимо подтвердить данные и передачу клиента.")
    person = {
        field: clean_text(data.get(field), label, 100)
        for field, label in [("last_name", "Фамилия"), ("first_name", "Имя")]
    }
    middle = data.get("middle_name", "")
    if not isinstance(middle, str) or len(middle) > 100:
        raise ApiError("Некорректное отчество.")
    person.update(
        {
            "middle_name": middle.strip(),
            "date_of_birth": birthday.isoformat() if birthday else None,
        }
    )
    return {
        "schema_version": 1,
        "external_admission_id": str(operation_id),
        "external_client_id": str(lead.client_id),
        "person": person,
        "admission": {"date_of_admission": admission.isoformat()},
        "contact": {"phone": lead.client.phone, "city": lead.client.city},
        "relatives": [
            {"name": c.name, "relationship": c.relationship, "phone": c.phone}
            for c in lead.client.contacts.order_by("id")[:20]
        ],
    }


@transaction.atomic
def queue_admission(actor, company_id, lead_id, data):
    member = get_membership(actor, company_id, Perm.SEND_ADMISSIONS)
    lead = find_lead(member, lead_id, lock=True)
    center = find_center(company_id, identifier(data.get("center_id")), lock=True)
    if not center.is_active or not center.verified_at:
        raise ApiError("Выберите проверенный активный центр.")
    if lead.version != data.get("version"):
        raise ApiError("Обращение изменилось. Откройте его заново.", 409)
    if data.get("client_version") != lead.client.version:
        raise ApiError(
            "Карточка клиента изменилась. Обновите предпросмотр передачи.", 409
        )
    operation_id = uuid.uuid4()
    payload = admission_payload(lead, operation_id, data)
    existing = AdmissionTransfer.objects.filter(lead=lead, center=center).first()
    if existing:
        if {
            k: v for k, v in existing.payload.items() if k != "external_admission_id"
        } != {k: v for k, v in payload.items() if k != "external_admission_id"}:
            raise ApiError(
                "Для этого обращения уже зафиксирована другая передача. Проверьте её историю.",
                409,
            )
        return existing, False
    transfer = AdmissionTransfer.objects.create(
        id=operation_id, lead=lead, center=center, payload=payload, confirmed_by=actor
    )
    LeadActivity.objects.create(
        lead=lead,
        actor=actor,
        kind="transfer",
        text=f"Подтверждена передача в центр «{center.name}»",
    )
    return transfer, True


@transaction.atomic
def retry_admission(actor, company_id, transfer_id):
    get_membership(actor, company_id, Perm.SEND_ADMISSIONS)
    transfer = (
        AdmissionTransfer.objects.select_for_update()
        .filter(pk=transfer_id, lead__organization_id=company_id)
        .first()
    )
    if not transfer:
        raise ApiError("Передача не найдена.", 404)
    if transfer.status in ("delivered", "sending", "pending", "retry"):
        raise ApiError("Передача уже доставлена или находится в очереди.", 409)
    if not transfer.center.is_active or not transfer.center.verified_at:
        raise ApiError("Сначала восстановите проверенное подключение.")
    transfer.status = "pending"
    transfer.cycle_attempts = 0
    transfer.next_attempt_at = timezone.now()
    transfer.lease_until = None
    transfer.lease_id = None
    transfer.save()
    audit.record(company_id, actor, "transfer.retried", transfer.id)
    return transfer
