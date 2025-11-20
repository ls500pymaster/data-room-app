# Backend Tests

This directory contains comprehensive unit and integration tests for the backend.

## Structure

```
tests/
├── conftest.py              # Shared fixtures and test configuration
├── unit/                    # Unit tests
│   ├── app/                # Tests for app/ module
│   │   ├── test_security.py
│   │   ├── test_deps.py
│   │   ├── test_file_storage.py
│   │   └── test_google_drive.py
│   └── api/                # Tests for api/ module
│       ├── test_auth.py
│       └── test_files.py
└── integration/            # Integration tests
    └── api/                # Full request/response cycle tests
        ├── test_auth.py
        └── test_files.py
```

## Running Tests

### Run all tests:
```bash
pytest
```

### Run only unit tests:
```bash
pytest tests/unit/
```

### Run only integration tests:
```bash
pytest tests/integration/
```

### Run specific test file:
```bash
pytest tests/unit/app/test_security.py
```

### Run with coverage:
```bash
pytest --cov=backend --cov-report=html
```

## Test Fixtures

- `test_db_session`: In-memory SQLite database session
- `test_client`: FastAPI test client with database override
- `test_user`: Test user with password authentication
- `test_user_with_google`: Test user with Google OAuth tokens
- `test_file`: Test file record
- `auth_cookies`: Authentication cookies for test user
- `temp_storage_dir`: Temporary storage directory for file tests

## Notes

- Tests use in-memory SQLite database for speed
- External services (Google Drive) are mocked
- File storage uses temporary directories that are cleaned up after tests

