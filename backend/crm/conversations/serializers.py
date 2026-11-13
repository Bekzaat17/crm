def token_data(token, secret=None):
    data = {
        "id": str(token.id),
        "name": token.name,
        "user": token.user.name,
        "created_at": token.created_at.isoformat(),
        "expires_at": token.expires_at.isoformat(),
        "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
        "revoked": token.revoked_at is not None,
    }
    if secret:
        data["secret"] = secret  # показывается только при выдаче
    return data


def message_data(message):
    return {
        "id": str(message.id),
        "direction": message.direction,
        "author": message.author,
        "sent_at": message.sent_at.isoformat() if message.sent_at else None,
        "text": message.text,
        "has_attachment": message.has_attachment,
    }


def conversation_data(conversation, limit=200):
    # Порядок фрагментов и порядок сообщений на странице мессенджера.
    messages = conversation.messages.order_by("batch__created_at", "position")
    total = messages.count()
    return {
        "id": str(conversation.id),
        "source": conversation.source,
        "source_label": conversation.get_source_display(),
        "title": conversation.title,
        "message_count": total,
        "messages": [message_data(m) for m in messages[max(0, total - limit) :]],
        "imports": [
            {
                "created_at": b.created_at.isoformat(),
                "received": b.received,
                "created": b.created,
                "note": b.history_note,
                "by": b.imported_by.name,
            }
            for b in conversation.imports.select_related("imported_by").order_by(
                "-created_at"
            )[:10]
        ],
    }
