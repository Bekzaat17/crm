"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";
import type { LeadRecord, PipelineMeta } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { Admission } from "@/components/integrations/admission";
import { useCompany } from "@/components/workspace/company-context";
import { LeadActivity } from "./lead-activity";
import { LeadConversations } from "./lead-conversations";
import { LeadForm } from "./lead-form";

export function LeadDetail() {
  const { leadId } = useParams<{ leadId: string }>();
  const { root, base, organization } = useCompany();
  const lead = useResource<LeadRecord>(`${root}/leads/${leadId}`);
  const meta = useResource<PipelineMeta>(`${root}/pipeline`);
  if (lead.error || meta.error)
    return (
      <ErrorAlert
        message={lead.error || meta.error}
        onRetry={() => {
          if (lead.error) lead.reload();
          if (meta.error) meta.reload();
        }}
      />
    );
  if (!lead.data || !meta.data) return <LoadingState />;
  const record = lead.data;
  return (
    <>
      <PageHeading
        eyebrow={organization.name}
        title={record.title}
        description={`${record.stage_label} · ${record.assignee_name}`}
        actions={
          <Link className="button secondary" href={`${base}/leads`}>
            <ArrowLeft size={16} /> К воронке
          </Link>
        }
      />
      <Link
        className="text-button"
        href={`${base}/clients/${record.client_id}`}
      >
        Карточка клиента: {record.client_name} <ArrowRight size={14} />
      </Link>
      <LeadForm
        key={record.version}
        root={root}
        lead={record}
        meta={meta.data}
        onSaved={lead.reload}
      />
      <article className="card sales-section">
        <Admission
          root={root}
          lead={record}
          canSend={meta.data.can_send}
          onSaved={lead.reload}
        />
      </article>
      <LeadConversations path={`${root}/leads/${record.id}/conversations`} />
      <LeadActivity root={root} lead={record} onChanged={lead.reload} />
    </>
  );
}
