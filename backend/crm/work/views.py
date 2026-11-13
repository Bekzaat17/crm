from django.http import JsonResponse
from django.utils import timezone

from crm.core.http import endpoint
from crm.organizations.context import get_membership
from crm.sales.selectors import leads_for, page
from crm.sales.serializers import lead_data

from .selectors import filtered_tasks, open_leads, sales_summary
from .serializers import task_data
from .services import create_task, update_task


@endpoint(["GET"], authenticated=True)
def summary(request, organization_id):
    member = get_membership(request.user, organization_id)
    return JsonResponse(sales_summary(member))


@endpoint(["GET"], authenticated=True)
def tasks(request, organization_id):
    member = get_membership(request.user, organization_id)
    queryset = filtered_tasks(member, request.GET.get("status", "open")).select_related(
        "lead__client", "lead__assignee__user"
    )
    rows, total, more = page(queryset, request.GET.get("page", "1"))
    return JsonResponse(
        {"items": [task_data(task) for task in rows], "total": total, "has_more": more}
    )


@endpoint(["POST"], authenticated=True)
def add_task(request, organization_id, lead_id):
    task = create_task(request.user, organization_id, lead_id, request.payload)
    return JsonResponse(task_data(task), status=201)


@endpoint(["POST"], authenticated=True)
def edit_task(request, organization_id, task_id):
    task = update_task(request.user, organization_id, task_id, request.payload)
    return JsonResponse(task_data(task))


@endpoint(["GET"], authenticated=True)
def contacts_due(request, organization_id):
    member = get_membership(request.user, organization_id)
    queryset = (
        open_leads(leads_for(member))
        .filter(next_contact_at__lte=timezone.now())
        .select_related("client", "assignee__user", "stage")
        .order_by("next_contact_at", "id")
    )
    rows, total, more = page(queryset, request.GET.get("page", "1"))
    return JsonResponse(
        {"items": [lead_data(lead) for lead in rows], "total": total, "has_more": more}
    )
