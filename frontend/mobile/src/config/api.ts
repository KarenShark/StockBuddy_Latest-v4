// API configuration
// Web version uses localhost, mobile uses LAN IP

// @ts-ignore
const isWeb = typeof window !== 'undefined' && !window.navigator.product;

// Web environment uses localhost, mobile uses LAN IP
export const API_BASE_URL = isWeb 
  ? 'http://localhost:8000'  // Web browser
  : 'http://172.27.183.237:8000';  // Mobile (Expo Go)

export const API_ENDPOINTS = {
  health: `${API_BASE_URL}/api/health`,
  analyze: `${API_BASE_URL}/api/analyze`,
  analysisStatus: (taskId: string) => `${API_BASE_URL}/api/analysis/${taskId}`,
  analysisResult: (taskId: string) => `${API_BASE_URL}/api/analysis/${taskId}/result`,
  tasks: `${API_BASE_URL}/api/tasks`,
};
