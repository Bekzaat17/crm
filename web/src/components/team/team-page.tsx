"use client";
import { useState } from "react";
import { Circle, Crown, Mail, Plus } from "lucide-react";
import { api } from "@/lib/api";
import {
  ROLE_LABELS,
  type Invitation,
  type Member,
  type Role,
} from "@/lib/types";
import { useMutation } from "@/lib/use-mutation";
import { useResource } from "@/lib/use-resource";
import { ConfirmDialog } from "@/components/ui/dialog";
import {
  EmptyState,
  ErrorAlert,
  LoadingState,
  Notice,
} from "@/components/ui/feedback";
import { PageHeading } from "@/components/ui/page-heading";
import { useCompany } from "@/components/workspace/company-context";
import { useSection } from "@/components/workspace/shell";
import { InviteDialog } from "./invite-dialog";
import { OwnershipDialog } from "./ownership-dialog";

type Team = { members: Member[]; invitations: Invitation[] };
type Confirm =
  | { kind: "deactivate"; member: Member }
  | { kind: "revoke"; invitation: Invitation };

const STATUS_LABELS = {
  pending: "Ожидает ответа",
  accepted: "Принято",
  revoked: "Отозвано",
  expired: "Истекло",
};

export function TeamPage() {
  const {
    root,
    session,
    organization,
    can,
    reload: reloadCompany,
  } = useCompany();
  const { item, eyebrow } = useSection();
  const team = useResource<Team>(`${root}/team`);
  const [notice, setNotice] = useState("");
  const [inviting, setInviting] = useState(false);
  const [transferring, setTransferring] = useState(false);
  const [confirm, setConfirm] = useState<Confirm | null>(null);
  const action = useMutation(team.reload);

  const changeRole = (member: Member, role: Role) =>
    action.run(async () => {
      await api(`${root}/members/${member.id}/role`, { role });
      setNotice(`${member.name}: роль «${ROLE_LABELS[role]}».`);
    });
  const confirmAction = () =>
    confirm &&
    action.run(async () => {
      const path =
        confirm.kind === "deactivate"
          ? `members/${confirm.member.id}/deactivate`
          : `invitations/${confirm.invitation.id}/revoke`;
      const result = await api<{ message: string }>(`${root}/${path}`, {});
      setConfirm(null);
      setNotice(result.message);
    });

  const pending =
    team.data?.invitations.filter((i) => i.status === "pending").length || 0;
  return (
    <>
      <PageHeading
        eyebrow={eyebrow}
        title={item?.label || "Команда"}
        description={item?.description}
        actions={
          <>
            {can("transfer_ownership") && (
              <button
                className="button secondary"
                onClick={() => setTransferring(true)}
              >
                <Crown size={16} /> Передать владение
              </button>
            )}
            <button
              className="button primary"
              onClick={() => setInviting(true)}
            >
              <Plus size={16} /> Пригласить сотрудника
            </button>
          </>
        }
      />
      <Notice message={notice} onClose={() => setNotice("")} />
      <ErrorAlert message={team.error} onRetry={team.reload} />
      {!confirm && <ErrorAlert message={action.error} />}
      {!team.data ? (
        <LoadingState />
      ) : (
        <>
          <div className="section-title table-section-title">
            <h2>
              Сотрудники{" "}
              <span className="subtle-pill">
                {team.data.members.filter((m) => m.is_active).length}
              </span>
            </h2>
            <span className="small muted">
              Роли действуют только в этой компании
            </span>
          </div>
          <div className="card table-card">
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Сотрудник</th>
                    <th>Роль</th>
                    <th>Доступ</th>
                    <th>
                      <span className="sr-only">Действия</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {team.data.members.map((m) => (
                    <tr key={m.id}>
                      <td>
                        <div className="member-cell">
                          <span className="avatar light-avatar">
                            {m.name.slice(0, 1)}
                          </span>
                          <div>
                            <strong>
                              {m.name}
                              {m.user_id === session.user?.id && (
                                <span className="you-label">Вы</span>
                              )}
                            </strong>
                            <span>{m.email}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        {m.manageable && can("manage_roles") ? (
                          <select
                            aria-label={`Роль сотрудника ${m.name}`}
                            value={m.role}
                            disabled={action.busy}
                            onChange={(e) =>
                              void changeRole(m, e.target.value as Role)
                            }
                          >
                            {organization.assignable_roles.map((role) => (
                              <option key={role} value={role}>
                                {ROLE_LABELS[role]}
                              </option>
                            ))}
                          </select>
                        ) : (
                          m.role_label
                        )}
                      </td>
                      <td>
                        <span
                          className={`status ${m.is_active ? "status-active" : "status-muted"}`}
                        >
                          <Circle size={7} fill="currentColor" />
                          {m.is_active ? "Активен" : "Отключён"}
                        </span>
                      </td>
                      <td>
                        {m.manageable && (
                          <button
                            className="text-button danger-text"
                            onClick={() => {
                              action.setError("");
                              setConfirm({ kind: "deactivate", member: m });
                            }}
                          >
                            Отключить
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="section-title table-section-title">
            <h2>
              Приглашения <span className="subtle-pill">{pending}</span>
            </h2>
          </div>
          <div className="card table-card">
            {team.data.invitations.length ? (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Электронная почта</th>
                      <th>Роль</th>
                      <th>Статус</th>
                      <th>
                        <span className="sr-only">Действия</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {team.data.invitations.map((i) => (
                      <tr key={i.id}>
                        <td>
                          <span className="invite-email">
                            <Mail size={16} />
                            {i.email}
                          </span>
                        </td>
                        <td>{i.role_label}</td>
                        <td>
                          <span
                            className={`status ${i.status === "pending" ? "status-pending" : "status-muted"}`}
                          >
                            {STATUS_LABELS[i.status]}
                          </span>
                        </td>
                        <td>
                          {i.status === "pending" && (
                            <button
                              className="text-button"
                              onClick={() => {
                                action.setError("");
                                setConfirm({ kind: "revoke", invitation: i });
                              }}
                            >
                              Отозвать
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState
                icon={<Mail size={25} />}
                title="Начните с приглашения"
                text="Сотрудник получит письмо и присоединится к вашей компании."
              />
            )}
          </div>
        </>
      )}
      {inviting && (
        <InviteDialog
          onClose={() => setInviting(false)}
          onDone={(message) => {
            setInviting(false);
            setNotice(message);
            team.reload();
          }}
        />
      )}
      {transferring && team.data && (
        <OwnershipDialog
          members={team.data.members}
          onClose={() => setTransferring(false)}
          onDone={() => {
            setTransferring(false);
            setNotice("Владение компанией передано. Вы теперь администратор.");
            reloadCompany();
          }}
        />
      )}
      {confirm && (
        <ConfirmDialog
          title={
            confirm.kind === "deactivate"
              ? "Отключить доступ?"
              : "Отозвать приглашение?"
          }
          text={
            confirm.kind === "deactivate"
              ? `${confirm.member.name} потеряет доступ к этой компании. Аккаунт и работа в других компаниях сохранятся.`
              : `Ссылка из письма для ${confirm.invitation.email} перестанет действовать.`
          }
          confirmLabel={
            confirm.kind === "deactivate" ? "Отключить доступ" : "Отозвать"
          }
          danger
          busy={action.busy}
          error={action.error}
          onClose={() => setConfirm(null)}
          onConfirm={() => void confirmAction()}
        />
      )}
    </>
  );
}
