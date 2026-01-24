// Type definitions

export interface AnalysisRequest {
  ticker: string;
  analysis_date?: string;
  analysts?: string[];
  research_depth?: number;
  llm_provider?: string;
  quick_think_llm?: string;
  deep_think_llm?: string;
}

export interface AnalysisResponse {
  task_id: string;
  status: string;
  message: string;
}

export interface TaskProgress {
  current_agent: string;
  percentage: number;
}

export interface TaskStatus {
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress?: TaskProgress;
  result?: AnalysisResult;
  error?: string;
}

export interface AnalysisResult {
  ticker: string;
  analysis_date: string;
  decision: string;
  market_report?: string;
  sentiment_report?: string;
  news_report?: string;
  fundamentals_report?: string;
  investment_plan?: string;
  trader_investment_plan?: string;
  final_trade_decision?: string;
  completed_at?: string;
}

export type RootStackParamList = {
  Test: undefined;
  Home: undefined;
  Analysis: { taskId: string; ticker: string };
};
