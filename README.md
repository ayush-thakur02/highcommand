# HighCommand - Project Management System

A minimal brutalist project management application with both CLI and Web interfaces.

## Features

- **User Authentication**: Secure account creation and login with hashed passwords
- **Project Management**: Create, edit, delete, and search projects
- **Task Management**: Full task lifecycle with status, priority, due dates, and assignees
- **Task Filtering**: Filter by status, assignee, and date range
- **CSV Export**: Export project tasks to CSV
- **Dual Interface**: Terminal CLI and Web UI

## Installation

### Prerequisites
- Python 3.7 or higher

### Setup

1. Clone or download this repository

2. Install Flask (only needed for web interface):
```bash
pip install -r requirements.txt
```

## Usage

### Terminal/CLI Interface

Run the command-line interface:
```bash
python app.py
```

Features:
- Menu-based navigation
- All project and task management features
- Works entirely in the terminal
- No dependencies required (pure Python)

### Web Interface

Run the Flask web server:
```bash
python web_app.py
```

Then open your browser to: **http://localhost:5000**

Features:
- Brutalist white theme design
- Clean, minimal developer-focused UI
- All CLI features accessible via web
- Session-based authentication
- Responsive design

## Design Philosophy

**Brutalism for Developers**
- Stark white background with black borders
- Monospace font (Courier New)
- No rounded corners, no shadows, no gradients
- High contrast, maximum readability
- Form follows function
- Zero visual distractions

## Project Structure

```
HighCommand/
├── app.py              # CLI application + backend logic
├── web_app.py          # Flask web application
├── requirements.txt    # Python dependencies
├── highcommand.db      # SQLite database (auto-created)
├── static/
│   └── style.css       # Brutalist white theme
└── templates/          # HTML templates
    ├── base.html
    ├── login.html
    ├── register.html
    ├── dashboard.html
    ├── projects.html
    ├── project_form.html
    ├── project_detail.html
    ├── task_form.html
    ├── task_detail.html
    └── error.html
```

## Database

- SQLite database stored in `highcommand.db`
- Automatically created on first run
- Shared between CLI and Web interfaces
- Contains: users, projects, tasks

## Security Notes

- Passwords are hashed using SHA-256 with random salt
- Session-based authentication for web interface
- SQL injection protection via parameterized queries
- No third-party authentication dependencies

## Development

Built with:
- Python standard library (CLI)
- Flask 3.0 (Web interface)
- SQLite (Database)
- Pure CSS (No frameworks)

## License

Open source - use as you wish.

## Author

Created by GitHub Copilot
December 9, 2025
