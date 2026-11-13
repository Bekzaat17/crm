from crm.sales.selectors import find_lead, leads_for

from .models import Conversation


def lead_conversations(member, lead_id):
    lead = find_lead(member, lead_id)
    return Conversation.objects.filter(lead=lead).order_by("-updated_at")


def lead_search(member, query, limit=20):
    leads = leads_for(member).select_related("client", "stage")
    if query:
        leads = leads.filter(title__icontains=query) | leads.filter(
            client__name__icontains=query
        )
    return leads.order_by("-updated_at")[:limit]
