import {
  Activity,
  BarChart3,
  CheckSquare,
  Layers3,
  LayoutDashboard,
  Settings,
  UserRound,
  Users,
  type LucideIcon,
} from "lucide-react";
import type { Perm } from "@/lib/types";

export type NavItem = {
  /** Путь относительно /c/{companyId}. */
  path: string;
  label: string;
  description: string;
  icon: LucideIcon;
  perm?: Perm;
};

export const NAVIGATION: NavItem[] = [
  {
    path: "",
    label: "Обзор",
    description: "Сводка по обращениям и задачам компании.",
    icon: LayoutDashboard,
  },
  {
    path: "/leads",
    label: "Воронка",
    description:
      "Обращения по этапам. Перетащите карточку, чтобы сменить этап.",
    icon: Layers3,
  },
  {
    path: "/clients",
    label: "Клиенты",
    description: "Карточки клиентов и контактные лица.",
    icon: UserRound,
  },
  {
    path: "/tasks",
    label: "Задачи",
    description: "Задачи менеджеров, сроки и следующие контакты.",
    icon: CheckSquare,
  },
  {
    path: "/analytics",
    label: "Аналитика",
    description: "Сколько обратились, поступили и отказались за период.",
    icon: BarChart3,
  },
  {
    path: "/team",
    label: "Команда",
    description: "Сотрудники, роли, приглашения и доступ к компании.",
    icon: Users,
    perm: "manage_team",
  },
  {
    path: "/activity",
    label: "История действий",
    description: "Изменения в компании и управление доступом.",
    icon: Activity,
    perm: "view_audit",
  },
  {
    path: "/settings",
    label: "Настройки",
    description: "Компания, филиалы, воронка, центры и уведомления.",
    icon: Settings,
  },
];

/** Активный раздел: самый длинный совпавший префикс пути. */
export function activeNav(pathname: string, base: string) {
  const relative = pathname.slice(base.length) || "";
  return [...NAVIGATION]
    .sort((a, b) => b.path.length - a.path.length)
    .find((item) =>
      item.path === ""
        ? relative === "" || relative === "/"
        : relative === item.path || relative.startsWith(`${item.path}/`),
    );
}
