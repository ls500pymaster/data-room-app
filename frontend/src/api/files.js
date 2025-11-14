import { apiClient } from './client';

export const filesApi = {
  async listImported() {
    return apiClient.get('/files');
  },

  async listDriveFiles({ pageSize = 20, pageToken } = {}) {
    const params = new URLSearchParams();
    if (pageSize) params.append('page_size', pageSize);
    if (pageToken) params.append('page_token', pageToken);
    const query = params.toString();
    const endpoint = query ? `/files/drive?${query}` : '/files/drive';
    return apiClient.get(endpoint);
  },

  async importFiles(fileIds) {
    return apiClient.post('/files/import', { file_ids: fileIds });
  },

  getFileViewUrl(fileId) {
    // Use relative path in production, absolute URL in development
    const apiUrl = process.env.REACT_APP_API_URL || 
      (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000');
    return `${apiUrl}/api/files/${fileId}/view`;
  },

  async deleteFile(fileId) {
    return apiClient.delete(`/files/${fileId}`);
  },
};

