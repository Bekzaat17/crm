from crm.organizations.selectors import active_memberships
from crm.organizations.serializers import company_data


def user_data(user):
    return {"id": str(user.id), "email": user.email, "name": user.name}


def session_data(user):
    if not user.is_authenticated:
        return {"user": None, "organizations": []}
    return {
        "user": user_data(user),
        "organizations": [company_data(m) for m in active_memberships(user)],
    }
