def client_data(c, detail=False):
    data = dict(
        id=str(c.id),
        name=c.name,
        phone=c.phone,
        city=c.city,
        date_of_birth=c.date_of_birth.isoformat() if c.date_of_birth else "",
        notes=c.notes,
        version=c.version,
    )
    if detail:
        data["contacts"] = [
            dict(
                id=str(r.id),
                name=r.name,
                phone=r.phone,
                relationship=r.relationship,
                version=r.version,
            )
            for r in c.contacts.order_by("name")
        ]
    return data


def lead_data(lead):
    return dict(
        id=str(lead.id),
        title=lead.title,
        client_id=str(lead.client_id),
        client_name=lead.client.name,
        phone=lead.client.phone,
        assignee_id=str(lead.assignee_id),
        assignee_name=lead.assignee.user.name,
        branch_id=str(lead.branch_id),
        source=lead.source,
        stage=str(lead.stage_id),
        stage_label=lead.stage.name,
        stage_kind=lead.stage.kind,
        refusal_reason=lead.refusal_reason,
        next_contact_at=lead.next_contact_at.isoformat()
        if lead.next_contact_at
        else "",
        version=lead.version,
        updated_at=lead.updated_at.isoformat(),
    )


def stage_data(stage):
    data = dict(
        id=str(stage.id),
        name=stage.name,
        kind=stage.kind,
        kind_label=stage.get_kind_display(),
        color=stage.color,
        position=stage.position,
        is_active=stage.is_active,
        version=stage.version,
    )
    if hasattr(stage, "lead_count"):
        data["lead_count"] = stage.lead_count
    return data
