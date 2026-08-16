import type { AuthTokens, User, Project, ImageryAnalysis, DashboardStats } from './types';

const API_BASE = 'http://localhost:8000/api/v1';

const getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const api = {
  auth: {
    login: async (email: string, password: string): Promise<AuthTokens> => {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(err.detail || 'Login failed');
      }
      return res.json();
    },

    register: async (email: string, password: string, full_name: string, role = 'planner'): Promise<User> => {
      const res = await fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, full_name, role })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Registration failed' }));
        throw new Error(err.detail || 'Registration failed');
      }
      return res.json();
    },

    getMe: async (): Promise<User> => {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Session expired');
      return res.json();
    }
  },

  projects: {
    list: async (): Promise<Project[]> => {
      const res = await fetch(`${API_BASE}/projects`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Failed to fetch projects');
      return res.json();
    },

    create: async (name: string, description?: string): Promise<Project> => {
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ name, description })
      });
      if (!res.ok) throw new Error('Failed to create project');
      return res.json();
    }
  },

  inference: {
    upload: async (projectId: number, file: File, populationEstimate = 1000): Promise<ImageryAnalysis> => {
      const formData = new FormData();
      formData.append('project_id', projectId.toString());
      formData.append('population_estimate', populationEstimate.toString());
      formData.append('file', file);

      const res = await fetch(`${API_BASE}/inference/upload`, {
        method: 'POST',
        headers: { ...getAuthHeaders() },
        body: formData
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      return res.json();
    },

    run: async (analysisId: number): Promise<ImageryAnalysis> => {
      const res = await fetch(`${API_BASE}/inference/${analysisId}/run`, {
        method: 'POST',
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Inference failed' }));
        throw new Error(err.detail || 'Inference failed');
      }
      return res.json();
    },

    getStatus: async (analysisId: number): Promise<ImageryAnalysis> => {
      const res = await fetch(`${API_BASE}/inference/${analysisId}/status`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Failed to fetch analysis status');
      return res.json();
    }
  },

  gis: {
    getGeoJson: async (analysisId: number): Promise<any> => {
      const res = await fetch(`${API_BASE}/gis/analyses/${analysisId}/geojson`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Failed to load GIS layer data');
      return res.json();
    }
  },

  analytics: {
    getDashboardStats: async (): Promise<DashboardStats> => {
      const res = await fetch(`${API_BASE}/analytics/dashboard`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Failed to load dashboard metrics');
      return res.json();
    },

    getBenchmark: async (analysisId: number): Promise<any> => {
      const res = await fetch(`${API_BASE}/analytics/analyses/${analysisId}/benchmark`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Failed to load benchmark details');
      return res.json();
    }
  },

  reports: {
    downloadPdfUrl: (analysisId: number) => `${API_BASE}/reports/analyses/${analysisId}/pdf`,
    downloadCsvUrl: (analysisId: number) => `${API_BASE}/reports/analyses/${analysisId}/csv`
  },

  users: {
    list: async (): Promise<User[]> => {
      const res = await fetch(`${API_BASE}/users`, {
        headers: { ...getAuthHeaders() }
      });
      if (!res.ok) throw new Error('Failed to list users');
      return res.json();
    }
  }
};
