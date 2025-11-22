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
  checkingHealth: false,
  uploadingToDrive: false,
  dragOver: false,
  createFolderModal: null,
  creatingFolder: false,
  currentFolderId: null,
  folderNavigationStack: [],
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
  SET_CHECKING_HEALTH: 'SET_CHECKING_HEALTH',
  RESET_ON_LOGOUT: 'RESET_ON_LOGOUT',
  REMOVE_DRIVE_FILES: 'REMOVE_DRIVE_FILES',
  SET_UPLOADING_TO_DRIVE: 'SET_UPLOADING_TO_DRIVE',
  SET_DRAG_OVER: 'SET_DRAG_OVER',
  SET_CREATE_FOLDER_MODAL: 'SET_CREATE_FOLDER_MODAL',
  CLEAR_CREATE_FOLDER_MODAL: 'CLEAR_CREATE_FOLDER_MODAL',
  SET_CREATING_FOLDER: 'SET_CREATING_FOLDER',
  SET_CURRENT_FOLDER: 'SET_CURRENT_FOLDER',
  NAVIGATE_TO_FOLDER: 'NAVIGATE_TO_FOLDER',
  NAVIGATE_BACK: 'NAVIGATE_BACK',
  RESET_FOLDER_NAVIGATION: 'RESET_FOLDER_NAVIGATION',
  SET_FOLDER_NAVIGATION_STACK: 'SET_FOLDER_NAVIGATION_STACK',
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
      return { ...state, healthStatus: action.payload, checkingHealth: false };
    
    case ActionTypes.SET_CHECKING_HEALTH:
      return { ...state, checkingHealth: action.payload };
    
    case ActionTypes.REMOVE_DRIVE_FILES:
      return {
        ...state,
        driveFiles: state.driveFiles.filter(
          (file) => !action.payload.includes(file.id)
        ),
      };
    
    case ActionTypes.SET_UPLOADING_TO_DRIVE:
      return { ...state, uploadingToDrive: action.payload };
    
    case ActionTypes.SET_DRAG_OVER:
      return { ...state, dragOver: action.payload };
    
    case ActionTypes.SET_CREATE_FOLDER_MODAL:
      return { ...state, createFolderModal: action.payload };
    
    case ActionTypes.CLEAR_CREATE_FOLDER_MODAL:
      return { ...state, createFolderModal: null };
    
    case ActionTypes.SET_CREATING_FOLDER:
      return { ...state, creatingFolder: action.payload };
    
    case ActionTypes.SET_CURRENT_FOLDER:
      return { ...state, currentFolderId: action.payload };
    
    case ActionTypes.NAVIGATE_TO_FOLDER:
      return {
        ...state,
        currentFolderId: action.payload.id,
        folderNavigationStack: [...state.folderNavigationStack, action.payload],
      };
    
    case ActionTypes.NAVIGATE_BACK:
      const newStack = state.folderNavigationStack.slice(0, -1);
      const newCurrentFolderId = newStack.length > 0 ? newStack[newStack.length - 1].id : null;
      return {
        ...state,
        folderNavigationStack: newStack,
        currentFolderId: newCurrentFolderId,
      };
    
    case ActionTypes.RESET_FOLDER_NAVIGATION:
      return {
        ...state,
        currentFolderId: null,
        folderNavigationStack: [],
      };
    
    case ActionTypes.SET_FOLDER_NAVIGATION_STACK:
      return {
        ...state,
        folderNavigationStack: action.payload,
      };
    
    case ActionTypes.RESET_ON_LOGOUT:
      return {
        ...initialState,
        currentUser: null,
        healthStatus: state.healthStatus,
        checkingHealth: false,
      };
    
    default:
      return state;
  }
};

