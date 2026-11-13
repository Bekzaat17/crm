import { ArrowUpRight } from "lucide-react";

export function Brand({ light = false }: { light?: boolean }) {
  return (
    <div className={`brand ${light ? "brand-light" : ""}`}>
      <span className="brand-mark">
        <ArrowUpRight size={23} strokeWidth={2.8} />
      </span>
      <span>
        rehub<span className="brand-pro">pro</span>
        <span className="brand-crm">CRM</span>
      </span>
    </div>
  );
}
