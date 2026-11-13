import type { Metadata } from "next";
import "./globals.css";
import "./rehub-theme.css";

export const metadata: Metadata = {
  title: "RehubPro CRM — рабочее пространство центра",
  description:
    "Команда, обращения и поступления вашего реабилитационного центра.",
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
