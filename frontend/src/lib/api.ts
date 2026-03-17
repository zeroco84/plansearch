/**
 * PlanSearch API client
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
