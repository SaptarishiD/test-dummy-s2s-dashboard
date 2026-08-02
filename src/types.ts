export type ValidationStatus = "green" | "warning" | "failure";
export type InitialConditionSourceId = "gfs" | "era5";

export type ProductKey =
  | "rainfall_total"
  | "rainfall_anomaly"
  | "temperature_mean"
  | "temperature_anomaly";

export type GlobalVariableKey =
  | "precipitation"
  | "temperature"
  | "z500"
  | "wind850"
  | "mslp"
  | "sst"
  | "olr"
  | "tcwv";

export type GlobalDisplayMode = "absolute" | "anomaly";

export interface LegendDefinition {
  boundaries: number[];
  colors: string[];
  under: string;
  over: string;
}

export interface ProductDefinition {
  label: string;
  short_label: string;
  description: string;
  units: string;
  baseline: string | null;
  legend: LegendDefinition;
}

export interface FieldSummary {
  india_weighted_mean: number;
  india_minimum: number;
  india_maximum: number;
}

export interface ForecastWeek {
  week: number;
  valid_start: string;
  valid_end: string;
  fields: Record<ProductKey, number[]>;
  summary: Record<ProductKey, FieldSummary>;
}

export interface ForecastData {
  schema_version: number;
  generated_at: string;
  issue: {
    initialization: string;
    information_cutoff: string;
    model_state_time: string;
    input_days: string[];
    input_source: string;
    members: number;
    lead_days: number;
    status: "green" | "warning";
    scientific_status: string;
    initial_condition_source: {
      id: InitialConditionSourceId;
      label: string;
      short_label: string;
      category: "operational_proxy" | "reanalysis_reference";
      availability: "near_real_time" | "delayed_reference";
      description: string;
    };
    downloads: {
      compact_json: string;
      india_netcdf: string;
      india_summary_csv: string;
      manifest: string;
      india_pdf: string;
    };
    climatology_alignment: {
      target_model_state_calendar_day: string;
      left_slot: string;
      right_slot: string;
      right_weight: number;
      operation_order: string;
    };
    hindcast_years: number[];
    observation_verification: {
      status: string;
      message: string;
    };
  };
  grid: {
    shape: [number, number];
    spacing_degrees: number;
    latitude: number[];
    longitude: number[];
    india_mask: boolean[];
    supported_cell_count: number;
    value_order: string;
  };
  products: Record<ProductKey, ProductDefinition>;
  diagnostics: {
    rainfall_weekly_mean_max_mm_day: number;
    temperature_weekly_mean_max_deg_c: number;
  };
  weeks: ForecastWeek[];
}

export interface ValidationCheck {
  id: string;
  label: string;
  group: string;
  status: ValidationStatus;
  summary: string;
  details: Record<string, unknown>;
}

export interface ValidationData {
  schema_version: number;
  generated_at: string;
  overall_status: ValidationStatus;
  presentation_allowed: boolean;
  checks: ValidationCheck[];
  warnings: string[];
  verification_metrics?: {
    status: string;
    reason: string;
  };
}

export interface SourceEntry {
  id: string;
  name: string;
  product: string;
  period: string;
  grid: string;
  units: Record<string, string>;
  sha256: string;
  validation_status: ValidationStatus;
}

export interface SourcesData {
  schema_version: number;
  generated_at: string;
  sources: SourceEntry[];
  observation_identity: Record<string, string>;
}

export interface FormulaDefinition {
  expression: string;
  description: string;
}

export interface FormulasData {
  schema_version: number;
  formula_version: string;
  definitions: Record<string, FormulaDefinition>;
  statistics: Record<string, string>;
  baseline_separation: Record<string, string>;
}

export interface OutlineData {
  schema_version: number;
  description: string;
  geometry: {
    type: string;
    coordinates?: unknown;
    geometries?: Array<{
      type: string;
      coordinates: unknown;
    }>;
  };
}

export interface GlobalBinaryDefinition {
  path: string;
  sha256: string;
  size_bytes: number;
  dtype: "uint16-little-endian";
  offset: number;
  scale: number;
  minimum: number;
  maximum: number;
  frame_ranges: Array<{
    minimum: number;
    maximum: number;
  }>;
}

export interface GlobalVariableDefinition extends GlobalBinaryDefinition {
  label: string;
  short_label: string;
  units: string;
  description: string;
  family: "surface" | "circulation" | "ocean-convection";
  interpretation: string;
  domain?: "global" | "ocean";
  vector?: {
    u: GlobalBinaryDefinition;
    v: GlobalBinaryDefinition;
    statistic: string;
  };
  spread: GlobalSpreadDefinition;
  anomaly?: GlobalAnomalyDefinition;
  legend: LegendDefinition;
}

