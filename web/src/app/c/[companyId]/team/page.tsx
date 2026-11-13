import { RequirePerm } from "@/components/settings/settings-tabs";
import { TeamPage } from "@/components/team/team-page";

export default function Team() {
  return (
    <RequirePerm perm="manage_team">
      <TeamPage />
    </RequirePerm>
  );
}
