export type Perm =
  | "manage_team"
  | "manage_roles"
  | "manage_branches"
  | "manage_pipeline"
  | "manage_centers"
  | "view_audit"
  | "view_all_leads"
  | "assign_leads"
  | "send_admissions"
  | "transfer_ownership";

export type Role = "owner" | "admin" | "lead" | "manager";

export const ROLE_LABELS: Record<Role, string> = {
  owner: "Владелец",
  admin: "Администратор",
  lead: "Руководитель",
  manager: "Менеджер",
};

export type Branch = {
  id: string;
  name: string;
  is_active: boolean;
  version: number;
};

export type Organization = {
  id: string;
  name: string;
  role: Role;
  role_label: string;
  permissions: Perm[];
  assignable_roles: Role[];
  branches: Branch[];
  member_count: number;
  created_at: string;
};

export type StageKind = "open" | "admitted" | "refused";

export type Stage = {
  id: string;
  name: string;
  kind: StageKind;
  kind_label: string;
  color: string;
  position: number;
  is_active: boolean;
  version: number;
  lead_count?: number;
};

export type Contact = {
  id: string;
  name: string;
  phone: string;
  relationship: string;
  version: number;
};

export type ClientRecord = {
  id: string;
  name: string;
  phone: string;
  city: string;
  date_of_birth: string;
  notes: string;
  version: number;
  contacts?: Contact[];
  leads?: LeadRecord[];
};

export type Activity = {
  id: string;
  text: string;
  kind: string;
  actor: string;
  created_at: string;
};

export type LeadRecord = {
  id: string;
  title: string;
  client_id: string;
  client_name: string;
  phone: string;
  assignee_id: string;
  assignee_name: string;
  branch_id: string;
  source: string;
  stage: string;
  stage_label: string;
  stage_kind: StageKind;
  refusal_reason: string;
  next_contact_at: string;
  version: number;
  updated_at: string;
  activities?: Activity[];
};

export type PipelineMeta = {
  stages: Stage[];
  assignees: { id: string; name: string }[];
  branches: { id: string; name: string }[];
  can_assign: boolean;
  can_send: boolean;
  can_manage_pipeline: boolean;
};

export type Page<T> = {
  items: T[];
  total: number;
  has_more: boolean;
  counts?: Record<string, number>;
};

export type Task = {
  id: string;
  title: string;
  lead_id: string;
  lead_title: string;
  client_name: string;
  assignee_name: string;
  due_at: string;
  completed: boolean;
  overdue: boolean;
  version: number;
};

export type Member = {
  id: string;
  user_id: string;
  name: string;
  email: string;
  role: Role;
  role_label: string;
  is_active: boolean;
  manageable: boolean;
};

export type Invitation = {
  id: string;
  email: string;
  role: Role;
  role_label: string;
  status: "pending" | "accepted" | "revoked" | "expired";
  created_at: string;
  expires_at: string;
};

export type AuditEvent = {
  id: string;
  action: string;
  actor: string;
  created_at: string;
};
