import { Centers } from "@/components/settings/centers";
import { RequirePerm } from "@/components/settings/settings-tabs";

export default function CentersPage() {
  return (
    <RequirePerm perm="manage_centers">
      <Centers />
    </RequirePerm>
  );
}
