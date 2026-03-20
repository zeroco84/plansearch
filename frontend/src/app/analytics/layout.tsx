import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Ireland Planning Analytics | PlanSearch — Live Data Dashboard',
  description:
    'Real-time analytics from 600,000+ Irish planning applications. Housing pipeline, data centres, refusal rates, construction value by county.',
  openGraph: {
    title: 'Ireland Planning Analytics | PlanSearch',
    description:
      'Real-time analytics from 600,000+ Irish planning applications. Housing pipeline gap, data centre map, refusal league table, construction value by county.',
    type: 'website',
    url: 'https://plansearch.cc/analytics',
    siteName: 'PlanSearch',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Ireland Planning Analytics | PlanSearch',
    description:
      'Live data dashboard: housing pipeline gap, data centres, refusal rates, and construction value across 43 local authorities.',
  },
};

export default function AnalyticsLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
