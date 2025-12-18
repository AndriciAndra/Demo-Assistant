# Demo Generator - Frontend

React frontend for the Demo & Self-Review Generator application.

## Tech Stack

- **React 18** with Vite
- **React Router** for navigation
- **Tailwind CSS** for styling
- **Axios** for API calls
- **Lucide React** for icons
- **date-fns** for date formatting

## Quick Start

### 1. Install dependencies

```bash
npm install
```

### 2. Start development server

```bash
npm run dev
```

The app will be available at `http://localhost:3000`

### 3. Build for production

```bash
npm run build
```

## Project Structure

```
src/
├── components/
│   ├── common/         # Reusable UI components
│   └── layout/         # Layout components (Sidebar, etc.)
├── context/
│   └── AuthContext.jsx # Authentication context
├── hooks/
│   └── useAuth.js      # Auth hook
├── pages/
│   ├── LoginPage.jsx   # Google OAuth login
│   ├── DemoPage.jsx    # Demo generator
│   ├── ReviewPage.jsx  # Self-review generator
│   ├── HistoryPage.jsx # Generated files history
│   └── SettingsPage.jsx# Settings & integrations
├── services/
│   ├── api.js          # Axios instance
│   ├── authService.js  # Auth API calls
│   ├── jiraService.js  # Jira API calls
│   ├── demoService.js  # Demo API calls
│   ├── reviewService.js# Review API calls
│   └── settingsService.js # Settings API calls
├── App.jsx             # Main app with routes
├── main.jsx            # Entry point
└── index.css           # Global styles
```

## Features

- **Google OAuth Login** - Single sign-on with Google
- **Demo Generator** - Create presentations from Jira sprint data
- **Self-Review Generator** - Generate performance review PDFs
- **History** - View and manage generated files
- **Settings** - Configure Jira, scheduler, and storage

## API Proxy

During development, API calls are proxied to `http://localhost:8000` via Vite.
Make sure the backend is running before starting the frontend.

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
VITE_API_URL=/api  # API base URL (uses Vite proxy by default)
```
