def center_data(center, admin=False):
    result = {
        "id": str(center.id),
        "name": center.name,
        "domain": center.domain,
        "endpoint": f"https://{center.domain}/crm/create",
        "verified": bool(center.verified_at),
        "is_active": center.is_active,
        "version": center.version,
    }
    if admin:
        result.update(
            {
                "company_id": str(center.organization_id),
                "has_key": bool(center.encrypted_key),
            }
        )
    return result


def transfer_data(transfer):
    return {
        "id": str(transfer.id),
        "center_name": transfer.center.name,
        "domain": transfer.center.domain,
        "status": transfer.status,
        "status_label": transfer.get_status_display(),
        "attempt_count": transfer.attempt_count,
        "last_error": transfer.last_error,
        "resident_id": transfer.resident_id,
        "next_attempt_at": transfer.next_attempt_at.isoformat()
        if transfer.status in ("pending", "retry")
        else None,
        "created_at": transfer.created_at.isoformat(),
        "attempts": [
            {
                "number": attempt.number,
                "outcome": attempt.outcome,
                "http_status": attempt.http_status,
                "started_at": attempt.started_at.isoformat(),
            }
            for attempt in transfer.attempts.order_by("-number")[:30]
        ],
    }
