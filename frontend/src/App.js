import React, { useCallback, useEffect, useMemo, useReducer } from 'react';
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

// Initial state
const initialState = {
  currentUser: null,
  importedFiles: [],
  importedLoading: false,
  driveFiles: [],
  driveNextPageToken: null,
  driveLoading: false,
  selectedDriveIds: [],
  importing: false,
  deleting: {},
  deleteConfirm: null,
  message: null,
  error: null,
  healthStatus: null,
};

// Action types
const ActionTypes = {
  SET_USER: 'SET_USER',
  SET_IMPORTED_FILES: 'SET_IMPORTED_FILES',
  SET_IMPORTED_LOADING: 'SET_IMPORTED_LOADING',
  SET_DRIVE_FILES: 'SET_DRIVE_FILES',
  APPEND_DRIVE_FILES: 'APPEND_DRIVE_FILES',
  SET_DRIVE_NEXT_PAGE_TOKEN: 'SET_DRIVE_NEXT_PAGE_TOKEN',
  SET_DRIVE_LOADING: 'SET_DRIVE_LOADING',
  TOGGLE_DRIVE_SELECTION: 'TOGGLE_DRIVE_SELECTION',
  CLEAR_DRIVE_SELECTION: 'CLEAR_DRIVE_SELECTION',
  SET_IMPORTING: 'SET_IMPORTING',
  SET_DELETING: 'SET_DELETING',
  REMOVE_DELETING: 'REMOVE_DELETING',
  SET_DELETE_CONFIRM: 'SET_DELETE_CONFIRM',
  CLEAR_DELETE_CONFIRM: 'CLEAR_DELETE_CONFIRM',
  SET_MESSAGE: 'SET_MESSAGE',
  CLEAR_MESSAGE: 'CLEAR_MESSAGE',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
  SET_HEALTH_STATUS: 'SET_HEALTH_STATUS',
  RESET_ON_LOGOUT: 'RESET_ON_LOGOUT',
  REMOVE_DRIVE_FILES: 'REMOVE_DRIVE_FILES',
};

// Reducer
const appReducer = (state, action) => {
  switch (action.type) {
    case ActionTypes.SET_USER:
      return { ...state, currentUser: action.payload };
    
    case ActionTypes.SET_IMPORTED_FILES:
      return { ...state, importedFiles: action.payload };
    
    case ActionTypes.SET_IMPORTED_LOADING:
      return { ...state, importedLoading: action.payload };
    
    case ActionTypes.SET_DRIVE_FILES:
      return { ...state, driveFiles: action.payload };
    
    case ActionTypes.APPEND_DRIVE_FILES:
      return { ...state, driveFiles: [...state.driveFiles, ...action.payload] };
    
    case ActionTypes.SET_DRIVE_NEXT_PAGE_TOKEN:
      return { ...state, driveNextPageToken: action.payload };
    
    case ActionTypes.SET_DRIVE_LOADING:
      return { ...state, driveLoading: action.payload };
    
    case ActionTypes.TOGGLE_DRIVE_SELECTION:
      return {
        ...state,
        selectedDriveIds: state.selectedDriveIds.includes(action.payload)
          ? state.selectedDriveIds.filter((id) => id !== action.payload)
          : [...state.selectedDriveIds, action.payload],
      };
    
    case ActionTypes.CLEAR_DRIVE_SELECTION:
      return { ...state, selectedDriveIds: [] };
    
    case ActionTypes.SET_IMPORTING:
      return { ...state, importing: action.payload };
    
    case ActionTypes.SET_DELETING:
      return {
        ...state,
        deleting: { ...state.deleting, [action.payload]: true },
      };
    
    case ActionTypes.REMOVE_DELETING:
      return {
        ...state,
        deleting: Object.fromEntries(
          Object.entries(state.deleting).filter(([key]) => key !== action.payload)
        ),
      };
    
    case ActionTypes.SET_DELETE_CONFIRM:
      return { ...state, deleteConfirm: action.payload };
    
    case ActionTypes.CLEAR_DELETE_CONFIRM:
      return { ...state, deleteConfirm: null };
    
    case ActionTypes.SET_MESSAGE:
      return { ...state, message: action.payload };
    
    case ActionTypes.CLEAR_MESSAGE:
      return { ...state, message: null };
    
    case ActionTypes.SET_ERROR:
      return { ...state, error: action.payload };
    
    case ActionTypes.CLEAR_ERROR:
      return { ...state, error: null };
    
    case ActionTypes.SET_HEALTH_STATUS:
      return { ...state, healthStatus: action.payload };
    
    case ActionTypes.REMOVE_DRIVE_FILES:
      return {
        ...state,
        driveFiles: state.driveFiles.filter(
          (file) => !action.payload.includes(file.id)
        ),
      };
    
    case ActionTypes.RESET_ON_LOGOUT:
      return {
        ...initialState,
        currentUser: null,
        healthStatus: state.healthStatus,
      };
    
    default:
      return state;
  }
};

