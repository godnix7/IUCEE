const API_BASE_URL = 'http://localhost:8000/api/v1';

export const api = {
  projects: {
    create: async (data: { name: string, description: string, root_path: string, classes: any[] }) => {
      const res = await fetch(`${API_BASE_URL}/projects/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    list: async () => {
      const res = await fetch(`${API_BASE_URL}/projects/`);
      if (!res.ok) throw new Error('Failed to fetch projects');
      return res.json();
    },
    get: async (id: number) => {
      const res = await fetch(`${API_BASE_URL}/projects/${id}`);
      if (!res.ok) throw new Error('Project not found');
      return res.json();
    },
    selectFolder: async () => {
      const res = await fetch(`${API_BASE_URL}/projects/select-folder`);
      if (!res.ok) throw new Error('Failed to select folder');
      return res.json();
    },
    cleanup: async (projectId: number, target: string, deleteSourceFiles: boolean) => {
      const res = await fetch(`${API_BASE_URL}/projects/${projectId}/cleanup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, delete_source_files: deleteSourceFiles })
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }
  },
  labeling: {
    autoLabelAll: async (projectId: number, modelName?: string) => {
      const res = await fetch(`${API_BASE_URL}/labeling/${projectId}/auto-label`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName || "nvidia/segformer-b3-finetuned-ade-512-512" })
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    pause: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/labeling/${projectId}/pause`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    resume: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/labeling/${projectId}/resume`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    stop: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/labeling/${projectId}/stop`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    },
    getQueueStatus: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/labeling/${projectId}/queue-status`);
      if (!res.ok) throw new Error('Failed to fetch queue status');
      return res.json();
    }
  },
  review: {
    getQueue: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/review-queue`);
      if (!res.ok) throw new Error('Failed to fetch review queue');
      return res.json();
    },
    getAnnotations: async (projectId: number, imageId: number) => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/images/${imageId}/annotations`);
      if (!res.ok) throw new Error('Failed to fetch annotations');
      return res.json();
    },
    markViewed: async (projectId: number, imageId: number, notes = '') => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/images/${imageId}/mark-viewed`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reviewer: 'manual_review', notes })
      });
      if (!res.ok) throw new Error('Failed to mark viewed');
      return res.json();
    },
    correct: async (projectId: number, imageId: number, annotations: any[], notes = '') => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/images/${imageId}/correct`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ annotations, reviewer: 'manual_review', notes })
      });
      if (!res.ok) throw new Error('Failed to save corrections');
      return res.json();
    },
    forcePopulate: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/force-populate`, { method: 'POST' });
      if (!res.ok) throw new Error('Failed to force populate');
      return res.json();
    },
    getDebugImages: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/debug-images`);
      if (!res.ok) throw new Error('Failed to fetch debug images');
      return res.json();
    },
    reject: async (projectId: number, imageId: number, reason: string, notes: string) => {
      const res = await fetch(`${API_BASE_URL}/review/${projectId}/images/${imageId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason, notes })
      });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }
  },
  dashboard: {
    getStats: async (projectId: number) => {
      const res = await fetch(`${API_BASE_URL}/dashboard/${projectId}/stats`);
      if (!res.ok) throw new Error('Failed to fetch stats');
      return res.json();
    }
  },
  exports: {
    generate: async (projectId: number, mode: string) => {
      const res = await fetch(`${API_BASE_URL}/exports/${projectId}/export?mode=${mode}`, { method: 'POST' });
      if (!res.ok) throw new Error(await res.text());
      return res.json();
    }
  }
};