// Helper function to get Font Awesome icon class based on MIME type
const getFileIcon = (mimeType) => {
  if (!mimeType) {
    return 'fa-file';
  }

  // Images
  if (mimeType.startsWith('image/')) {
    return 'fa-file-image';
  }

  // Videos
  if (mimeType.startsWith('video/')) {
    return 'fa-file-video';
  }

  // Audio
  if (mimeType.startsWith('audio/')) {
    return 'fa-file-audio';
  }

  // PDF
  if (mimeType === 'application/pdf') {
    return 'fa-file-pdf';
  }

  // Archives
  if (
    mimeType === 'application/zip' ||
    mimeType === 'application/x-zip-compressed' ||
    mimeType === 'application/x-rar-compressed' ||
    mimeType === 'application/x-7z-compressed' ||
    mimeType === 'application/x-tar' ||
    mimeType === 'application/gzip'
  ) {
    return 'fa-file-zipper';
  }

  // Text files
  if (mimeType.startsWith('text/')) {
    if (mimeType === 'text/markdown' || mimeType === 'text/x-markdown') {
      return 'fa-file-code';
    }
    if (mimeType === 'text/csv') {
      return 'fa-file-csv';
    }
    return 'fa-file-lines';
  }

  // Code files
  if (
    mimeType === 'application/json' ||
    mimeType === 'application/javascript' ||
    mimeType === 'text/javascript' ||
    mimeType === 'application/xml' ||
    mimeType === 'text/xml'
  ) {
    return 'fa-file-code';
  }

  // Word documents
  if (
    mimeType === 'application/msword' ||
    mimeType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
  ) {
    return 'fa-file-word';
  }

  // Excel
  if (
    mimeType === 'application/vnd.ms-excel' ||
    mimeType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ) {
    return 'fa-file-excel';
  }

  // PowerPoint
  if (
    mimeType === 'application/vnd.ms-powerpoint' ||
    mimeType === 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
  ) {
    return 'fa-file-powerpoint';
  }

  // Default
  return 'fa-file';
};

