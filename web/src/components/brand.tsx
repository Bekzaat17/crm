export function Brand({ light = false }: { light?: boolean }) {
  return (
    <div className={`brand ${light ? "brand-light" : ""}`}>
      {/* Логотип RehubPro: web/public/logo.png из rehubpro-main/static/logo. */}
      <img
        className="brand-logo"
        src="/logo.png"
        alt=""
        width={34}
        height={34}
      />
      <span>
        rehub<span className="brand-pro">pro</span>
        <span className="brand-crm">CRM</span>
      </span>
    </div>
  );
}
