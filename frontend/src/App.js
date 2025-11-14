import React, { useCallback, useEffect, useMemo, useState } from 'react';
import './App.css';
import Auth from './components/Auth';
import { filesApi } from './api/files';

// Use relative path in production (same domain), absolute URL in development
const getApiUrl = () => {
  if (process.env.REACT_APP_API_URL) {
    return process.env.REACT_APP_API_URL;
  }
  // In production, if served from same domain, use relative path
  if (process.env.NODE_ENV === 'production') {
    return '';
  }
  return 'http://localhost:8000';
};

const API_URL = getApiUrl();

function App() {
  const [currentUser, setCurrentUser] = useState(null);
  const [importedFiles, setImportedFiles] = useState([]);
  const [importedLoading, setImportedLoading] = useState(false);
  const [driveFiles, setDriveFiles] = useState([]);
  const [driveNextPageToken, setDriveNextPageToken] = useState(null);
  const [driveLoading, setDriveLoading] = useState(false);
  const [selectedDriveIds, setSelectedDriveIds] = useState([]);
  const [importing, setImporting] = useState(false);
  const [deleting, setDeleting] = useState({});
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      const data = await response.json();
      setHealthStatus(`Backend status: ${data.status}`);
    } catch (err) {
      setHealthStatus(`Backend error: ${err.message}`);
    }
  }, []);

  const fetchImportedFiles = useCallback(async () => {
    if (!currentUser) {
      setImportedFiles([]);
      return;
    }

    setImportedLoading(true);
    try {
      const data = await filesApi.listImported();
      setImportedFiles(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setImportedLoading(false);
    }
  }, [currentUser]);

  useEffect(() => {
    if (currentUser) {
      fetchImportedFiles();
    } else {
      setImportedFiles([]);
      setDriveFiles([]);
      setSelectedDriveIds([]);
      setDriveNextPageToken(null);
    }
  }, [currentUser, fetchImportedFiles]);

  const handleAuthChange = useCallback((user) => {
    setCurrentUser(user);
  }, []);

  const loadDriveFiles = useCallback(
    async ({ loadMore = false } = {}) => {
      if (!currentUser) {
        setError('Please sign in to view Google Drive');
        return;
      }
      if (loadMore && !driveNextPageToken) {
        return;
      }

      setDriveLoading(true);
      setError(null);
      try {
        const data = await filesApi.listDriveFiles({
          pageSize: 20,
          pageToken: loadMore ? driveNextPageToken : undefined,
        });
        setDriveNextPageToken(data.next_page_token || null);
        setDriveFiles((prev) => (loadMore ? [...prev, ...data.files] : data.files));
      } catch (err) {
        setError(err.message);
      } finally {
        setDriveLoading(false);
      }
    },
    [currentUser, driveNextPageToken]
  );

  const toggleDriveSelection = useCallback((fileId) => {
    setSelectedDriveIds((prev) =>
      prev.includes(fileId) ? prev.filter((id) => id !== fileId) : [...prev, fileId]
    );
  }, []);

  const handleImportSelected = useCallback(async () => {
    if (!selectedDriveIds.length) {
      setError('Please select at least one file to import');
      return;
    }
    setImporting(true);
    setMessage(null);
    setError(null);
    try {
      const result = await filesApi.importFiles(selectedDriveIds);
      const importedCount = result.imported.length;
      const skippedCount = result.skipped.length;
      const failedCount = result.failed.length;

      const summaryParts = [];
      if (importedCount) summaryParts.push(`Imported: ${importedCount}`);
      if (skippedCount) summaryParts.push(`Skipped: ${skippedCount}`);
      if (failedCount) summaryParts.push(`Failed: ${failedCount}`);
      
      // Show error details if any
      if (result.failed && result.failed.length > 0) {
        const errorDetails = result.failed.map(f => `${f.file_id}: ${f.error}`).join('; ');
        setError(`Import errors: ${errorDetails}`);
      } else {
        setMessage(summaryParts.join(' · ') || 'Import completed');
      }

      if (importedCount) {
        await fetchImportedFiles();
        // Remove imported files from Drive list
        setDriveFiles((prev) => prev.filter((file) => !result.imported.find((f) => f.drive_file_id === file.id)));
      }
      setSelectedDriveIds([]);
    } catch (err) {
      setError(err.message);
    } finally {
      setImporting(false);
    }
  }, [selectedDriveIds, fetchImportedFiles]);

  const handleDeleteClick = useCallback((fileId, fileName) => {
    setDeleteConfirm({ fileId, fileName });
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!deleteConfirm) return;

    const { fileId } = deleteConfirm;
    setDeleting((prev) => ({ ...prev, [fileId]: true }));
    setError(null);
    setDeleteConfirm(null);
    
    try {
      await filesApi.deleteFile(fileId);
      setMessage('File deleted successfully');
      await fetchImportedFiles();
    } catch (err) {
      setError(`Error deleting file: ${err.message}`);
    } finally {
      setDeleting((prev) => {
        const next = { ...prev };
        delete next[fileId];
        return next;
      });
    }
  }, [deleteConfirm, fetchImportedFiles]);

  const handleDeleteCancel = useCallback(() => {
    setDeleteConfirm(null);
  }, []);

  const isDriveSelectionDisabled = useMemo(
    () => !currentUser || driveLoading || importing,
    [currentUser, driveLoading, importing]
  );

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-top">
          <div>
            <h1 className="app-title">Data Room MVP</h1>
            <p className="app-subtitle">Import and manage files from Google Drive</p>
          </div>
          <div className="app-actions">
            <button onClick={checkHealth} className="secondary-button">
              Check backend
            </button>
            {healthStatus && <span className="hint-text">{healthStatus}</span>}
          </div>
        </div>
        <Auth onAuthChange={handleAuthChange} />
      </header>

      {!currentUser ? (
        <div className="unauthorized-placeholder">
          <p>Sign in with Google to view and import files.</p>
        </div>
      ) : (
        <main className="app-content">
          {(message || error) && (
            <div className="alerts">
              {message && (
                <div className="alert alert-success" onClick={() => setMessage(null)}>
                  {message}
                </div>
              )}
              {error && (
                <div className="alert alert-error" onClick={() => setError(null)}>
                  {error}
                </div>
              )}
            </div>
          )}

          <section className="drive-section">
            <div className="section-header">
              <h2>Google Drive</h2>
              <div className="section-actions">
                <button
                  onClick={() => loadDriveFiles({ loadMore: false })}
                  className="primary-button"
                  disabled={driveLoading}
                >
                  {driveLoading ? 'Loading...' : 'Load files'}
                </button>
                {driveNextPageToken && (
                  <button
                    onClick={() => loadDriveFiles({ loadMore: true })}
                    className="secondary-button"
                    disabled={driveLoading}
                  >
                    Load more
                  </button>
                )}
                <button
                  onClick={handleImportSelected}
                  className="accent-button"
                  disabled={isDriveSelectionDisabled || !selectedDriveIds.length}
                >
                  {importing ? 'Importing...' : `Import (${selectedDriveIds.length})`}
                </button>
              </div>
            </div>

            <div className="drive-list">
              {driveFiles.length === 0 && !driveLoading ? (
                <p className="muted-text">Google Drive files not loaded. Click "Load files".</p>
              ) : (
                <ul>
                  {driveFiles.map((file) => {
                    const isSelected = selectedDriveIds.includes(file.id);
                    return (
                      <li key={file.id} className={isSelected ? 'drive-item selected' : 'drive-item'}>
                        <label>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={isDriveSelectionDisabled}
                            onChange={() => toggleDriveSelection(file.id)}
                          />
                          <span className="drive-item-name">{file.name}</span>
                        </label>
                        <div className="drive-item-meta">
                          <span>{file.mime_type || '—'}</span>
                          <span>{file.size_bytes ? `${file.size_bytes.toLocaleString()} bytes` : 'Size unknown'}</span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </section>

          <section className="imported-section">
            <div className="section-header">
              <h2>Imported Files</h2>
              <span className="badge">{importedFiles.length}</span>
            </div>
            {importedLoading ? (
              <p className="muted-text">Loading...</p>
            ) : importedFiles.length === 0 ? (
              <p className="muted-text">No imported files yet.</p>
            ) : (
              <ul className="imported-list">
                {importedFiles.map((file) => (
                  <li key={file.id} className="imported-item">
                    <div>
                      <div className="imported-name">{file.original_name}</div>
                      <div className="imported-meta">
                        <span>{file.mime_type || 'Type unknown'}</span>
                        <span>{file.size_bytes.toLocaleString()} bytes</span>
                      </div>
                    </div>
                    <div className="imported-actions">
                      <a
                        className="action-button action-button-view"
                        href={filesApi.getFileViewUrl(file.id)}
                        target="_blank"
                        rel="noreferrer"
                      >
                        View
                      </a>
                      {file.web_view_link && (
                        <a
                          className="action-button action-button-drive"
                          href={file.web_view_link}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Open in Google Drive
                        </a>
                      )}
                      <button
                        className="action-button action-button-delete"
                        onClick={() => handleDeleteClick(file.id, file.original_name)}
                        disabled={deleting[file.id]}
                      >
                        {deleting[file.id] ? 'Deleting...' : 'Delete'}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </main>
      )}

      {/* Delete confirmation modal */}
      {deleteConfirm && (
        <div className="modal-overlay" onClick={handleDeleteCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm Deletion</h3>
            <p>Are you sure you want to delete the file <strong>"{deleteConfirm.fileName}"</strong>?</p>
            <p className="modal-warning">This action cannot be undone.</p>
            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={handleDeleteCancel}
              >
                Cancel
              </button>
              <button
                className="danger-button"
                onClick={handleDeleteConfirm}
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

