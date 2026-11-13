import { ActivityPage } from "@/components/activity/activity-page";
import { RequirePerm } from "@/components/settings/settings-tabs";

export default function Activity() {
  return (
    <RequirePerm perm="view_audit">
      <ActivityPage />
    </RequirePerm>
  );
}
