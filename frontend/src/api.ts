import type { User, Project, ImageryAnalysis, DashboardStats, AnalyticsResponse } from './types';

const API_BASE = 'http://localhost:8000/api/v1';

/**
 * In-memory access token. Set by AuthContext after login/refresh.
 * NEVER stored in localStorage.
 */
let _accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

const getAuthHeaders = (): Record<string, string> => {
  return _accessToken ? { Authorization: `Bearer ${_accessToken}` } : {};
};

/**
 * Wrapper for fetch that includes credentials (cookies) and handles 401 auto-refresh.
 */
async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(url, {
    ...init,
    credentials: 'include', // Send HttpOnly cookies
    headers: {
      ...getAuthHeaders(),
      ...(init.headers || {}),
    },
  });

  // On 401, attempt one silent refresh then retry
  if (res.status === 401 && _accessToken) {
    try {
      const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (refreshRes.ok) {
        const data = await refreshRes.json();
        _accessToken = data.access_token;

        // Retry original request with new token
        const retryRes = await fetch(url, {
          ...init,
          credentials: 'include',
          headers: {
            ...getAuthHeaders(),
            ...(init.headers || {}),
          },
        });
        return retryRes;
      }
    } catch {
      // Refresh failed — clear session and redirect to login
      _accessToken = null;
      window.dispatchEvent(new Event('auth-failed'));
      window.location.href = '/';
    }
  }

  return res;
}

// Auth response types (no refresh_token in body — it's in HttpOnly cookie)
interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

interface RefreshResponse {
  access_token: string;
  token_type: string;
}

export const api = {
  auth: {
    login: async (email: string, password: string): Promise<LoginResponse> => {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        credentials: 'include', // Receive HttpOnly cookie
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Login failed' }));
        throw new Error(err.detail || 'Login failed');
      }
      const data: LoginResponse = await res.json();
      _accessToken = data.access_token;
      return data;
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

    refresh: async (): Promise<RefreshResponse> => {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include', // Send refresh cookie
      });
      if (!res.ok) {
        throw new Error('Token refresh failed');
      }
      const data: RefreshResponse = await res.json();
      _accessToken = data.access_token;
      return data;
    },

    logout: async (): Promise<void> => {
      await fetch(`${API_BASE}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
      _accessToken = null;
    },

    getMe: async (tokenOverride?: string): Promise<User> => {
      const headers: Record<string, string> = {};
      if (tokenOverride) {
        headers['Authorization'] = `Bearer ${tokenOverride}`;
      } else {
        Object.assign(headers, getAuthHeaders());
      }
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers,
        credentials: 'include',
      });
      if (!res.ok) throw new Error('Session expired');
      return res.json();
    }
  },

  projects: {
    list: async (): Promise<Project[]> => {
      const res = await authFetch(`${API_BASE}/projects`);
      if (!res.ok) throw new Error('Failed to fetch projects');
      return res.json();
    },

    create: async (name: string, description?: string): Promise<Project> => {
      const res = await authFetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
      });
      if (!res.ok) throw new Error('Failed to create project');
      return res.json();
    }
  },

  inference: {
    upload: async (projectId: number, file: File, populationCount?: number, populationSource?: string, populationDate?: string): Promise<ImageryAnalysis> => {
      const formData = new FormData();
      formData.append('project_id', projectId.toString());
      if (populationCount !== undefined) formData.append('population_count', populationCount.toString());
      if (populationSource) formData.append('population_source', populationSource);
      if (populationDate) formData.append('population_date', populationDate);
      formData.append('file', file);

      const res = await authFetch(`${API_BASE}/inference/upload`, {
        method: 'POST',
        body: formData
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      return res.json();
    },

    run: async (analysisId: number): Promise<ImageryAnalysis> => {
      const res = await authFetch(`${API_BASE}/inference/${analysisId}/run`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Inference failed' }));
        throw new Error(err.detail || 'Inference failed');
      }
      return res.json();
    },

    getStatus: async (analysisId: number): Promise<ImageryAnalysis> => {
      const res = await authFetch(`${API_BASE}/inference/${analysisId}/status`);
      if (!res.ok) throw new Error('Failed to fetch analysis status');
      return res.json();
    }
  },

  gis: {
    getGeoJson: async (analysisId: number): Promise<any> => {
      const res = await authFetch(`${API_BASE}/gis/analyses/${analysisId}/geojson`);
      if (!res.ok) throw new Error('Failed to load AI layer data');
      return res.json();
    },
    getOsmGeoJson: async (analysisId: number): Promise<any> => {
      const res = await authFetch(`${API_BASE}/gis/analyses/${analysisId}/osm-enrichment`);
      if (!res.ok) throw new Error('Failed to load OSM layer data');
      return res.json();
    }
  },

  analytics: {
    getDashboardStats: async (): Promise<DashboardStats> => {
      const res = await authFetch(`${API_BASE}/analytics/dashboard`);
      if (!res.ok) throw new Error('Failed to load dashboard metrics');
      return res.json();
    },

    getAnalysisAnalytics: async (analysisId: number): Promise<AnalyticsResponse> => {
      const res = await authFetch(`${API_BASE}/analytics/analyses/${analysisId}`);
      if (!res.ok) throw new Error('Failed to load analysis analytics');
      return res.json();
    }
  },

  reports: {
    downloadPdf: async (analysisId: number): Promise<void> => {
      const res = await authFetch(`${API_BASE}/reports/analyses/${analysisId}/pdf`);
      if (!res.ok) throw new Error('Failed to download PDF');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `UrbanSense_Report_Analysis_${analysisId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    },
    downloadCsv: async (analysisId: number): Promise<void> => {
      const res = await authFetch(`${API_BASE}/reports/analyses/${analysisId}/csv`);
      if (!res.ok) throw new Error('Failed to download CSV');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `UrbanSense_Features_Analysis_${analysisId}.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    },
    downloadGeoJson: async (analysisId: number): Promise<void> => {
      const res = await authFetch(`${API_BASE}/reports/analyses/${analysisId}/geojson`);
      if (!res.ok) throw new Error('Failed to download GeoJSON');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `UrbanSense_Features_Analysis_${analysisId}.geojson`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
    }
  },

  users: {
    list: async (): Promise<User[]> => {
      const res = await authFetch(`${API_BASE}/users`);
      if (!res.ok) throw new Error('Failed to list users');
      return res.json();
    },
    create: async (data: any): Promise<User> => {
      const res = await authFetch(`${API_BASE}/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Failed to create user' }));
        throw new Error(err.detail || 'Failed to create user');
      }
      return res.json();
    }
  },

  benchmarks: {
    list: async (): Promise<any[]> => {
      const res = await authFetch(`${API_BASE}/benchmarks`);
      if (!res.ok) throw new Error('Failed to list benchmarks');
      return res.json();
    },
    create: async (data: any): Promise<any> => {
      const res = await authFetch(`${API_BASE}/benchmarks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) throw new Error('Failed to create benchmark');
      return res.json();
    },
    update: async (id: number, data: any): Promise<any> => {
      const res = await authFetch(`${API_BASE}/benchmarks/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) throw new Error('Failed to update benchmark');
      return res.json();
    },
    delete: async (id: number): Promise<void> => {
      const res = await authFetch(`${API_BASE}/benchmarks/${id}`, {
        method: 'DELETE'
      });
      if (!res.ok) throw new Error('Failed to delete benchmark');
    }
  }
};
