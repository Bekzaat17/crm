from django.db.models import Count, Q
from django.http import JsonResponse

from crm.core.http import endpoint
from crm.organizations.context import get_membership
from crm.organizations.models import Branch, Membership
from crm.organizations.permissions import Perm, can

from . import pipeline, services
from .selectors import clients_for, find_client, find_lead, leads_for, page
from .serializers import client_data, lead_data, stage_data


@endpoint(["GET"], authenticated=True)
def metadata(request, organization_id):
    m = get_membership(request.user, organization_id)
    staff = Membership.objects.filter(
        organization_id=organization_id, is_active=True
    ).select_related("user")
    if not can(m, Perm.ASSIGN_LEADS):
        staff = staff.filter(pk=m.pk)
    return JsonResponse(
        {
            "stages": [stage_data(s) for s in pipeline.active_stages(organization_id)],
            "assignees": [
                dict(id=str(x.id), name=x.user.name)
                for x in staff.order_by("user__name")
            ],
            "branches": [
                dict(id=str(b.id), name=b.name)
                for b in Branch.objects.filter(
                    organization_id=organization_id, is_active=True
                ).order_by("name")
            ],
            "can_assign": can(m, Perm.ASSIGN_LEADS),
            "can_send": can(m, Perm.SEND_ADMISSIONS),
            "can_manage_pipeline": can(m, Perm.MANAGE_PIPELINE),
        }
    )


@endpoint(["GET", "POST"], authenticated=True)
def clients(request, organization_id):
    m = get_membership(request.user, organization_id)
    if request.method == "POST":
        return JsonResponse(
            client_data(
                services.create_client(request.user, organization_id, request.payload),
                True,
            ),
            status=201,
        )
    qs = clients_for(m)
    q = request.GET.get("q", "").strip()[:160]
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(phone__icontains=q)
            | Q(contacts__phone__icontains=q)
            | Q(contacts__name__icontains=q)
        ).distinct()
    rows, total, more = page(
        qs.order_by("-created_at", "id"), request.GET.get("page", "1")
    )
    return JsonResponse(
        {"items": [client_data(c) for c in rows], "total": total, "has_more": more}
    )


@endpoint(["GET", "POST"], authenticated=True)
def client_detail(request, organization_id, client_id):
    m = get_membership(request.user, organization_id)
    client = (
        services.update_client(
            request.user, organization_id, client_id, request.payload
        )
        if request.method == "POST"
        else find_client(m, client_id)
    )
    result = client_data(client, True)
    result["leads"] = [
        lead_data(x)
        for x in leads_for(m)
        .filter(client=client)
        .select_related("client", "assignee__user", "stage")
        .order_by("-created_at")
    ]
    return JsonResponse(result)


@endpoint(["POST"], authenticated=True)
def add_contact(request, organization_id, client_id):
    obj = services.create_contact(
        request.user, organization_id, client_id, request.payload
    )
    return JsonResponse({"id": str(obj.id)}, status=201)


@endpoint(["GET", "POST"], authenticated=True)
def leads(request, organization_id):
    m = get_membership(request.user, organization_id)
    if request.method == "POST":
        return JsonResponse(
            lead_data(
                services.create_lead(request.user, organization_id, request.payload)
            ),
            status=201,
        )
    qs = leads_for(m)
    q = request.GET.get("q", "").strip()[:160]
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(client__name__icontains=q)
            | Q(client__phone__icontains=q)
        )
    stage = request.GET.get("stage", "")
    if stage:
        qs = qs.filter(stage=pipeline.find_stage(organization_id, stage, active=False))
    counts = {
        str(x["stage"]): x["n"] for x in qs.values("stage").annotate(n=Count("id"))
    }
    rows, total, more = page(
        qs.select_related("client", "assignee__user", "stage").order_by(
            "-updated_at", "id"
        ),
        request.GET.get("page", "1"),
    )
    return JsonResponse(
        {
            "items": [lead_data(x) for x in rows],
            "total": total,
            "has_more": more,
            "counts": counts,
        }
    )


@endpoint(["GET", "POST"], authenticated=True)
def lead_detail(request, organization_id, lead_id):
    m = get_membership(request.user, organization_id)
    lead = (
        services.update_lead(request.user, organization_id, lead_id, request.payload)
        if request.method == "POST"
        else find_lead(m, lead_id)
    )
    result = lead_data(lead)
    result["activities"] = [
        dict(
            id=str(a.id),
            text=a.text,
            kind=a.kind,
            actor=a.actor.name,
            created_at=a.created_at.isoformat(),
        )
        for a in lead.activities.select_related("actor").order_by("-created_at", "id")[
            :100
        ]
    ]
    return JsonResponse(result)


@endpoint(["POST"], authenticated=True)
def comment(request, organization_id, lead_id):
    services.add_comment(request.user, organization_id, lead_id, request.payload)
    return JsonResponse({"message": "Комментарий добавлен."}, status=201)


@endpoint(["GET", "POST"], authenticated=True)
def stages(request, organization_id):
    get_membership(request.user, organization_id, Perm.MANAGE_PIPELINE)
    if request.method == "POST":
        stage = pipeline.create_stage(request.user, organization_id, request.payload)
        return JsonResponse(stage_data(stage), status=201)
    return JsonResponse(
        {"items": [stage_data(s) for s in pipeline.all_stages(organization_id)]}
    )


@endpoint(["POST"], authenticated=True)
def edit_stage(request, organization_id, stage_id):
    stage = pipeline.update_stage(
        request.user, organization_id, stage_id, request.payload
    )
    return JsonResponse(stage_data(stage))


@endpoint(["POST"], authenticated=True)
def reorder_stages(request, organization_id):
    items = pipeline.reorder_stages(request.user, organization_id, request.payload)
    return JsonResponse({"items": [stage_data(s) for s in items]})


@endpoint(["POST"], authenticated=True)
def archive_stage(request, organization_id, stage_id):
    stage, moved = pipeline.archive_stage(
        request.user, organization_id, stage_id, request.payload
    )
    return JsonResponse({**stage_data(stage), "moved_leads": moved})


@endpoint(["POST"], authenticated=True)
def restore_stage(request, organization_id, stage_id):
    return JsonResponse(
        stage_data(pipeline.restore_stage(request.user, organization_id, stage_id))
    )


@endpoint(["POST"], authenticated=True)
def edit_contact(request, organization_id, client_id, contact_id):
    contact = services.update_contact(
        request.user, organization_id, client_id, contact_id, request.payload
    )
    return JsonResponse({"id": str(contact.id), "version": contact.version})


@endpoint(["POST"], authenticated=True)
def delete_contact(request, organization_id, client_id, contact_id):
    services.delete_contact(request.user, organization_id, client_id, contact_id)
    return JsonResponse({"message": "Контактное лицо удалено."})