function App() {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/health`);
      const data = await response.json();
      dispatch({ type: ActionTypes.SET_HEALTH_STATUS, payload: `Backend status: ${data.status}` });
    } catch (err) {
      dispatch({ type: ActionTypes.SET_HEALTH_STATUS, payload: `Backend error: ${err.message}` });
    }
  }, []);

  const fetchImportedFiles = useCallback(async () => {
    if (!state.currentUser) {
      dispatch({ type: ActionTypes.SET_IMPORTED_FILES, payload: [] });
      return;
    }

    dispatch({ type: ActionTypes.SET_IMPORTED_LOADING, payload: true });
    try {
      const data = await filesApi.listImported();
      dispatch({ type: ActionTypes.SET_IMPORTED_FILES, payload: data });
    } catch (err) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: err.message });
    } finally {
      dispatch({ type: ActionTypes.SET_IMPORTED_LOADING, payload: false });
    }
  }, [state.currentUser]);

  useEffect(() => {
    if (state.currentUser) {
      fetchImportedFiles();
    } else {
      dispatch({ type: ActionTypes.RESET_ON_LOGOUT });
    }
  }, [state.currentUser, fetchImportedFiles]);

  const handleAuthChange = useCallback((user) => {
    dispatch({ type: ActionTypes.SET_USER, payload: user });
  }, []);

  const loadDriveFiles = useCallback(
    async ({ loadMore = false } = {}) => {
      if (!state.currentUser) {
        dispatch({ type: ActionTypes.SET_ERROR, payload: 'Please sign in to view Google Drive' });
        return;
      }
      if (loadMore && !state.driveNextPageToken) {
        return;
      }

      dispatch({ type: ActionTypes.SET_DRIVE_LOADING, payload: true });
      dispatch({ type: ActionTypes.CLEAR_ERROR });
      try {
        const data = await filesApi.listDriveFiles({
          pageSize: 20,
          pageToken: loadMore ? state.driveNextPageToken : undefined,
        });
        dispatch({ type: ActionTypes.SET_DRIVE_NEXT_PAGE_TOKEN, payload: data.next_page_token || null });
        if (loadMore) {
          dispatch({ type: ActionTypes.APPEND_DRIVE_FILES, payload: data.files });
        } else {
          dispatch({ type: ActionTypes.SET_DRIVE_FILES, payload: data.files });
        }
      } catch (err) {
        dispatch({ type: ActionTypes.SET_ERROR, payload: err.message });
      } finally {
        dispatch({ type: ActionTypes.SET_DRIVE_LOADING, payload: false });
      }
    },
    [state.currentUser, state.driveNextPageToken]
  );

  const toggleDriveSelection = useCallback((fileId) => {
    dispatch({ type: ActionTypes.TOGGLE_DRIVE_SELECTION, payload: fileId });
  }, []);

  const handleImportSelected = useCallback(async () => {
    if (!state.selectedDriveIds.length) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: 'Please select at least one file to import' });
      return;
    }
    dispatch({ type: ActionTypes.SET_IMPORTING, payload: true });
    dispatch({ type: ActionTypes.CLEAR_MESSAGE });
    dispatch({ type: ActionTypes.CLEAR_ERROR });
    try {
      const result = await filesApi.importFiles(state.selectedDriveIds);
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
        dispatch({ type: ActionTypes.SET_ERROR, payload: `Import errors: ${errorDetails}` });
      } else {
        dispatch({ type: ActionTypes.SET_MESSAGE, payload: summaryParts.join(' · ') || 'Import completed' });
      }

      if (importedCount) {
        await fetchImportedFiles();
        // Remove imported files from Drive list
        const importedDriveIds = result.imported.map(f => f.drive_file_id);
        dispatch({ type: ActionTypes.REMOVE_DRIVE_FILES, payload: importedDriveIds });
      }
      dispatch({ type: ActionTypes.CLEAR_DRIVE_SELECTION });
    } catch (err) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: err.message });
    } finally {
      dispatch({ type: ActionTypes.SET_IMPORTING, payload: false });
    }
  }, [state.selectedDriveIds, fetchImportedFiles]);

  const handleDeleteClick = useCallback((fileId, fileName) => {
    dispatch({ type: ActionTypes.SET_DELETE_CONFIRM, payload: { fileId, fileName } });
  }, []);

  const handleDeleteConfirm = useCallback(async () => {
    if (!state.deleteConfirm) return;

    const { fileId } = state.deleteConfirm;
    dispatch({ type: ActionTypes.SET_DELETING, payload: fileId });
    dispatch({ type: ActionTypes.CLEAR_ERROR });
    dispatch({ type: ActionTypes.CLEAR_DELETE_CONFIRM });
    
    try {
      await filesApi.deleteFile(fileId);
      dispatch({ type: ActionTypes.SET_MESSAGE, payload: 'File deleted successfully' });
      await fetchImportedFiles();
    } catch (err) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: `Error deleting file: ${err.message}` });
    } finally {
      dispatch({ type: ActionTypes.REMOVE_DELETING, payload: fileId });
    }
  }, [state.deleteConfirm, fetchImportedFiles]);

  const handleDeleteCancel = useCallback(() => {
    dispatch({ type: ActionTypes.CLEAR_DELETE_CONFIRM });
  }, []);

  const isDriveSelectionDisabled = useMemo(
    () => !state.currentUser || state.driveLoading || state.importing,
    [state.currentUser, state.driveLoading, state.importing]
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
            {state.healthStatus && <span className="hint-text">{state.healthStatus}</span>}
          </div>
        </div>
        <Auth onAuthChange={handleAuthChange} />
      </header>

      {!state.currentUser ? (
        <div className="unauthorized-placeholder">
          <p>Sign in with Google to view and import files.</p>
        </div>
      ) : (
        <main className="app-content">
          {(state.message || state.error) && (
            <div className="alerts">
              {state.message && (
                <div className="alert alert-success" onClick={() => dispatch({ type: ActionTypes.CLEAR_MESSAGE })}>
                  {state.message}
                </div>
              )}
              {state.error && (
                <div className="alert alert-error" onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })}>
                  {state.error}
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
                  disabled={state.driveLoading}
                >
                  {state.driveLoading ? 'Loading...' : 'Load files'}
                </button>
                {state.driveNextPageToken && (
                  <button
                    onClick={() => loadDriveFiles({ loadMore: true })}
                    className="secondary-button"
                    disabled={state.driveLoading}
                  >
                    Load more
                  </button>
                )}
                <button
                  onClick={handleImportSelected}
                  className="accent-button"
                  disabled={isDriveSelectionDisabled || !state.selectedDriveIds.length}
                >
                  {state.importing ? 'Importing...' : `Import (${state.selectedDriveIds.length})`}
                </button>
              </div>
            </div>

            <div className="drive-list">
              {state.driveFiles.length === 0 && !state.driveLoading ? (
                <p className="muted-text">Google Drive files not loaded. Click "Load files".</p>
              ) : (
                <ul>
                  {state.driveFiles.map((file) => {
                    const isSelected = state.selectedDriveIds.includes(file.id);
                    const isFolder = file.is_folder || false;
                    const isGoogleApp = file.mime_type && file.mime_type.startsWith('application/vnd.google-apps.');
                    const canImport = !isFolder && !isGoogleApp;
                    return (
                      <li key={file.id} className={isSelected ? 'drive-item selected' : 'drive-item'}>
                        <label>
                          <input
                            type="checkbox"
                            checked={isSelected}
                            disabled={isDriveSelectionDisabled || !canImport}
                            onChange={() => toggleDriveSelection(file.id)}
                          />
                          <span className="drive-item-name">
                            {isFolder && '📁 '}
                            {file.name}
                            {isFolder && ' (Folder)'}
                            {isGoogleApp && !isFolder && ' (Google App)'}
                          </span>
                        </label>
                        <div className="drive-item-meta">
                          <span>{isFolder ? 'Folder' : (file.mime_type || '—')}</span>
                          <span>{isFolder || isGoogleApp ? '—' : (file.size_bytes ? `${file.size_bytes.toLocaleString()} bytes` : 'Size unknown')}</span>
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
              <span className="badge">{state.importedFiles.length}</span>
            </div>
            {state.importedLoading ? (
              <p className="muted-text">Loading...</p>
            ) : state.importedFiles.length === 0 ? (
              <p className="muted-text">No imported files yet.</p>
            ) : (
              <ul className="imported-list">
                {state.importedFiles.map((file) => (
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
                        disabled={state.deleting[file.id]}
                      >
                        {state.deleting[file.id] ? 'Deleting...' : 'Delete'}
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
      {state.deleteConfirm && (
        <div className="modal-overlay" onClick={handleDeleteCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Confirm Deletion</h3>
            <p>Are you sure you want to delete the file <strong>"{state.deleteConfirm.fileName}"</strong>?</p>
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