export interface GlobalAnomalyDefinition extends GlobalBinaryDefinition {
  label: string;
  short_label: string;
  units: string;
  description: string;
  baseline: {
    name: string;
    source_file: string;
    source_sha256: string;
    initialization_slot: string;
    hindcast_years: number[];
    years: 20;
    native_members_per_year: 51;
    lead_days: 42;
    weighting: string;
  };
  legend: LegendDefinition;
}

export interface GlobalSpreadDefinition extends GlobalBinaryDefinition {
  offset: 0;
  frame_area_means: number[];
  statistic: string;
}

export interface GlobalMetadata {
  schema_version: number;
  generated_at: string;
  issue: {
    initialization: string;
    members: number;
    lead_days: number;
    status: "experimental";
    public_label: string;
    input_description: string;
    ensemble_relation: string;
    display_interpolation: string;
  };
  grid: {
    shape: [number, number];
    spacing_degrees: number;
    latitude_first: number;
    latitude_last: number;
    longitude_first: number;
    longitude_last: number;
    value_order: string;
    ocean_mask: {
      path: string;
      sha256: string;
      size_bytes: number;
      dtype: "uint8";
      meaning: string;
    };
  };
  valid_period_starts: string[];
  variables: Record<GlobalVariableKey, GlobalVariableDefinition>;
  validation: {
    status: ValidationStatus;
    checks: string[];
  };
}

export interface GlobalForecastData {
  metadata: GlobalMetadata;
  fields: Partial<Record<GlobalVariableKey, Uint16Array>>;
  anomalies: Partial<Record<GlobalVariableKey, Uint16Array>>;
  spreads: Partial<Record<GlobalVariableKey, Uint16Array>>;
  vectors: Partial<
    Record<GlobalVariableKey, { u: Uint16Array; v: Uint16Array }>
  >;
  oceanMask: Uint8Array;
  loadVariable: (key: GlobalVariableKey) => Promise<void>;
}

export interface WorldCountriesData {
  type: "FeatureCollection";
  features: Array<{
    type: "Feature";
    properties?: {
      NAME?: string;
      NAME_EN?: string;
      ADMIN?: string;
      LABEL_X?: number;
      LABEL_Y?: number;
      LABELRANK?: number;
      MIN_LABEL?: number;
      MAX_LABEL?: number;
      POP_EST?: number;
    };
    geometry: {
      type: "Polygon" | "MultiPolygon";
      coordinates: number[][][] | number[][][][];
    } | null;
  }>;
}

export interface IndiaAdminData {
  type: "FeatureCollection";
  name: string;
  description: string;
  source: {
    name: string;
    product: string;
    source_sha256: string;
    display_note: string;
  };
  features: Array<{
    type: "Feature";
    properties: {
      name: string;
      label: boolean;
      label_longitude: number;
      label_latitude: number;
    };
    geometry: {
      type: "Polygon" | "MultiPolygon";
      coordinates: number[][][] | number[][][][];
    };
  }>;
}

export interface IndiaMapGeographyData {
  schema_version: 1;
  description: string;
  view_box: [0, 0, 620, 620];
  world_path: string;
  india_outline_path: string;
  india_admin_path: string;
  sources: {
    world_countries_sha256: string;
    india_outline_sha256: string;
    india_admin_sha256: string;
  };
}

export interface IssueIndexData {
  schema_version: number;
  default_view: "india";
  default_source: InitialConditionSourceId;
  latest_successful_issue: string;
  initial_condition_sources: Array<{
    id: InitialConditionSourceId;
    label: string;
    short_label: string;
    category: "operational_proxy" | "reanalysis_reference";
    status: "experimental" | "reference";
    description: string;
    default_issue: string;
    issues: Array<{
      id: string;
      initialization: string;
      members: number;
      status: "green" | "warning";
      role: "operational_experimental" | "reference" | "rapid_prototype";
      forecast: string;
    }>;
  }>;
  available_issues: Array<{
    id: string;
    initialization: string;
    status: "green" | "warning";
    forecast: string;
  }>;
}

export interface AppData {
  index?: IssueIndexData;
  forecast?: ForecastData;
  validation?: ValidationData;
  indiaGeography?: IndiaMapGeographyData;
  global?: GlobalForecastData;
  world?: WorldCountriesData;
  indiaAdmin?: IndiaAdminData;
}
