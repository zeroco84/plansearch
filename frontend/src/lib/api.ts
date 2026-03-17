/**
 * PlanSearch API client
 */

const API_BASE = typeof window === 'undefined'
  ? 'https://api.plansearch.cc'
  : (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : 'https://api.plansearch.cc';

export interface ApplicationSummary {
  id: number;
  reg_ref: string;
  apn_date: string | null;
  proposal: string | null;
  location: string | null;
  decision: string | null;
  dev_category: string | null;
  dev_subcategory: string | null;
  applicant_name: string | null;
  lat: number | null;
  lng: number | null;
  relevance_score: number | null;
  // Phase 2 national fields
  planning_authority: string | null;
  lifecycle_stage: string | null;
  est_value_high: number | null;
  significance_score: number | null;
  num_residential_units: number | null;
  floor_area: number | null;
}

export interface SearchResponse {
  results: ApplicationSummary[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  query_time_ms: number | null;
}

export interface AppealDetail {
  id: number;
  appeal_ref: string | null;
  appeal_date: string | null;
  appellant: string | null;
  appeal_decision: string | null;
  appeal_dec_date: string | null;
}

export interface FurtherInfoDetail {
  id: number;
  fi_date: string | null;
  fi_type: string | null;
  fi_response_date: string | null;
}

export interface CompanyDetail {
  cro_number: string;
  company_name: string;
  company_status: string | null;
  registered_address: string | null;
  incorporation_date: string | null;
  company_type: string | null;
  directors: string[] | null;
}

export interface DocumentDetail {
  id: number;
  doc_name: string;
  doc_type: string | null;
  file_extension: string | null;
  file_size_bytes: number | null;
  portal_source: string | null;
  direct_url: string | null;
  portal_url: string | null;
  uploaded_date: string | null;
  doc_category: string | null;
}

export interface ApplicationDetail {
  id: number;
  reg_ref: string;
  year: number | null;
  apn_date: string | null;
  rgn_date: string | null;
  dec_date: string | null;
  final_grant_date: string | null;
  time_exp: string | null;
  proposal: string | null;
  long_proposal: string | null;
  location: string | null;
  app_type: string | null;
  stage: string | null;
  decision: string | null;
  dev_category: string | null;
  dev_subcategory: string | null;
  classification_confidence: number | null;
  applicant_name: string | null;
  cro_number: string | null;
  lat: number | null;
  lng: number | null;
  portal_url: string | null;
  appeals: AppealDetail[];
  further_info: FurtherInfoDetail[];
  company: CompanyDetail | null;
  documents: DocumentDetail[];
}

export interface StatsResponse {
  total_applications: number;
  total_classified: number;
  total_applicants_scraped: number;
  total_cro_enriched: number;
  total_documents: number;
  categories: Record<string, number>;
  decisions: Record<string, number>;
  years: Record<string, number>;
  last_sync: string | null;
}

export interface MapFeatureCollection {
  type: string;
  features: {
    type: string;
    geometry: { type: string; coordinates: [number, number] };
    properties: {
      reg_ref: string;
      decision: string | null;
      dev_category: string | null;
      proposal: string | null;
      location: string | null;
    };
  }[];
  total: number;
}

export interface SearchParams {
  q?: string;
  category?: string;
  decision?: string;
  applicant?: string;
  location?: string;
  year_from?: number;
  year_to?: number;
  lat?: number;
  lng?: number;
  radius_m?: number;
  authority?: string;
  lifecycle_stage?: string;
  value_min?: number;
  value_max?: number;
  one_off_house?: boolean;
  sort?: string;
  page?: number;
  page_size?: number;
}

// ── API Functions ──────────────────────────────────────────────────────

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }

  return res.json();
}

export async function searchApplications(params: SearchParams): Promise<SearchResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value));
    }
  });
  return fetchApi<SearchResponse>(`/api/search?${query.toString()}`);
}

export async function getApplication(regRef: string): Promise<ApplicationDetail> {
  return fetchApi<ApplicationDetail>(`/api/applications/${encodeURIComponent(regRef)}`);
}

export async function getMapPoints(params: SearchParams): Promise<MapFeatureCollection> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      query.set(key, String(value));
    }
  });
  return fetchApi<MapFeatureCollection>(`/api/map/points?${query.toString()}`);
}

export async function getStats(): Promise<StatsResponse> {
  return fetchApi<StatsResponse>('/api/stats');
}

