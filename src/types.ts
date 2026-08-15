export interface FindingRecord {
  what: string;
  where: string;
  why: string;
  verdict: 'HEALTHY' | 'DEGRADED' | 'FAILED' | 'INCONCLUSIVE' | 'BLOCKED' | string;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | 'UNKNOWN' | string;
  corroboration: string[];
  evidence_ids: string[];
  failure_class?: string | null;
  conflicts?: string[];
  plugin_id?: string | null;
  notes?: string[];
}

export interface ReportSection {
  title: string;
  status: string;
  verdict: string;
  findings: FindingRecord[];
  attachments?: any[];
  metadata?: Record<string, any>;
}

export interface ReportSummary {
  overall_verdict: string;
  lowest_confidence: string;
  total_findings: number;
  healthy: number;
  degraded: number;
  failed: number;
  inconclusive: number;
  blocked: number;
  layers_covered: (string | { id: string; label: string })[];
  failure_classes: Record<string, number>;
  duration_seconds?: number;
  has_unanswered_questions?: boolean;
}

export interface ReportMetadata {
  execution_id: string;
  generated_at: string;
  environment: string;
  framework_name: string;
  framework_version: string;
  validation_standard_version: string;
  host?: string | null;
  organization?: string | null;
  build_number?: string | null;
  agent_version?: string | null;
  extra?: Record<string, any>;
}

export interface StructuredReport {
  metadata: ReportMetadata;
  summary: ReportSummary;
  sections: ReportSection[];
}

export interface RunReport {
  verdict: string;
  confidence: string;
  findings: number;
  layers: string[];
  report_file?: string;
  raw_output?: string;
}

export interface FeatureProfile {
  feature_id: string;
  name: string;
  verification_status: string;
  note: string;
  expected_sqlite_tables: string[];
  expected_runtime_components: string[];
  expected_apis: string[];
  expected_dashboard_pages: string[];
}

export interface PluginInfo {
  id: string;
  name: string;
  status: string;
}
