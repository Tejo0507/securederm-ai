/** Shapes of the JSON the backend returns, shared by the dashboard components. */

export interface HospitalInfo {
  id: number;
  name: string;
  email?: string;
  location?: string;
}

export interface PredictionResult {
  model_id?: string | null;
  predicted_class: string;
  confidence: number;
  is_unknown: boolean;
  message: string;
  class_probabilities: Record<string, number>;
  top_predictions?: { label: string; probability: number }[];
  uncertainty?: number;
}

/** One slot of a batch response: a result, or the reason that file failed. */
export type BatchSlot =
  | ({ index: number; error?: undefined } & PredictionResult)
  | { index: number; error: string };

export interface BatchPredictionResponse {
  count: number;
  failed: number;
  results: BatchSlot[];
}

export interface HistoryItem {
  id: number;
  created_at: string | null;
  model_id: string;
  predicted_class: string;
  confidence: number;
  uncertainty: number;
  is_unknown: boolean;
}

export interface HistoryPage {
  total: number;
  items: HistoryItem[];
}

export interface HistorySummary {
  total: number;
  unknown: number;
  unknown_rate: number;
  average_confidence: number | null;
  first_at: string | null;
  last_at: string | null;
  by_class: Record<string, number>;
  by_model: { model_id: string; count: number }[];
}

export interface ModelInfo {
  available: boolean;
  model_id?: string;
  size_bytes?: number;
  updated_at?: string;
  classes: string[];
  image_size: number;
  unknown_threshold: number;
  temperature: number;
  test_time_augmentation: boolean;
  top_k: number;
}
