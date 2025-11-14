# Data Room MVP

A secure file management system with Google Drive integration. Import, view, and manage files from Google Drive through an intuitive web interface.

## Features

- **Dual Authentication**: Sign in with Google OAuth or email/password
- **Google Drive Integration**: Import files directly from your Google Drive
- **File Viewing**: View imported files directly in the browser
- **File Management**: Delete files from your Data Room
- **Secure Storage**: Files stored securely on the server
- **User Dashboard**: Manage your files with an intuitive interface

## Tech Stack

### Backend
- **FastAPI** 0.115.2 - Modern Python web framework
- **PostgreSQL** 16 - Relational database
- **SQLAlchemy** 2.x - ORM for database operations
- **Alembic** 2.x - Database migrations
- **Poetry** - Dependency management
- **Google Drive API v3** - File integration

### Frontend
- **React** 18.3.1 - UI library
- **Axios** - HTTP client
- **CSS3** - Styling

### Infrastructure
- **Docker Compose** - Container orchestration
- **PostgreSQL** - Database service

## Prerequisites

Before you begin, ensure you have the following installed:

- [Docker](https://www.docker.com/get-started) (version 20.10 or higher)
- [Docker Compose](https://docs.docker.com/compose/install/) (version 2.0 or higher)
- [Google Cloud Platform](https://console.cloud.google.com/) account (for OAuth setup)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd DataRoom
```

### 2. Configure Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable **Google Drive API** and **Google+ API**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Configure OAuth consent screen:
   - User Type: External
   - Application name: Data Room
   - Authorized domains: `localhost` (for development)
6. Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:8000/api/auth/callback`
7. Copy your **Client ID** and **Client Secret**

### 3. Create Environment File

Create `backend/.env` file:

```bash
cd backend
touch .env
```

Add the following configuration:

```env
# Database
DB_URL=postgresql+asyncpg://user:pass@db:5432/dataroom

# Google OAuth 2.0
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/callback

# Security
SECRET_KEY=your-secret-key-here-change-in-production
SESSION_TTL_MINUTES=60

# Storage
STORAGE_PATH=/app/storage

# CORS (optional, defaults to localhost:3000)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### 4. Start the Application

From the project root directory:

```bash
docker compose up --build
```

This will:
- Build and start the PostgreSQL database
- Build and start the FastAPI backend
- Build and start the React frontend
- Run database migrations automatically

### 5. Access the Application

Once all containers are running:

- **Frontend**: [http://localhost:3000](http://localhost:3000)
- **Backend API**: [http://localhost:8000](http://localhost:8000)
- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)
- **Database**: `localhost:55432` (user: `user`, password: `pass`, database: `dataroom`)

## Project Structure

```
DataRoom/
├── backend/
│   ├── app/
│   │   ├── api/           # API routes (auth, files)
│   │   ├── core/          # Configuration
│   │   ├── models/        # SQLAlchemy models
│   │   ├── services/      # Business logic (Google Drive, file storage)
│   │   └── main.py        # FastAPI application entry point
│   ├── alembic/           # Database migrations
│   ├── pyproject.toml      # Poetry dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/           # API client functions
│   │   ├── components/    # React components
│   │   └── App.js         # Main application component
│   ├── package.json
│   └── Dockerfile
├── storage/               # User files (created automatically)
├── docker-compose.yml
└── README.md
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/auth/login` | Initiate Google OAuth flow |
| `GET` | `/api/auth/callback` | OAuth callback handler |
| `POST` | `/api/auth/register` | Register with email/password |
| `POST` | `/api/auth/login` | Login with email/password |
| `POST` | `/api/auth/logout` | Logout current user |
| `GET` | `/api/auth/user` | Get current user info |
| `GET` | `/api/auth/avatar` | Get user avatar (proxied) |

### Files

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/files` | List all imported files |
| `POST` | `/api/files/import` | Import files from Google Drive |
| `GET` | `/api/files/{id}` | Get file metadata |
| `GET` | `/api/files/{id}/view` | View file in browser |
| `DELETE` | `/api/files/{id}` | Delete file from Data Room |

### Google Drive

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/drive/picker-config` | Get Google Picker configuration |
| `GET` | `/api/drive/files` | List files in Google Drive |

## Development

### Running Locally (without Docker)

#### Backend

```bash
cd backend
poetry install
poetry run alembic upgrade head  # Run migrations
poetry run uvicorn app.main:app --reload
```

#### Frontend

```bash
cd frontend
npm install
npm start
```

### Database Migrations

```bash
# Create a new migration
cd backend
poetry run alembic revision --autogenerate -m "description"

# Apply migrations
poetry run alembic upgrade head

# Rollback migration
poetry run alembic downgrade -1
```

### Viewing Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f db
```

### Stopping the Application

```bash
# Stop containers
docker compose down

# Stop and remove volumes (WARNING: deletes database data)
docker compose down -v
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DB_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@db:5432/dataroom` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | Required |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | Required |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | `http://localhost:8000/api/auth/callback` |
| `SECRET_KEY` | Secret key for sessions | `dev-secret-change-me` |
| `SESSION_TTL_MINUTES` | Session timeout in minutes | `60` |
| `STORAGE_PATH` | Path to store user files | `/app/storage` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | `http://localhost:3000` |

### Google OAuth Scopes

The application requests the following scopes:
- `openid` - OpenID Connect
- `https://www.googleapis.com/auth/userinfo.email` - User email
- `https://www.googleapis.com/auth/userinfo.profile` - User profile
- `https://www.googleapis.com/auth/drive.readonly` - Read-only access to Google Drive

## Notes

- **File Storage**: Imported files are stored in the `storage/` directory, organized by user ID
- **Database**: PostgreSQL data is persisted in a Docker volume (`pg_data`)
- **Development Mode**: Hot reload is enabled for both backend and frontend
- **API Documentation**: Interactive API docs available at `/docs` (Swagger UI)

## Troubleshooting

### Port Already in Use

If ports 3000, 8000, or 55432 are already in use:

1. Change ports in `docker-compose.yml`
2. Update `GOOGLE_REDIRECT_URI` in `backend/.env` if port 8000 changed
3. Update `REACT_APP_API_URL` in `docker-compose.yml` if port 8000 changed

### Database Connection Issues

```bash
# Check if database is running
docker compose ps

# Restart database
docker compose restart db

# View database logs
docker compose logs db
```

### Google OAuth Not Working

1. Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `backend/.env`
2. Check that redirect URI matches exactly: `http://localhost:8000/api/auth/callback`
3. Ensure Google Drive API is enabled in Google Cloud Console
4. Check backend logs: `docker compose logs backend`

### Frontend Not Connecting to Backend

1. Verify `REACT_APP_API_URL` in `docker-compose.yml` matches backend URL
2. Check CORS settings in `backend/core/config.py`
3. Check browser console for errors

## License

This project is part of an MVP development.
