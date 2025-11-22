import { apiClient } from './client';

export const filesApi = {
  async listImported() {
    return apiClient.get('/files');
  },

  async listDriveFiles({ pageSize = 20, pageToken, parentFolderId } = {}) {
    const params = new URLSearchParams();
    if (pageSize) params.append('page_size', pageSize);
    if (pageToken) params.append('page_token', pageToken);
    // Only add parent_folder_id if it's explicitly provided and not null
    if (parentFolderId !== null && parentFolderId !== undefined) {
      params.append('parent_folder_id', parentFolderId);
    }
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

  async uploadToDrive(file, parentFolderId = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (parentFolderId) {
      formData.append('parent_folder_id', parentFolderId);
    }
    // Don't set Content-Type manually - browser will set it with boundary
    return apiClient.post('/files/drive/upload', formData);
  },

  async createFolder(folderName, parentFolderId = null) {
    const payload = { name: folderName };
    if (parentFolderId) {
      payload.parent_folder_id = parentFolderId;
    }
    return apiClient.post('/files/drive/folder', payload);
  },
};

