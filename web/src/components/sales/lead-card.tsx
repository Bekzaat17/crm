"use client";
import Link from "next/link";
import { Phone } from "lucide-react";
import type { LeadRecord } from "@/lib/types";
import { formatShort, isPast } from "@/lib/format";

export function LeadCard({
  lead,
  href,
  pending,
}: {
  lead: LeadRecord;
  href: string;
  pending: boolean;
}) {
  return (
    <Link
      href={href}
      className={`lead-card ${pending ? "lead-card-pending" : ""}`}
      draggable
      onDragStart={(event) => {
        event.dataTransfer.setData("text/lead-id", lead.id);
        event.dataTransfer.effectAllowed = "move";
      }}
    >
      <span className="lead-source">{lead.source || "Источник не указан"}</span>
      <strong>{lead.title}</strong>
      <span>{lead.client_name}</span>
      {lead.phone && (
        <span className="lead-phone">
          <Phone size={12} />
          {lead.phone}
        </span>
      )}
      <footer>
        <span>{lead.assignee_name}</span>
        {lead.next_contact_at && (
          <time className={isPast(lead.next_contact_at) ? "overdue" : ""}>
            {formatShort(lead.next_contact_at)}
          </time>
        )}
      </footer>
    </Link>
  );
}
