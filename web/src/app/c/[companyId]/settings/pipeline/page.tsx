import { PipelineSettings } from "@/components/settings/pipeline-settings";
import { RequirePerm } from "@/components/settings/settings-tabs";

export default function PipelinePage() {
  return (
    <RequirePerm perm="manage_pipeline">
      <PipelineSettings />
    </RequirePerm>
  );
}
