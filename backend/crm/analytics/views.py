from django.http import JsonResponse

from crm.core.http import endpoint
from crm.organizations.context import get_membership

from .period import parse_period
from .selectors import Report


@endpoint(["GET"], authenticated=True)
def report(request, organization_id):
    member = get_membership(request.user, organization_id)
    period = parse_period(request.GET)
    return JsonResponse(Report(member, period, request.GET).data())