function App() {
  const [state, dispatch] = useReducer(appReducer, initialState);

  const checkHealth = useCallback(async () => {
    dispatch({ type: ActionTypes.SET_CHECKING_HEALTH, payload: true });
    dispatch({ type: ActionTypes.SET_HEALTH_STATUS, payload: null });
    try {
      const response = await fetch(`${API_URL}/api/health`);
      const data = await response.json();
      dispatch({ type: ActionTypes.SET_HEALTH_STATUS, payload: `Backend status: ${data.status}` });
    } catch (err) {
      dispatch({ type: ActionTypes.SET_HEALTH_STATUS, payload: `Backend error: ${err.message}` });
    } finally {
      dispatch({ type: ActionTypes.SET_CHECKING_HEALTH, payload: false });
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
    async ({ loadMore = false, folderId = undefined } = {}) => {
      if (!state.currentUser) {
        dispatch({ type: ActionTypes.SET_ERROR, payload: 'Please sign in to view Google Drive' });
        return Promise.reject(new Error('User not authenticated'));
      }
      
      // Check if Google Drive is connected
      if (!state.currentUser.has_google_drive) {
        dispatch({ 
          type: ActionTypes.SET_ERROR, 
          payload: 'Google Drive is not connected. Please sign in with Google to access Google Drive files.' 
        });
        return Promise.reject(new Error('Google Drive not connected'));
      }
      
      if (loadMore && !state.driveNextPageToken) {
        return Promise.reject(new Error('No more pages'));
      }
      // Block new requests during loading (except loadMore)
      if (!loadMore && state.driveLoading) {
        return Promise.reject(new Error('Already loading'));
      }

      dispatch({ type: ActionTypes.SET_DRIVE_LOADING, payload: true });
      dispatch({ type: ActionTypes.CLEAR_ERROR });
      try {
        // If folderId is explicitly provided (including null for root), use it
        // If not provided (undefined), use currentFolderId from state
        const parentFolderId = folderId !== undefined ? folderId : (state.currentFolderId || null);
        const data = await filesApi.listDriveFiles({
          pageSize: 20,
          pageToken: loadMore ? state.driveNextPageToken : undefined,
          parentFolderId: parentFolderId,
        });
        dispatch({ type: ActionTypes.SET_DRIVE_NEXT_PAGE_TOKEN, payload: data.next_page_token || null });
        if (loadMore) {
          dispatch({ type: ActionTypes.APPEND_DRIVE_FILES, payload: data.files });
        } else {
          dispatch({ type: ActionTypes.SET_DRIVE_FILES, payload: data.files });
        }
        return data;
      } catch (err) {
        const errorMsg = err.message || 'Unknown error';
        // Handle Google Drive not connected error
        if (errorMsg.includes('403') || errorMsg.includes('Google Drive is not connected') || errorMsg.includes('not connected')) {
          dispatch({ 
            type: ActionTypes.SET_ERROR, 
            payload: 'Google Drive is not connected. Please sign in with Google to access Google Drive files.' 
          });
        } else {
          dispatch({ type: ActionTypes.SET_ERROR, payload: errorMsg });
        }
        throw err;
      } finally {
        dispatch({ type: ActionTypes.SET_DRIVE_LOADING, payload: false });
      }
    },
    [state.currentUser, state.driveNextPageToken, state.currentFolderId, state.driveLoading]
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

      // Build detailed messages
      const messages = [];
      const errors = [];
      
      if (importedCount) {
        messages.push(`Imported: ${importedCount} file${importedCount > 1 ? 's' : ''}`);
      }
      
      if (skippedCount > 0) {
        // Group skipped files by reason
        const alreadyImported = result.skipped.filter(s => s.reason === 'already_imported');
        const unsupported = result.skipped.filter(s => s.reason === 'unsupported_type');
        
        if (alreadyImported.length > 0) {
          const fileNames = alreadyImported
            .map(s => s.file_name || s.file_id)
            .slice(0, 3)
            .join(', ');
          const more = alreadyImported.length > 3 ? ` and ${alreadyImported.length - 3} more` : '';
          messages.push(`Already imported: ${fileNames}${more}`);
        }
        
        if (unsupported.length > 0) {
          const fileNames = unsupported
            .map(s => s.file_name || s.file_id)
            .slice(0, 3)
            .join(', ');
          const more = unsupported.length > 3 ? ` and ${unsupported.length - 3} more` : '';
          messages.push(`Unsupported type: ${fileNames}${more}`);
        }
      }
      
      if (failedCount > 0) {
        const errorDetails = result.failed.map(f => {
          const fileName = state.driveFiles.find(df => df.id === f.file_id)?.name || f.file_id;
          return `${fileName}: ${f.error}`;
        }).join('; ');
        errors.push(`Failed: ${errorDetails}`);
      }
      
      // Show messages
      if (errors.length > 0) {
        dispatch({ type: ActionTypes.SET_ERROR, payload: errors.join(' ') });
      } else if (messages.length > 0) {
        dispatch({ type: ActionTypes.SET_MESSAGE, payload: messages.join(' • ') });
      } else {
        dispatch({ type: ActionTypes.SET_MESSAGE, payload: 'Import completed' });
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
    () => !state.currentUser || state.driveLoading || state.importing || state.uploadingToDrive,
    [state.currentUser, state.driveLoading, state.importing, state.uploadingToDrive]
  );

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragEnter = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!state.uploadingToDrive) {
      dispatch({ type: ActionTypes.SET_DRAG_OVER, payload: true });
    }
  }, [state.uploadingToDrive]);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only remove drag over if we're leaving the container (not entering a child)
    if (!e.currentTarget.contains(e.relatedTarget)) {
      dispatch({ type: ActionTypes.SET_DRAG_OVER, payload: false });
    }
  }, []);

  const handleDrop = useCallback(async (e) => {
    e.preventDefault();
    e.stopPropagation();
    dispatch({ type: ActionTypes.SET_DRAG_OVER, payload: false });

    const files = Array.from(e.dataTransfer.files);
    if (files.length === 0) return;

    if (!state.currentUser) {
      dispatch({ type: ActionTypes.SET_ERROR, payload: 'Please sign in to upload files to Google Drive' });
      return;
    }

    // Check if Google Drive is connected
    if (!state.currentUser.has_google_drive) {
      dispatch({ 
        type: ActionTypes.SET_ERROR, 
        payload: 'Google Drive is not connected. Please sign in with Google to upload files to Google Drive.' 
      });
      return;
    }

    dispatch({ type: ActionTypes.SET_UPLOADING_TO_DRIVE, payload: true });
    dispatch({ type: ActionTypes.CLEAR_ERROR });
    dispatch({ type: ActionTypes.CLEAR_MESSAGE });

    const uploadPromises = files.map(async (file) => {
      try {
        await filesApi.uploadToDrive(file, state.currentFolderId || null);
        return { success: true, fileName: file.name };
      } catch (err) {
        // Check if error is about Google Drive not being connected or no upload permission
        const errorMsg = err.message || '';
        if (errorMsg.includes('403') || errorMsg.includes('No permission') || errorMsg.includes('not connected') || errorMsg.includes('grant upload permissions')) {
          return { 
            success: false, 
            fileName: file.name, 
            error: 'No permission to upload files. Please sign in again with Google to grant upload permissions.',
            isGoogleNotConnected: true 
          };
        }
        return { success: false, fileName: file.name, error: errorMsg };
      }
    });

    const results = await Promise.all(uploadPromises);
    const successful = results.filter(r => r.success);
    const failed = results.filter(r => !r.success);
    const googleNotConnected = failed.some(r => r.isGoogleNotConnected);

    if (successful.length > 0) {
      const count = successful.length;
      dispatch({
        type: ActionTypes.SET_MESSAGE,
        payload: `${count} file${count > 1 ? 's' : ''} uploaded successfully to Google Drive`,
      });
      // Reload Drive files list
      await loadDriveFiles({ loadMore: false });
    }

    if (failed.length > 0) {
      // Special handling for Google Drive not connected or no upload permission
      if (googleNotConnected) {
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: 'No permission to upload files to Google Drive. Please sign in again with Google to grant upload permissions.',
        });
      } else {
        const errorMessages = failed.map(f => `${f.fileName}: ${f.error}`).join('; ');
        dispatch({
          type: ActionTypes.SET_ERROR,
          payload: `Failed to upload ${failed.length} file${failed.length > 1 ? 's' : ''}: ${errorMessages}`,
        });
      }
    }

    dispatch({ type: ActionTypes.SET_UPLOADING_TO_DRIVE, payload: false });
  }, [state.currentUser, loadDriveFiles]);

  const handleCreateFolderClick = useCallback(() => {
    if (!state.currentUser?.has_google_drive) {
      dispatch({ 
        type: ActionTypes.SET_ERROR, 
        payload: 'Google Drive is not connected. Please sign in with Google.' 
      });
      return;
    }
    dispatch({ 
      type: ActionTypes.SET_CREATE_FOLDER_MODAL, 
      payload: { isOpen: true, folderName: '' } 
    });
  }, [state.currentUser]);

  const handleCreateFolderCancel = useCallback(() => {
    dispatch({ type: ActionTypes.CLEAR_CREATE_FOLDER_MODAL });
  }, []);

  const handleCreateFolderNameChange = useCallback((e) => {
    dispatch({ 
      type: ActionTypes.SET_CREATE_FOLDER_MODAL, 
      payload: { 
        isOpen: true, 
        folderName: e.target.value 
      } 
    });
  }, []);

  const handleCreateFolderConfirm = useCallback(async () => {
    const folderName = state.createFolderModal?.folderName?.trim();
    
    if (!folderName || folderName.length === 0) {
      dispatch({ 
        type: ActionTypes.SET_ERROR, 
        payload: 'Folder name cannot be empty' 
      });
      return;
    }
    
    if (folderName.length > 255) {
      dispatch({ 
        type: ActionTypes.SET_ERROR, 
        payload: 'Folder name is too long (max 255 characters)' 
      });
      return;
    }
    
    // Validate forbidden characters
    const forbiddenChars = /[\/\\?*:|"<>]/;
    if (forbiddenChars.test(folderName)) {
      dispatch({ 
        type: ActionTypes.SET_ERROR, 
        payload: 'Folder name contains invalid characters' 
      });
      return;
    }
    
    dispatch({ type: ActionTypes.SET_CREATING_FOLDER, payload: true });
    dispatch({ type: ActionTypes.CLEAR_ERROR });
    dispatch({ type: ActionTypes.CLEAR_MESSAGE });
    
    try {
      const result = await filesApi.createFolder(folderName, state.currentFolderId || null);
      dispatch({ 
        type: ActionTypes.SET_MESSAGE, 
        payload: `Folder "${result.name}" created successfully` 
      });
      dispatch({ type: ActionTypes.CLEAR_CREATE_FOLDER_MODAL });
      await loadDriveFiles({ loadMore: false });
    } catch (err) {
      const errorMsg = err.message || 'Unknown error';
      if (errorMsg.includes('403') || errorMsg.includes('No permission')) {
        dispatch({ 
          type: ActionTypes.SET_ERROR, 
          payload: 'No permission to create folders. Please sign in again with Google to grant upload permissions.' 
        });
      } else {
        dispatch({ 
          type: ActionTypes.SET_ERROR, 
          payload: `Failed to create folder: ${errorMsg}` 
        });
      }
    } finally {
      dispatch({ type: ActionTypes.SET_CREATING_FOLDER, payload: false });
    }
  }, [state.createFolderModal, state.currentFolderId, loadDriveFiles]);

  const handleFolderClick = useCallback((folderId, folderName) => {
    // Block clicks during loading (debouncing/throttling)
    if (state.driveLoading) {
      return;
    }
    
    // Update navigation only after successful load
    loadDriveFiles({ loadMore: false, folderId }).then(() => {
      dispatch({ 
        type: ActionTypes.NAVIGATE_TO_FOLDER, 
        payload: { id: folderId, name: folderName } 
      });
    }).catch(() => {
      // On error, navigation is not updated
    });
  }, [loadDriveFiles, state.driveLoading]);

  const handleNavigateBack = useCallback(() => {
    // Block clicks during loading
    if (state.driveLoading) {
      return;
    }
    
    if (state.folderNavigationStack.length === 0) {
      return;
    }
    
    const newStack = state.folderNavigationStack.slice(0, -1);
    const newCurrentFolderId = newStack.length > 0 
      ? newStack[newStack.length - 1].id 
      : null;
    
    loadDriveFiles({ loadMore: false, folderId: newCurrentFolderId }).then(() => {
      dispatch({ type: ActionTypes.NAVIGATE_BACK });
    }).catch(() => {
      // On error, navigation is not updated
    });
  }, [state.folderNavigationStack, state.driveLoading, loadDriveFiles]);

  const handleNavigateToRoot = useCallback(() => {
    // Block clicks during loading
    if (state.driveLoading) {
      return;
    }
    
    dispatch({ type: ActionTypes.SET_DRIVE_FILES, payload: [] });
    loadDriveFiles({ loadMore: false, folderId: null }).then(() => {
      dispatch({ type: ActionTypes.RESET_FOLDER_NAVIGATION });
    }).catch(() => {
      // On error, navigation is not updated
    });
  }, [loadDriveFiles, state.driveLoading]);

  const handleNavigateToFolder = useCallback((folderId, index) => {
    // Block clicks during loading
    if (state.driveLoading) {
      return;
    }
    
    // Navigate to specific folder from breadcrumbs
    if (index === -1) {
      handleNavigateToRoot();
      return;
    }
    
    const newStack = state.folderNavigationStack.slice(0, index + 1);
    const targetFolder = newStack.length > 0 ? newStack[newStack.length - 1] : null;
    
    if (targetFolder) {
      dispatch({ type: ActionTypes.SET_DRIVE_FILES, payload: [] });
      loadDriveFiles({ loadMore: false, folderId: targetFolder.id }).then(() => {
        // Update navigation only after successful load
        dispatch({ 
          type: ActionTypes.SET_FOLDER_NAVIGATION_STACK, 
          payload: newStack 
        });
        dispatch({ 
          type: ActionTypes.SET_CURRENT_FOLDER, 
          payload: targetFolder.id 
        });
      }).catch(() => {
        // On error, navigation is not updated
      });
    }
  }, [state.folderNavigationStack, state.driveLoading, loadDriveFiles, handleNavigateToRoot]);

  return (
    <div className="app">
      <header className="app-header">
        <div className="app-header-top">
          <div className="app-header-info">
            <div className="app-title-wrapper">
              <i className="fa-brands fa-google-drive app-title-icon"></i>
              <h1 className="app-title">Data Room App</h1>
            </div>
            <p className="app-subtitle">Import and manage files from Google Drive</p>
          </div>
          <div className="app-actions">
            <button 
              onClick={checkHealth} 
              className="secondary-button"
              disabled={state.checkingHealth}
            >
              {state.checkingHealth ? (
                <>
                  <i className="fa-solid fa-spinner fa-spin" style={{ marginRight: '8px' }}></i>
                  Checking...
                </>
              ) : (
                <>
                  <i className="fa-solid fa-heartbeat" style={{ marginRight: '8px' }}></i>
                  Check backend
                </>
              )}
            </button>
            {state.healthStatus && (
              <span className={`hint-text ${state.healthStatus.includes('error') ? 'error-text' : 'success-text'}`}>
                {state.healthStatus.includes('error') ? (
                  <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '6px' }}></i>
                ) : (
                  <i className="fa-solid fa-circle-check" style={{ marginRight: '6px' }}></i>
                )}
                {state.healthStatus}
              </span>
            )}
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
                  <i className="fa-solid fa-circle-check"></i>
                  <span>{state.message}</span>
                </div>
              )}
              {state.error && (
                <div className="alert alert-error" onClick={() => dispatch({ type: ActionTypes.CLEAR_ERROR })}>
                  <i className="fa-solid fa-circle-exclamation"></i>
                  <span>{state.error}</span>
                </div>
              )}
            </div>
          )}

          <section className="drive-section">
            <div className="section-header">
              <h2>
                Google Drive
                {state.driveLoading && (
                  <i className="fa-solid fa-spinner fa-spin loading-icon" style={{ marginLeft: '8px' }}></i>
                )}
              </h2>
              <div className="section-actions">
                <button
                  onClick={() => {
                    // Check if Google Drive is connected before loading
                    if (!state.currentUser?.has_google_drive) {
                      dispatch({ 
                        type: ActionTypes.SET_ERROR, 
                        payload: 'Google Drive is not connected. Please sign in with Google to access Google Drive files.' 
                      });
                      return;
                    }
                    dispatch({ type: ActionTypes.RESET_FOLDER_NAVIGATION });
                    loadDriveFiles({ loadMore: false, folderId: null });
                  }}
                  className="primary-button"
                  disabled={state.driveLoading || !state.currentUser?.has_google_drive}
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
                <button
                  onClick={handleCreateFolderClick}
                  className="primary-button"
                  disabled={!state.currentUser?.has_google_drive || state.driveLoading || state.creatingFolder}
                >
                  Create folder
                </button>
              </div>
            </div>

            {/* Breadcrumbs and Back button */}
            {state.folderNavigationStack.length > 0 && (
              <div className="breadcrumbs">
                <button 
                  className="breadcrumb-item" 
                  onClick={() => !state.driveLoading && handleNavigateToFolder(null, -1)}
                  disabled={state.driveLoading}
                >
                  Root
                </button>
                {state.folderNavigationStack.map((folder, index) => (
                  <React.Fragment key={folder.id}>
                    <span className="breadcrumb-separator">/</span>
                    <button
                      className="breadcrumb-item"
                      onClick={() => !state.driveLoading && handleNavigateToFolder(folder.id, index)}
                      disabled={state.driveLoading}
                    >
                      {folder.name}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            )}

            <div
              className={`drive-list ${state.dragOver ? 'drag-over' : ''} ${state.uploadingToDrive ? 'uploading' : ''}`}
              onDragOver={handleDragOver}
              onDragEnter={handleDragEnter}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              {state.uploadingToDrive && (
                <div className="upload-progress">
                  <p>Uploading files to Google Drive...</p>
                </div>
              )}
              {!state.uploadingToDrive && state.dragOver && (
                <div className="drag-over-hint">
                  <p>Drop files here to upload to Google Drive</p>
                </div>
              )}
              {!state.currentUser?.has_google_drive ? (
                <div className="drive-not-connected">
                  <i className="fa-solid fa-circle-exclamation" style={{ marginRight: '8px', color: '#f59e0b' }}></i>
                  <p className="muted-text">
                    Google Drive is not connected. Please sign in with Google to access your Google Drive files.
                  </p>
                </div>
              ) : state.driveFiles.length === 0 && !state.driveLoading && !state.uploadingToDrive && !state.dragOver ? (
                <p className="muted-text">Google Drive files not loaded. Click "Load files".</p>
              ) : (
                <ul>
                  {state.driveFiles.map((file) => {
                    const isSelected = state.selectedDriveIds.includes(file.id);
                    const isFolder = file.is_folder || false;
                    const isGoogleApp = file.mime_type && file.mime_type.startsWith('application/vnd.google-apps.');
                    const canImport = !isFolder && !isGoogleApp;
                    return (
                      <li 
                        key={file.id} 
                        className={`drive-item ${isSelected ? 'selected' : ''} ${isFolder ? 'folder-clickable' : ''} ${state.driveLoading && isFolder ? 'folder-loading' : ''}`}
                        onClick={isFolder && !state.driveLoading ? () => handleFolderClick(file.id, file.name) : undefined}
                      >
                        <div className="drive-item-content">
                          {isFolder ? (
                            <div className="folder-header">
                              <i className="fa-solid fa-folder folder-icon"></i>
                              <span className="drive-item-name">
                                {file.name}
                              </span>
                              <i className="fa-solid fa-chevron-right folder-arrow"></i>
                            </div>
                          ) : (
                            <div className="checkbox-container">
                              <label>
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  disabled={isDriveSelectionDisabled || !canImport}
                                  onChange={(e) => {
                                    e.stopPropagation();
                                    toggleDriveSelection(file.id);
                                  }}
                                  onClick={(e) => e.stopPropagation()}
                                />
                                <i className={`fa-solid ${getFileIcon(file.mime_type)} file-icon`}></i>
                                <span className="drive-item-name">
                                  {file.name}
                                  {isGoogleApp && ' (Google App)'}
                                </span>
                              </label>
                            </div>
                          )}
                          <div className="drive-item-meta">
                            <span>{isFolder ? 'Folder' : (file.mime_type || '—')}</span>
                            <span>{isFolder || isGoogleApp ? '—' : (file.size_bytes ? `${file.size_bytes.toLocaleString()} bytes` : 'Size unknown')}</span>
                          </div>
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
                    <div className="imported-item-content">
                      <i className={`fa-solid ${getFileIcon(file.mime_type)} file-icon`}></i>
                      <div>
                        <div className="imported-name">{file.original_name}</div>
                        <div className="imported-meta">
                          <span>{file.mime_type || 'Type unknown'}</span>
                          <span>{file.size_bytes.toLocaleString()} bytes</span>
                        </div>
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

      {/* Create folder modal */}
      {state.createFolderModal?.isOpen && (
        <div className="modal-overlay" onClick={handleCreateFolderCancel}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Create Folder</h3>
            <input
              type="text"
              placeholder="Folder name"
              value={state.createFolderModal.folderName || ''}
              onChange={handleCreateFolderNameChange}
              disabled={state.creatingFolder}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !state.creatingFolder && state.createFolderModal?.folderName?.trim()) {
                  handleCreateFolderConfirm();
                }
                if (e.key === 'Escape') {
                  handleCreateFolderCancel();
                }
              }}
            />
            <div className="modal-actions">
              <button
                className="secondary-button"
                onClick={handleCreateFolderCancel}
                disabled={state.creatingFolder}
              >
                Cancel
              </button>
              <button
                className="accent-button"
                onClick={handleCreateFolderConfirm}
                disabled={state.creatingFolder || !state.createFolderModal.folderName?.trim()}
              >
                {state.creatingFolder ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

