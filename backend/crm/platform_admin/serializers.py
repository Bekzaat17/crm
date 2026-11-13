from .selectors import owner_status


def company_data(organization):
    return {
        "id": str(organization.id),
        "name": organization.name,
        "created_at": organization.created_at.isoformat(),
        "members": getattr(organization, "members", None),
        "owner": owner_status(organization),
    }
