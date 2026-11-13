"use client";
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Plus } from "lucide-react";
import { api } from "@/lib/api";
import type { ClientRecord, PipelineMeta } from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ErrorAlert, LoadingState } from "@/components/ui/feedback";
import { fields } from "@/components/ui/form";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { ClientFields } from "./client-fields";
import { ContactFields, ContactRow } from "./contact-row";
import { NewLeadDialog } from "./new-lead-dialog";

export function ClientDetail() {
  const { clientId } = useParams<{ clientId: string }>();
  const { root, base, organization } = useCompany();
  const path = `${root}/clients/${clientId}`;
  const client = useResource<ClientRecord>(path);
  const meta = useResource<PipelineMeta>(`${root}/pipeline`);
  const [creatingLead, setCreatingLead] = useState(false);
  const save = useMutation(client.reload);
  const addContact = useMutation(client.reload);
  if (client.error)
    return <ErrorAlert message={client.error} onRetry={client.reload} />;
  if (!client.data) return <LoadingState />;
  const record = client.data;
  return (
    <>
      <PageHeading
        eyebrow={organization.name}
        title={record.name}
        description="Карточка клиента, контактные лица и обращения."
        actions={
          <>
            <Link className="button secondary" href={`${base}/clients`}>
              <ArrowLeft size={16} /> К списку
            </Link>
            <button
              className="button primary"
              disabled={!meta.data}
              onClick={() => setCreatingLead(true)}
            >
              <Plus size={16} /> Новое обращение
            </button>
          </>
        }
      />
      <div className="detail-grid">
        <article className="card">
          <h3>Данные клиента</h3>
          <ErrorAlert message={meta.error} onRetry={meta.reload} />
          <ErrorAlert message={save.error} />
          <form
            key={record.version}
            className="auth-form"
            onSubmit={(e) => {
              e.preventDefault();
              const data = fields(e.currentTarget);
              void save.run(() =>
                api(path, { ...data, version: record.version }),
              );
            }}
          >
            <ClientFields client={record} />
            <button className="button primary" disabled={save.busy}>
              Сохранить карточку
            </button>
          </form>
        </article>
        <div>
          <article className="card">
            <h3>Родственники и контактные лица</h3>
            {record.contacts?.map((contact) => (
              <ContactRow
                key={`${contact.id}-${contact.version}`}
                path={`${path}/contacts/${contact.id}`}
                contact={contact}
                onChanged={client.reload}
              />
            ))}
            <h4 className="sales-section">Новый контакт</h4>
            <ErrorAlert message={addContact.error} />
            <form
              className="auth-form related-form"
              onSubmit={(e) => {
                e.preventDefault();
                const form = e.currentTarget;
                const data = fields(form);
                void addContact.run(async () => {
                  await api(`${path}/contacts`, data);
                  form.reset();
                });
              }}
            >
              <ContactFields />
              <button className="button secondary" disabled={addContact.busy}>
                Добавить контакт
              </button>
            </form>
          </article>
          <article className="card sales-section">
            <h3>Обращения клиента</h3>
            {record.leads?.length ? (
              record.leads.map((lead) => (
                <Link
                  className="client-lead"
                  key={lead.id}
                  href={`${base}/leads/${lead.id}`}
                >
                  <strong>{lead.title}</strong>
                  <span>{lead.stage_label}</span>
                </Link>
              ))
            ) : (
              <p className="small muted">Обращений пока нет.</p>
            )}
          </article>
        </div>
      </div>
      {creatingLead && meta.data && (
        <NewLeadDialog
          meta={meta.data}
          client={record}
          onClose={() => setCreatingLead(false)}
        />
      )}
    </>
  );
}
