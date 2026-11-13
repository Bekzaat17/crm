export type ClientRecord = {
  id: string;
  name: string;
  phone: string;
  city: string;
  date_of_birth: string;
  notes: string;
  version: number;
  contacts?: {
    id: string;
    name: string;
    phone: string;
    relationship: string;
  }[];
  leads?: LeadRecord[];
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
  refusal_reason: string;
  next_contact_at: string;
  version: number;
  activities?: {
    id: string;
    text: string;
    actor: string;
    created_at: string;
  }[];
};
export type Metadata = {
  stages: { id: string; name: string }[];
  assignees: { id: string; name: string }[];
  branches: { id: string; name: string }[];
  can_assign: boolean;
  can_send: boolean;
};
export type List<T> = {
  items: T[];
  total: number;
  has_more: boolean;
  counts?: Record<string, number>;
};