// Admin APIs
export async function getAdminConfig(token: string) {
  return fetchApi('/api/admin/config', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updateAdminConfig(token: string, data: { key: string; value: string; encrypted?: boolean; description?: string }) {
  return fetchApi('/api/admin/config', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
}

export async function triggerSync(token: string) {
  return fetchApi('/api/admin/sync/trigger', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getSyncStatus(token: string) {
  return fetchApi('/api/admin/sync/status', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function triggerClassification(token: string, batchSize: number = 100) {
  return fetchApi(`/api/admin/classify/trigger?batch_size=${batchSize}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getClassifyStatus(token: string) {
  return fetchApi('/api/admin/classify/status', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function triggerScraping(token: string) {
  return fetchApi('/api/admin/scrape/trigger', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function getScrapeStatus(token: string) {
  return fetchApi('/api/admin/scrape/status', {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function updateApiKey(token: string, keyType: 'claude' | 'cro', apiKey: string) {
  return fetchApi(`/api/admin/keys/${keyType}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ api_key: apiKey }),
  });
}

export async function getAdminLogs(token: string, limit?: number) {
  return fetchApi(`/api/admin/logs${limit ? `?limit=${limit}` : ''}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

// Category display labels
export const CATEGORY_LABELS: Record<string, string> = {
  residential_new_build: 'New Residential',
  residential_extension: 'Extension / Renovation',
  residential_conversion: 'Residential Conversion',
  hotel_accommodation: 'Hotel & Accommodation',
  commercial_retail: 'Retail & Food',
  commercial_office: 'Office',
  industrial_warehouse: 'Industrial / Warehouse',
  mixed_use: 'Mixed Use',
  protected_structure: 'Protected Structure',
  telecommunications: 'Telecoms',
  renewable_energy: 'Renewable Energy',
  signage: 'Signage',
  change_of_use: 'Change of Use',
  demolition: 'Demolition',
  other: 'Other',
};

// Decision colour mapping
export const DECISION_COLORS: Record<string, string> = {
  GRANTED: '#10b981',
  REFUSED: '#ef4444',
  FURTHER_INFO: '#f59e0b',
  SPLIT: '#8b5cf6',
  WITHDRAWN: '#6b7280',
  INVALID: '#6b7280',
  PENDING: '#3b82f6',
};

export function getDecisionColor(decision: string | null): string {
  if (!decision) return '#6b7280';
  const upper = decision.toUpperCase();
  for (const [key, color] of Object.entries(DECISION_COLORS)) {
    if (upper.includes(key)) return color;
  }
  return '#6b7280';
}

export function formatDate(date: string | null): string {
  if (!date) return '—';
  try {
    return new Date(date).toLocaleDateString('en-IE', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    });
  } catch {
    return date;
  }
}

export function formatFileSize(bytes: number | null): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function getPortalDocumentUrl(regRef: string, year: number | null): string {
  if (year && year >= 2024) {
    return `https://planning.localgov.ie/en/view-planning-applications?reference=${encodeURIComponent(regRef)}`;
  }
  return `https://planning.agileapplications.ie/dublincity/search-applications/?reg_ref=${encodeURIComponent(regRef)}`;
}

// ── Phase 2: National constants ────────────────────────────────────────

export const IRISH_AUTHORITIES: Record<string, string[]> = {
  Leinster: [
    'Dublin City Council',
    'Dún Laoghaire-Rathdown County Council',
    'Fingal County Council',
    'South Dublin County Council',
    'Kildare County Council',
    'Meath County Council',
    'Wicklow County Council',
    'Louth County Council',
    'Wexford County Council',
    'Carlow County Council',
    'Kilkenny County Council',
    'Laois County Council',
    'Offaly County Council',
    'Longford County Council',
    'Westmeath County Council',
  ],
  Munster: [
    'Cork City Council',
    'Cork County Council',
    'Kerry County Council',
    'Limerick City & County Council',
    'Tipperary County Council',
    'Waterford City & County Council',
    'Clare County Council',
  ],
  Connacht: [
    'Galway City Council',
    'Galway County Council',
    'Mayo County Council',
    'Roscommon County Council',
    'Sligo County Council',
    'Leitrim County Council',
  ],
  'Ulster (ROI)': [
    'Donegal County Council',
    'Cavan County Council',
    'Monaghan County Council',
  ],
};

export const LIFECYCLE_STAGES: Record<string, string> = {
  submitted: 'Application Submitted',
  registered: 'Registered',
  further_info: 'Further Info Requested',
  decided_granted: 'Granted',
  decided_refused: 'Refused',
  appealed: 'Under Appeal',
  appeal_granted: 'Appeal Granted',
  appeal_refused: 'Appeal Refused',
  fsc_filed: 'FSC Filed — Construction Imminent',
  under_construction: 'Under Construction',
  complete: 'Complete',
  expired: 'Permission Expired',
};

export const LIFECYCLE_COLORS: Record<string, string> = {
  submitted: '#9ca3af',
  registered: '#9ca3af',
  further_info: '#f59e0b',
  decided_granted: '#10b981',
  decided_refused: '#ef4444',
  appealed: '#f59e0b',
  appeal_granted: '#10b981',
  appeal_refused: '#ef4444',
  fsc_filed: '#3b82f6',
  under_construction: '#8b5cf6',
  complete: '#06b6d4',
  expired: '#6b7280',
};

export const VALUE_RANGES = [
  { label: 'Any', value: '' },
  { label: '€500k+', min: 500_000 },
  { label: '€2m+', min: 2_000_000 },
  { label: '€10m+', min: 10_000_000 },
  { label: '€50m+', min: 50_000_000 },
  { label: '€100m+', min: 100_000_000 },
];

export function formatValue(value: number | null): string {
  if (!value) return '—';
  if (value >= 1_000_000) return `€${(value / 1_000_000).toFixed(1)}m`;
  if (value >= 1_000) return `€${(value / 1_000).toFixed(0)}k`;
  return `€${value}`;
}

export interface DigestEntry {
  reg_ref: string;
  planning_authority: string;
  location: string | null;
  proposal: string | null;
  applicant: string | null;
  dev_category: string | null;
  num_residential_units: number | null;
  floor_area: number | null;
  est_value_low: number | null;
  est_value_high: number | null;
  est_value_str: string | null;
  est_value_basis: string | null;
  decision: string | null;
  decision_date: string | null;
  link_app_details: string | null;
  significance_score: number | null;
  lifecycle_stage: string | null;
}

export interface DigestResponse {
  week_start: string | null;
  week_end: string | null;
  generated_at: string | null;
  total_entries: number;
  entries: DigestEntry[];
}

export async function getLatestDigest(): Promise<DigestResponse> {
  return fetchApi<DigestResponse>('/api/digest/latest');
}

// ── Phase 3: The Build Integration ────────────────────────────────────

export interface InsightsPost {
  id: number;
  slug: string;
  title: string;
  subtitle: string | null;
  excerpt: string | null;
  featured_image_url: string | null;
  substack_url: string;
  published_at: string | null;
  summary_one_line: string | null;
  topics: string[];
  mentioned_councils: string[];
  tone: string | null;
  related_app_count: number;
}

export interface LinkedApplication {
  id: number;
  reg_ref: string;
  proposal: string | null;
  location: string | null;
  decision: string | null;
  planning_authority: string | null;
  lifecycle_stage: string | null;
  est_value_high: number | null;
  link_type: string;
  confidence: number;
}

export interface InsightsPostDetail extends InsightsPost {
  related_applications: LinkedApplication[];
}

export interface InsightsFeedResponse {
  posts: InsightsPost[];
  total: number;
  page: number;
  total_pages: number;
}

export async function getInsightsFeed(page: number = 1): Promise<InsightsFeedResponse> {
  return fetchApi<InsightsFeedResponse>(`/api/insights?page=${page}&page_size=12`);
}

export async function getInsightsPost(slug: string): Promise<InsightsPostDetail> {
  return fetchApi<InsightsPostDetail>(`/api/insights/${slug}`);
}

export async function getInsightsByTopic(topic: string, page: number = 1): Promise<InsightsFeedResponse> {
  return fetchApi<InsightsFeedResponse>(`/api/insights/topic/${topic}?page=${page}`);
}

export interface BuildRelatedPost {
  slug: string;
  title: string;
  excerpt: string | null;
  tone: string | null;
  published_at: string | null;
  substack_url: string;
  link_type: string;
  confidence: number;
}

export async function getRelatedPosts(regRef: string): Promise<{ posts: BuildRelatedPost[] }> {
  return fetchApi<{ posts: BuildRelatedPost[] }>(`/api/insights/related/${encodeURIComponent(regRef)}`);
}

// ── Phase 3: Advertising ─────────────────────────────────────────────

export interface AdDisplay {
  campaign_id: number;
  advertiser: string;
  headline: string | null;
  body_text: string | null;
  cta_text: string | null;
  cta_url: string | null;
  logo_url: string | null;
  campaign_type: string;
}

export async function getContextualAd(params: {
  dev_category?: string;
  council?: string;
  lifecycle_stage?: string;
  page_path?: string;
}): Promise<AdDisplay | null> {
  const qs = new URLSearchParams();
  if (params.dev_category) qs.set('dev_category', params.dev_category);
  if (params.council) qs.set('council', params.council);
  if (params.lifecycle_stage) qs.set('lifecycle_stage', params.lifecycle_stage);
  if (params.page_path) qs.set('page_path', params.page_path);
  try {
    return await fetchApi<AdDisplay>(`/api/ads/contextual?${qs.toString()}`);
  } catch {
    return null;
  }
}

export async function recordAdClick(campaignId: number): Promise<void> {
  await fetch(`${API_BASE}/api/ads/click/${campaignId}`, { method: 'POST' });
}

export const TOPIC_LABELS: Record<string, string> = {
  judicial_review: 'Judicial Review',
  LRD: 'LRD',
  SHD: 'SHD',
  student_accommodation: 'Student Accommodation',
  build_to_rent: 'Build to Rent',
  social_housing: 'Social Housing',
  apartment_guidelines: 'Apartment Guidelines',
  planning_reform: 'Planning Reform',
  ABP: 'An Bord Pleanála',
  further_information: 'Further Information',
  infrastructure: 'Infrastructure',
  viability: 'Viability',
};

export const TONE_LABELS: Record<string, string> = {
  analysis: 'Analysis',
  opinion: 'Opinion',
  case_study: 'Case Study',
  news: 'News',
};

export const TONE_COLORS: Record<string, string> = {
  analysis: '#3b82f6',
  opinion: '#f59e0b',
  case_study: '#8b5cf6',
  news: '#10b981',
};
