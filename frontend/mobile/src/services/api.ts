// API services
import axios from 'axios';
import { API_ENDPOINTS } from '../config/api';
import { AnalysisRequest, AnalysisResponse, TaskStatus } from '../types';

const apiClient = axios.create({
  timeout: 10000, // 降低到 10 秒便于快速调试
  headers: {
    'Content-Type': 'application/json',
  },
});

// 添加请求拦截器用于调试
apiClient.interceptors.request.use(
  (config) => {
    console.log(`🌐 API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('❌ Request Error:', error);
    return Promise.reject(error);
  }
);

// 添加响应拦截器用于调试
apiClient.interceptors.response.use(
  (response) => {
    console.log(`✅ API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    if (error.code === 'ECONNABORTED') {
      console.error('⏱️ Request Timeout');
    } else if (error.message === 'Network Error') {
      console.error('🚫 Network Error - Cannot reach server');
    }
    console.error('❌ Response Error:', error.message);
    return Promise.reject(error);
  }
);

export const tradingApi = {
  // Health check
  async healthCheck() {
    const response = await apiClient.get(API_ENDPOINTS.health);
    return response.data;
  },

  // Create analysis task
  async createAnalysis(request: AnalysisRequest): Promise<AnalysisResponse> {
    const response = await apiClient.post<AnalysisResponse>(
      API_ENDPOINTS.analyze,
      request
    );
    return response.data;
  },

  // Get task status
  async getTaskStatus(taskId: string): Promise<TaskStatus> {
    const response = await apiClient.get<TaskStatus>(
      API_ENDPOINTS.analysisStatus(taskId)
    );
    return response.data;
  },

  // Get analysis result
  async getAnalysisResult(taskId: string) {
    const response = await apiClient.get(API_ENDPOINTS.analysisResult(taskId));
    return response.data;
  },

  // Get all tasks
  async getAllTasks() {
    const response = await apiClient.get(API_ENDPOINTS.tasks);
    return response.data;
  },
};
