import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PlanSearch — Dublin Planning Intelligence",
  description: "Search, explore, and analyse Dublin City Council planning applications. AI-classified by development type, enriched with company data, and linked to public documents.",
  keywords: "Dublin, planning, applications, search, DCC, planning permission, Ireland",
  openGraph: {
    title: "PlanSearch — Dublin Planning Intelligence",
    description: "A modern, searchable database of all Dublin City Council planning applications.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="icon" href="/favicon.ico" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </head>
      <body>
        {children}
      </body>
    </html>
  );
}
