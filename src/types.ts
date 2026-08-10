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
