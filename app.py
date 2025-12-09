#!/usr/bin/env python3
"""
HighCommand - Terminal-based Project Management Application

A CLI project management tool with user authentication, projects, and tasks.
Uses only Python standard library and SQLite for data persistence.

Usage:
    python app.py

Features:
    - User account creation and authentication with secure password hashing
    - Project creation, editing, and deletion
    - Task management with status tracking, priorities, and assignees
    - Task filtering by status, assignee, and due date
    - CSV export functionality for project tasks
    
Author: GitHub Copilot
Date: December 9, 2025
"""

import sqlite3
import hashlib
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Tuple
import csv
from io import StringIO


# ============================================================================
# DATABASE LAYER
# ============================================================================

class Database:
    """Handles all database operations and schema initialization."""
    
    def __init__(self, db_path: str = "highcommand.db"):
        """Initialize database connection and create tables if needed."""
        self.db_path = db_path
        self.conn = None
        self.initialize()
    
    def connect(self):
        """Create database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        return self.conn
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
    
    def initialize(self):
        """Create database schema if it doesn't exist."""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        
        # Projects table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                owner_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'in-progress',
                created_at TEXT NOT NULL,
                FOREIGN KEY (owner_id) REFERENCES users(id)
            )
        """)
        
        # Project members table (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(project_id, user_id)
            )
        """)
        
        # Project join requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                requested_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(project_id, user_id)
            )
        """)
        
        # Tasks table - Updated to support multiple assignees
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL DEFAULT 'todo',
                priority TEXT NOT NULL DEFAULT 'medium',
                due_date TEXT,
                creator_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (creator_id) REFERENCES users(id)
            )
        """)
        
        # Task assignees table (many-to-many relationship)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_assignees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                assigned_at TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE(task_id, user_id)
            )
        """)
        
        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_owner 
            ON projects(owner_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_projects_status 
            ON projects(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_members_project 
            ON project_members(project_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_project_members_user 
            ON project_members(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_project 
            ON tasks(project_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tasks_status 
            ON tasks(status)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_assignees_task 
            ON task_assignees(task_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_task_assignees_user 
            ON task_assignees(user_id)
        """)
        
        conn.commit()
        self.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        self.close()
        return results
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows or last row id."""
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        last_id = cursor.lastrowid
        self.close()
        return last_id


# ============================================================================
# AUTHENTICATION & USER MANAGEMENT
# ============================================================================

class AuthManager:
    """Handles user authentication and password security."""
    
    def __init__(self, db: Database):
        self.db = db
    
    @staticmethod
    def hash_password(password: str, salt: str) -> str:
        """Hash password with salt using SHA-256."""
        return hashlib.sha256((password + salt).encode()).hexdigest()
    
    @staticmethod
    def generate_salt() -> str:
        """Generate a random salt for password hashing."""
        return os.urandom(32).hex()
    
    def create_user(self, username: str, password: str) -> Tuple[bool, str]:
        """
        Create a new user account.
        Returns (success, message).
        """
        # Validate input
        if not username or len(username.strip()) < 3:
            return False, "Username must be at least 3 characters long."
        
        if not password or len(password) < 6:
            return False, "Password must be at least 6 characters long."
        
        username = username.strip().lower()
        
        # Check if username exists
        existing = self.db.execute_query(
            "SELECT id FROM users WHERE username = ?", (username,)
        )
        if existing:
            return False, "Username already exists. Please choose another."
        
        # Create user
        salt = self.generate_salt()
        password_hash = self.hash_password(password, salt)
        created_at = datetime.now().isoformat()
        
        try:
            self.db.execute_update(
                "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                (username, password_hash, salt, created_at)
            )
            return True, f"Account created successfully! Welcome, {username}!"
        except Exception as e:
            return False, f"Error creating account: {str(e)}"
    
    def authenticate(self, username: str, password: str) -> Optional[Dict]:
        """
        Authenticate user credentials.
        Returns user dict if successful, None otherwise.
        """
        username = username.strip().lower()
        
        users = self.db.execute_query(
            "SELECT * FROM users WHERE username = ?", (username,)
        )
        
        if not users:
            return None
        
        user = dict(users[0])
        password_hash = self.hash_password(password, user['salt'])
        
        if password_hash == user['password_hash']:
            return user
        
        return None
    
    def get_user_by_id(self, user_id: int) -> Optional[Dict]:
        """Get user information by ID."""
        users = self.db.execute_query(
            "SELECT id, username, created_at FROM users WHERE id = ?", (user_id,)
        )
        return dict(users[0]) if users else None
    
    def get_all_users(self) -> List[Dict]:
        """Get all users (for assignee selection)."""
        users = self.db.execute_query(
            "SELECT id, username FROM users ORDER BY username"
        )
        return [dict(user) for user in users]


# ============================================================================
# PROJECT MANAGEMENT
# ============================================================================

class ProjectManager:
    """Handles project operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_project(self, name: str, description: str, owner_id: int) -> Tuple[bool, str]:
        """Create a new project."""
        if not name or len(name.strip()) < 3:
            return False, "Project name must be at least 3 characters long."
        
        name = name.strip()
        description = description.strip() if description else ""
        created_at = datetime.now().isoformat()
        
        try:
            project_id = self.db.execute_update(
                "INSERT INTO projects (name, description, owner_id, created_at) VALUES (?, ?, ?, ?)",
                (name, description, owner_id, created_at)
            )
            return True, f"Project '{name}' created successfully! (ID: {project_id})"
        except Exception as e:
            return False, f"Error creating project: {str(e)}"
    
    def list_projects(self, user_id: Optional[int] = None) -> List[Dict]:
        """
        List all projects or projects owned by a specific user.
        """
        if user_id:
            query = """
                SELECT p.*, u.username as owner_name
                FROM projects p
                JOIN users u ON p.owner_id = u.id
                WHERE p.owner_id = ?
                ORDER BY p.created_at DESC
            """
            projects = self.db.execute_query(query, (user_id,))
        else:
            query = """
                SELECT p.*, u.username as owner_name
                FROM projects p
                JOIN users u ON p.owner_id = u.id
                ORDER BY p.created_at DESC
            """
            projects = self.db.execute_query(query)
        
        return [dict(project) for project in projects]
    
    def get_project(self, project_id: int) -> Optional[Dict]:
        """Get project details by ID."""
        query = """
            SELECT p.*, u.username as owner_name
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            WHERE p.id = ?
        """
        projects = self.db.execute_query(query, (project_id,))
        return dict(projects[0]) if projects else None
    
    def update_project(self, project_id: int, user_id: int, name: str = None, 
                      description: str = None) -> Tuple[bool, str]:
        """Update project details (only owner can update)."""
        project = self.get_project(project_id)
        if not project:
            return False, "Project not found."
        
        if project['owner_id'] != user_id:
            return False, "Only the project owner can edit this project."
        
        updates = []
        params = []
        
        if name and len(name.strip()) >= 3:
            updates.append("name = ?")
            params.append(name.strip())
        
        if description is not None:
            updates.append("description = ?")
            params.append(description.strip())
        
        if not updates:
            return False, "No valid updates provided."
        
        params.append(project_id)
        query = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
        
        try:
            self.db.execute_update(query, tuple(params))
            return True, "Project updated successfully!"
        except Exception as e:
            return False, f"Error updating project: {str(e)}"
    
    def delete_project(self, project_id: int, user_id: int) -> Tuple[bool, str]:
        """Delete a project (only owner can delete)."""
        project = self.get_project(project_id)
        if not project:
            return False, "Project not found."
        
        if project['owner_id'] != user_id:
            return False, "Only the project owner can delete this project."
        
        try:
            self.db.execute_update("DELETE FROM projects WHERE id = ?", (project_id,))
            return True, f"Project '{project['name']}' and all its tasks deleted successfully!"
        except Exception as e:
            return False, f"Error deleting project: {str(e)}"
    
    def search_projects(self, search_term: str) -> List[Dict]:
        """Search projects by name."""
        query = """
            SELECT p.*, u.username as owner_name
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            WHERE p.name LIKE ?
            ORDER BY p.created_at DESC
        """
        projects = self.db.execute_query(query, (f"%{search_term}%",))
        return [dict(project) for project in projects]
    
    def add_member(self, project_id: int, user_id: int) -> Tuple[bool, str]:
        """Add a member to a project."""
        joined_at = datetime.now().isoformat()
        try:
            self.db.execute_update(
                "INSERT INTO project_members (project_id, user_id, joined_at) VALUES (?, ?, ?)",
                (project_id, user_id, joined_at)
            )
            return True, "Member added successfully!"
        except Exception as e:
            return False, f"Error adding member: {str(e)}"
    
    def remove_member(self, project_id: int, user_id: int, requester_id: int) -> Tuple[bool, str]:
        """Remove a member from a project (only owner can remove)."""
        project = self.get_project(project_id)
        if not project:
            return False, "Project not found."
        
        if project['owner_id'] != requester_id and user_id != requester_id:
            return False, "Only the project owner or the member themselves can remove membership."
        
        try:
            self.db.execute_update(
                "DELETE FROM project_members WHERE project_id = ? AND user_id = ?",
                (project_id, user_id)
            )
            return True, "Member removed successfully!"
        except Exception as e:
            return False, f"Error removing member: {str(e)}"
    
    def get_project_members(self, project_id: int) -> List[Dict]:
        """Get all members of a project including the owner."""
        query = """
            SELECT u.id, u.username, pm.joined_at, 'member' as role
            FROM project_members pm
            JOIN users u ON pm.user_id = u.id
            WHERE pm.project_id = ?
            UNION
            SELECT u.id, u.username, p.created_at as joined_at, 'owner' as role
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            WHERE p.id = ?
            ORDER BY role DESC, joined_at ASC
        """
        members = self.db.execute_query(query, (project_id, project_id))
        return [dict(member) for member in members]
    
    def is_member(self, project_id: int, user_id: int) -> bool:
        """Check if user is a member or owner of a project."""
        query = """
            SELECT 1 FROM projects WHERE id = ? AND owner_id = ?
            UNION
            SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?
        """
        result = self.db.execute_query(query, (project_id, user_id, project_id, user_id))
        return len(result) > 0
    
    def request_to_join(self, project_id: int, user_id: int) -> Tuple[bool, str]:
        """Request to join a project."""
        # Check if already a member
        if self.is_member(project_id, user_id):
            return False, "You are already a member of this project."
        
        # Check for existing request
        existing = self.db.execute_query(
            "SELECT id FROM project_requests WHERE project_id = ? AND user_id = ? AND status = 'pending'",
            (project_id, user_id)
        )
        if existing:
            return False, "You have already requested to join this project."
        
        requested_at = datetime.now().isoformat()
        try:
            self.db.execute_update(
                "INSERT INTO project_requests (project_id, user_id, requested_at) VALUES (?, ?, ?)",
                (project_id, user_id, requested_at)
            )
            return True, "Join request sent successfully!"
        except Exception as e:
            return False, f"Error sending request: {str(e)}"
    
    def get_pending_requests(self, project_id: int) -> List[Dict]:
        """Get all pending join requests for a project."""
        query = """
            SELECT pr.id, pr.project_id, pr.user_id, pr.requested_at, u.username
            FROM project_requests pr
            JOIN users u ON pr.user_id = u.id
            WHERE pr.project_id = ? AND pr.status = 'pending'
            ORDER BY pr.requested_at ASC
        """
        requests = self.db.execute_query(query, (project_id,))
        return [dict(req) for req in requests]
    
    def approve_request(self, request_id: int, project_owner_id: int) -> Tuple[bool, str]:
        """Approve a join request (only owner can approve)."""
        # Get request details
        requests = self.db.execute_query(
            "SELECT pr.*, p.owner_id FROM project_requests pr JOIN projects p ON pr.project_id = p.id WHERE pr.id = ?",
            (request_id,)
        )
        if not requests:
            return False, "Request not found."
        
        request = dict(requests[0])
        if request['owner_id'] != project_owner_id:
            return False, "Only the project owner can approve requests."
        
        try:
            # Add member
            self.add_member(request['project_id'], request['user_id'])
            # Update request status
            self.db.execute_update(
                "UPDATE project_requests SET status = 'approved' WHERE id = ?",
                (request_id,)
            )
            return True, "Request approved successfully!"
        except Exception as e:
            return False, f"Error approving request: {str(e)}"
    
    def reject_request(self, request_id: int, project_owner_id: int) -> Tuple[bool, str]:
        """Reject a join request (only owner can reject)."""
        # Get request details
        requests = self.db.execute_query(
            "SELECT pr.*, p.owner_id FROM project_requests pr JOIN projects p ON pr.project_id = p.id WHERE pr.id = ?",
            (request_id,)
        )
        if not requests:
            return False, "Request not found."
        
        request = dict(requests[0])
        if request['owner_id'] != project_owner_id:
            return False, "Only the project owner can reject requests."
        
        try:
            self.db.execute_update(
                "UPDATE project_requests SET status = 'rejected' WHERE id = ?",
                (request_id,)
            )
            return True, "Request rejected successfully!"
        except Exception as e:
            return False, f"Error rejecting request: {str(e)}"
    
    def list_user_projects(self, user_id: int) -> List[Dict]:
        """List all projects where user is a member or owner."""
        query = """
            SELECT DISTINCT p.*, u.username as owner_name
            FROM projects p
            JOIN users u ON p.owner_id = u.id
            LEFT JOIN project_members pm ON p.id = pm.project_id
            WHERE p.owner_id = ? OR pm.user_id = ?
            ORDER BY p.created_at DESC
        """
        projects = self.db.execute_query(query, (user_id, user_id))
        return [dict(project) for project in projects]
    
    def update_project_status(self, project_id: int, user_id: int, status: str) -> Tuple[bool, str]:
        """Update project status (only owner can update)."""
        if status not in ['in-progress', 'completed']:
            return False, "Invalid status. Must be 'in-progress' or 'completed'."
        
        project = self.get_project(project_id)
        if not project:
            return False, "Project not found."
        
        if project['owner_id'] != user_id:
            return False, "Only the project owner can update project status."
        
        try:
            self.db.execute_update(
                "UPDATE projects SET status = ? WHERE id = ?",
                (status, project_id)
            )
            return True, "Project status updated successfully!"
        except Exception as e:
            return False, f"Error updating status: {str(e)}"


# ============================================================================
# TASK MANAGEMENT
# ============================================================================

class TaskManager:
    """Handles task operations."""
    
    VALID_STATUSES = ['todo', 'in-progress', 'done']
    VALID_PRIORITIES = ['low', 'medium', 'high']
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_task(self, project_id: int, title: str, description: str,
                   status: str, priority: str, due_date: Optional[str],
                   assignee_ids: List[int], creator_id: int) -> Tuple[bool, str]:
        """Create a new task with multiple assignees."""
        if not title or len(title.strip()) < 3:
            return False, "Task title must be at least 3 characters long."
        
        if status not in self.VALID_STATUSES:
            return False, f"Invalid status. Must be one of: {', '.join(self.VALID_STATUSES)}"
        
        if priority not in self.VALID_PRIORITIES:
            return False, f"Invalid priority. Must be one of: {', '.join(self.VALID_PRIORITIES)}"
        
        # Validate due date format
        if due_date:
            try:
                datetime.strptime(due_date, "%Y-%m-%d")
            except ValueError:
                return False, "Invalid date format. Use YYYY-MM-DD."
        
        title = title.strip()
        description = description.strip() if description else ""
        created_at = datetime.now().isoformat()
        assigned_at = datetime.now().isoformat()
        
        try:
            task_id = self.db.execute_update(
                """INSERT INTO tasks (project_id, title, description, status, priority, 
                   due_date, creator_id, created_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, title, description, status, priority, due_date, 
                 creator_id, created_at)
            )
            
            # Add assignees
            if assignee_ids:
                for assignee_id in assignee_ids:
                    self.db.execute_update(
                        "INSERT INTO task_assignees (task_id, user_id, assigned_at) VALUES (?, ?, ?)",
                        (task_id, assignee_id, assigned_at)
                    )
            
            return True, f"Task '{title}' created successfully! (ID: {task_id})"
        except Exception as e:
            return False, f"Error creating task: {str(e)}"
    
    def get_task(self, task_id: int) -> Optional[Dict]:
        """Get task details by ID with assignees."""
        query = """
            SELECT t.*, 
                   u1.username as creator_name,
                   p.name as project_name
            FROM tasks t
            JOIN users u1 ON t.creator_id = u1.id
            JOIN projects p ON t.project_id = p.id
            WHERE t.id = ?
        """
        tasks = self.db.execute_query(query, (task_id,))
        if not tasks:
            return None
        
        task = dict(tasks[0])
        
        # Get assignees
        assignees_query = """
            SELECT u.id, u.username
            FROM task_assignees ta
            JOIN users u ON ta.user_id = u.id
            WHERE ta.task_id = ?
        """
        assignees = self.db.execute_query(assignees_query, (task_id,))
        task['assignees'] = [dict(a) for a in assignees]
        task['assignee_names'] = ', '.join([a['username'] for a in task['assignees']]) if task['assignees'] else 'Unassigned'
        
        return task
    
    def list_tasks(self, project_id: int, status: Optional[str] = None,
                   assignee_id: Optional[int] = None, 
                   due_date_from: Optional[str] = None,
                   due_date_to: Optional[str] = None) -> List[Dict]:
        """List tasks with optional filtering."""
        query = """
            SELECT DISTINCT t.*, 
                   u1.username as creator_name
            FROM tasks t
            JOIN users u1 ON t.creator_id = u1.id
            LEFT JOIN task_assignees ta ON t.id = ta.task_id
            WHERE t.project_id = ?
        """
        params = [project_id]
        
        if status:
            query += " AND t.status = ?"
            params.append(status)
        
        if assignee_id:
            query += " AND ta.user_id = ?"
            params.append(assignee_id)
        
        if due_date_from:
            query += " AND t.due_date >= ?"
            params.append(due_date_from)
        
        if due_date_to:
            query += " AND t.due_date <= ?"
            params.append(due_date_to)
        
        query += " ORDER BY t.created_at DESC"
        
        tasks = self.db.execute_query(query, tuple(params))
        result = []
        
        for task in tasks:
            task_dict = dict(task)
            # Get assignees for each task
            assignees_query = """
                SELECT u.id, u.username
                FROM task_assignees ta
                JOIN users u ON ta.user_id = u.id
                WHERE ta.task_id = ?
            """
            assignees = self.db.execute_query(assignees_query, (task_dict['id'],))
            task_dict['assignees'] = [dict(a) for a in assignees]
            task_dict['assignee_names'] = ', '.join([a['username'] for a in task_dict['assignees']]) if task_dict['assignees'] else 'Unassigned'
            result.append(task_dict)
        
        return result
    
    def update_task(self, task_id: int, user_id: int, project_owner_id: int,
                   **kwargs) -> Tuple[bool, str]:
        """Update task fields including multiple assignees."""
        task = self.get_task(task_id)
        if not task:
            return False, "Task not found."
        
        # Only creator or project owner can edit
        if task['creator_id'] != user_id and project_owner_id != user_id:
            return False, "Only the task creator or project owner can edit this task."
        
        updates = []
        params = []
        
        if 'title' in kwargs and kwargs['title'] and len(kwargs['title'].strip()) >= 3:
            updates.append("title = ?")
            params.append(kwargs['title'].strip())
        
        if 'description' in kwargs:
            updates.append("description = ?")
            params.append(kwargs['description'].strip() if kwargs['description'] else "")
        
        if 'status' in kwargs and kwargs['status'] in self.VALID_STATUSES:
            updates.append("status = ?")
            params.append(kwargs['status'])
        
        if 'priority' in kwargs and kwargs['priority'] in self.VALID_PRIORITIES:
            updates.append("priority = ?")
            params.append(kwargs['priority'])
        
        if 'due_date' in kwargs:
            if kwargs['due_date']:
                try:
                    datetime.strptime(kwargs['due_date'], "%Y-%m-%d")
                    updates.append("due_date = ?")
                    params.append(kwargs['due_date'])
                except ValueError:
                    return False, "Invalid date format. Use YYYY-MM-DD."
            else:
                updates.append("due_date = ?")
                params.append(None)
        
        try:
            # Update basic task fields if any
            if updates:
                params.append(task_id)
                query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
                self.db.execute_update(query, tuple(params))
            
            # Update assignees if provided
            if 'assignee_ids' in kwargs:
                # Remove existing assignees
                self.db.execute_update("DELETE FROM task_assignees WHERE task_id = ?", (task_id,))
                
                # Add new assignees
                if kwargs['assignee_ids']:
                    assigned_at = datetime.now().isoformat()
                    for assignee_id in kwargs['assignee_ids']:
                        self.db.execute_update(
                            "INSERT INTO task_assignees (task_id, user_id, assigned_at) VALUES (?, ?, ?)",
                            (task_id, assignee_id, assigned_at)
                        )
            
            return True, "Task updated successfully!"
        except Exception as e:
            return False, f"Error updating task: {str(e)}"
    
    def delete_task(self, task_id: int, user_id: int, project_owner_id: int) -> Tuple[bool, str]:
        """Delete a task."""
        task = self.get_task(task_id)
        if not task:
            return False, "Task not found."
        
        # Only creator or project owner can delete
        if task['creator_id'] != user_id and project_owner_id != user_id:
            return False, "Only the task creator or project owner can delete this task."
        
        try:
            self.db.execute_update("DELETE FROM tasks WHERE id = ?", (task_id,))
            return True, f"Task '{task['title']}' deleted successfully!"
        except Exception as e:
            return False, f"Error deleting task: {str(e)}"
    
    def get_user_assigned_tasks(self, user_id: int, status_filter: Optional[str] = None) -> List[Dict]:
        """Get all tasks assigned to a specific user, optionally filtered by status."""
        query = """
            SELECT DISTINCT t.*, 
                   u1.username as creator_name,
                   p.name as project_name
            FROM tasks t
            JOIN users u1 ON t.creator_id = u1.id
            JOIN projects p ON t.project_id = p.id
            JOIN task_assignees ta ON t.id = ta.task_id
            WHERE ta.user_id = ?
        """
        params = [user_id]
        
        if status_filter:
            query += " AND t.status = ?"
            params.append(status_filter)
        
        query += " ORDER BY t.due_date ASC, t.created_at DESC"
        
        tasks = self.db.execute_query(query, tuple(params))
        result = []
        
        for task in tasks:
            task_dict = dict(task)
            # Get all assignees for each task
            assignees_query = """
                SELECT u.id, u.username
                FROM task_assignees ta
                JOIN users u ON ta.user_id = u.id
                WHERE ta.task_id = ?
            """
            assignees = self.db.execute_query(assignees_query, (task_dict['id'],))
            task_dict['assignees'] = [dict(a) for a in assignees]
            task_dict['assignee_names'] = ', '.join([a['username'] for a in task_dict['assignees']]) if task_dict['assignees'] else 'Unassigned'
            result.append(task_dict)
        
        return result
    
    def export_tasks_to_csv(self, project_id: int) -> str:
        """Export project tasks to CSV format."""
        tasks = self.list_tasks(project_id)
        
        if not tasks:
            return "No tasks to export."
        
        output = StringIO()
        fieldnames = ['ID', 'Title', 'Description', 'Status', 'Priority', 
                     'Due Date', 'Assignee', 'Creator', 'Created At']
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        for task in tasks:
            writer.writerow({
                'ID': task['id'],
                'Title': task['title'],
                'Description': task['description'] or '',
                'Status': task['status'],
                'Priority': task['priority'],
                'Due Date': task['due_date'] or '',
                'Assignee': task['assignee_name'] or 'Unassigned',
                'Creator': task['creator_name'],
                'Created At': task['created_at']
            })
        
        return output.getvalue()


# ============================================================================
# CLI APPLICATION
# ============================================================================

class HighCommandCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.db = Database()
        self.auth = AuthManager(self.db)
        self.projects = ProjectManager(self.db)
        self.tasks = TaskManager(self.db)
        self.current_user = None
    
    @staticmethod
    def clear_screen():
        """Clear the terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    @staticmethod
    def print_header(title: str):
        """Print a formatted header."""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70)
    
    @staticmethod
    def print_separator():
        """Print a separator line."""
        print("-" * 70)
    
    def get_input(self, prompt: str, allow_empty: bool = False) -> str:
        """Get user input with optional validation."""
        while True:
            value = input(prompt).strip()
            if value or allow_empty:
                return value
            print("⚠ This field cannot be empty. Please try again.")
    
    def get_choice(self, prompt: str, valid_choices: List[str]) -> str:
        """Get user choice from valid options."""
        while True:
            choice = input(prompt).strip().lower()
            if choice in valid_choices:
                return choice
            print(f"⚠ Invalid choice. Please choose from: {', '.join(valid_choices)}")
    
    def pause(self):
        """Pause and wait for user input."""
        input("\nPress Enter to continue...")
    
    # Authentication flows
    def show_welcome(self):
        """Show welcome screen."""
        self.clear_screen()
        self.print_header("HIGHCOMMAND - Project Management System")
        print("\n  Welcome! Manage your projects and tasks efficiently.\n")
    
    def login_flow(self):
        """Handle user login."""
        self.clear_screen()
        self.print_header("LOGIN")
        
        username = self.get_input("\nUsername: ")
        password = self.get_input("Password: ")
        
        user = self.auth.authenticate(username, password)
        
        if user:
            self.current_user = user
            print(f"\n✓ Login successful! Welcome back, {user['username']}!")
            self.pause()
            return True
        else:
            print("\n✗ Invalid username or password.")
            self.pause()
            return False
    
    def register_flow(self):
        """Handle user registration."""
        self.clear_screen()
        self.print_header("CREATE ACCOUNT")
        
        print("\nUsername requirements: At least 3 characters")
        print("Password requirements: At least 6 characters\n")
        
        username = self.get_input("Choose a username: ")
        password = self.get_input("Choose a password: ")
        password_confirm = self.get_input("Confirm password: ")
        
        if password != password_confirm:
            print("\n✗ Passwords do not match!")
            self.pause()
            return
        
        success, message = self.auth.create_user(username, password)
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def main_menu(self):
        """Show main menu after login."""
        while True:
            self.clear_screen()
            self.print_header(f"MAIN MENU - Logged in as: {self.current_user['username']}")
            
            print("\n1. Projects")
            print("2. Tasks")
            print("3. Logout")
            print("4. Exit")
            
            choice = self.get_input("\nChoose an option (1-4): ")
            
            if choice == '1':
                self.project_menu()
            elif choice == '2':
                self.task_menu()
            elif choice == '3':
                self.current_user = None
                print("\n✓ Logged out successfully!")
                self.pause()
                break
            elif choice == '4':
                print("\n👋 Goodbye!")
                sys.exit(0)
            else:
                print("\n⚠ Invalid choice. Please try again.")
                self.pause()
    
    # Project operations
    def project_menu(self):
        """Show project management menu."""
        while True:
            self.clear_screen()
            self.print_header("PROJECT MANAGEMENT")
            
            print("\n1. Create new project")
            print("2. List all projects")
            print("3. List my projects")
            print("4. Search projects")
            print("5. View project details")
            print("6. Edit project")
            print("7. Delete project")
            print("8. Back to main menu")
            
            choice = self.get_input("\nChoose an option (1-8): ")
            
            if choice == '1':
                self.create_project()
            elif choice == '2':
                self.list_projects(all_projects=True)
            elif choice == '3':
                self.list_projects(all_projects=False)
            elif choice == '4':
                self.search_projects()
            elif choice == '5':
                self.view_project()
            elif choice == '6':
                self.edit_project()
            elif choice == '7':
                self.delete_project()
            elif choice == '8':
                break
            else:
                print("\n⚠ Invalid choice. Please try again.")
                self.pause()
    
    def create_project(self):
        """Create a new project."""
        self.clear_screen()
        self.print_header("CREATE NEW PROJECT")
        
        name = self.get_input("\nProject name: ")
        description = self.get_input("Description (optional): ", allow_empty=True)
        
        success, message = self.projects.create_project(
            name, description, self.current_user['id']
        )
        
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def list_projects(self, all_projects: bool = True):
        """List projects."""
        self.clear_screen()
        title = "ALL PROJECTS" if all_projects else "MY PROJECTS"
        self.print_header(title)
        
        project_list = self.projects.list_projects(
            None if all_projects else self.current_user['id']
        )
        
        if not project_list:
            print("\nNo projects found.")
        else:
            print(f"\nFound {len(project_list)} project(s):\n")
            for project in project_list:
                print(f"ID: {project['id']} | {project['name']}")
                print(f"  Owner: {project['owner_name']}")
                print(f"  Description: {project['description'] or 'N/A'}")
                print(f"  Created: {project['created_at'][:10]}")
                self.print_separator()
        
        self.pause()
    
    def search_projects(self):
        """Search for projects."""
        self.clear_screen()
        self.print_header("SEARCH PROJECTS")
        
        search_term = self.get_input("\nEnter search term: ")
        
        results = self.projects.search_projects(search_term)
        
        if not results:
            print(f"\nNo projects found matching '{search_term}'.")
        else:
            print(f"\nFound {len(results)} project(s):\n")
            for project in results:
                print(f"ID: {project['id']} | {project['name']}")
                print(f"  Owner: {project['owner_name']}")
                print(f"  Description: {project['description'] or 'N/A'}")
                self.print_separator()
        
        self.pause()
    
    def view_project(self):
        """View project details."""
        self.clear_screen()
        self.print_header("VIEW PROJECT")
        
        project_id = self.get_input("\nEnter project ID: ")
        
        try:
            project_id = int(project_id)
        except ValueError:
            print("\n✗ Invalid project ID.")
            self.pause()
            return
        
        project = self.projects.get_project(project_id)
        
        if not project:
            print("\n✗ Project not found.")
            self.pause()
            return
        
        print(f"\n📁 {project['name']}")
        self.print_separator()
        print(f"ID: {project['id']}")
        print(f"Owner: {project['owner_name']}")
        print(f"Description: {project['description'] or 'N/A'}")
        print(f"Created: {project['created_at']}")
        self.print_separator()
        
        # Show task summary
        tasks = self.tasks.list_tasks(project_id)
        print(f"\nTasks: {len(tasks)} total")
        if tasks:
            todo = sum(1 for t in tasks if t['status'] == 'todo')
            in_progress = sum(1 for t in tasks if t['status'] == 'in-progress')
            done = sum(1 for t in tasks if t['status'] == 'done')
            print(f"  • Todo: {todo}")
            print(f"  • In Progress: {in_progress}")
            print(f"  • Done: {done}")
        
        self.pause()
    
    def edit_project(self):
        """Edit a project."""
        self.clear_screen()
        self.print_header("EDIT PROJECT")
        
        project_id = self.get_input("\nEnter project ID: ")
        
        try:
            project_id = int(project_id)
        except ValueError:
            print("\n✗ Invalid project ID.")
            self.pause()
            return
        
        project = self.projects.get_project(project_id)
        if not project:
            print("\n✗ Project not found.")
            self.pause()
            return
        
        print(f"\nCurrent name: {project['name']}")
        print(f"Current description: {project['description'] or 'N/A'}")
        
        name = self.get_input("\nNew name (or press Enter to keep current): ", allow_empty=True)
        description = self.get_input("New description (or press Enter to keep current): ", allow_empty=True)
        
        if not name and not description:
            print("\n⚠ No changes made.")
            self.pause()
            return
        
        success, message = self.projects.update_project(
            project_id, self.current_user['id'],
            name if name else None,
            description if description else None
        )
        
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def delete_project(self):
        """Delete a project."""
        self.clear_screen()
        self.print_header("DELETE PROJECT")
        
        project_id = self.get_input("\nEnter project ID: ")
        
        try:
            project_id = int(project_id)
        except ValueError:
            print("\n✗ Invalid project ID.")
            self.pause()
            return
        
        project = self.projects.get_project(project_id)
        if not project:
            print("\n✗ Project not found.")
            self.pause()
            return
        
        print(f"\n⚠ WARNING: This will delete '{project['name']}' and ALL its tasks!")
        confirm = self.get_input("Type 'yes' to confirm: ")
        
        if confirm.lower() == 'yes':
            success, message = self.projects.delete_project(project_id, self.current_user['id'])
            print(f"\n{'✓' if success else '✗'} {message}")
        else:
            print("\n⚠ Deletion cancelled.")
        
        self.pause()
    
    # Task operations
    def task_menu(self):
        """Show task management menu."""
        while True:
            self.clear_screen()
            self.print_header("TASK MANAGEMENT")
            
            print("\n1. Create new task")
            print("2. List tasks (with filtering)")
            print("3. View task details")
            print("4. Edit task")
            print("5. Delete task")
            print("6. Change task status")
            print("7. Assign task")
            print("8. Export tasks to CSV")
            print("9. Back to main menu")
            
            choice = self.get_input("\nChoose an option (1-9): ")
            
            if choice == '1':
                self.create_task()
            elif choice == '2':
                self.list_tasks()
            elif choice == '3':
                self.view_task()
            elif choice == '4':
                self.edit_task()
            elif choice == '5':
                self.delete_task()
            elif choice == '6':
                self.change_task_status()
            elif choice == '7':
                self.assign_task()
            elif choice == '8':
                self.export_tasks()
            elif choice == '9':
                break
            else:
                print("\n⚠ Invalid choice. Please try again.")
                self.pause()
    
    def create_task(self):
        """Create a new task."""
        self.clear_screen()
        self.print_header("CREATE NEW TASK")
        
        # First, select project
        project_id = self.get_input("\nEnter project ID: ")
        
        try:
            project_id = int(project_id)
        except ValueError:
            print("\n✗ Invalid project ID.")
            self.pause()
            return
        
        project = self.projects.get_project(project_id)
        if not project:
            print("\n✗ Project not found.")
            self.pause()
            return
        
        print(f"\nCreating task for project: {project['name']}\n")
        
        title = self.get_input("Task title: ")
        description = self.get_input("Description (optional): ", allow_empty=True)
        
        print(f"\nStatus options: {', '.join(self.tasks.VALID_STATUSES)}")
        status = self.get_choice("Status [todo]: ", self.tasks.VALID_STATUSES + [''])
        status = status if status else 'todo'
        
        print(f"\nPriority options: {', '.join(self.tasks.VALID_PRIORITIES)}")
        priority = self.get_choice("Priority [medium]: ", self.tasks.VALID_PRIORITIES + [''])
        priority = priority if priority else 'medium'
        
        due_date = self.get_input("\nDue date (YYYY-MM-DD, optional): ", allow_empty=True)
        
        # Optional assignee
        assign = self.get_input("Assign to someone? (y/n) [n]: ", allow_empty=True)
        assignee_id = None
        
        if assign.lower() == 'y':
            users = self.auth.get_all_users()
            print("\nAvailable users:")
            for user in users:
                print(f"  {user['id']}: {user['username']}")
            
            assignee_input = self.get_input("\nEnter user ID (or press Enter to skip): ", allow_empty=True)
            if assignee_input:
                try:
                    assignee_id = int(assignee_input)
                except ValueError:
                    print("\n⚠ Invalid user ID. Task will be unassigned.")
        
        success, message = self.tasks.create_task(
            project_id, title, description, status, priority,
            due_date if due_date else None, assignee_id, self.current_user['id']
        )
        
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def list_tasks(self):
        """List tasks with optional filtering."""
        self.clear_screen()
        self.print_header("LIST TASKS")
        
        project_id = self.get_input("\nEnter project ID: ")
        
        try:
            project_id = int(project_id)
        except ValueError:
            print("\n✗ Invalid project ID.")
            self.pause()
            return
        
        project = self.projects.get_project(project_id)
        if not project:
            print("\n✗ Project not found.")
            self.pause()
            return
        
        # Optional filters
        print("\n--- Optional Filters (press Enter to skip) ---")
        
        status_filter = self.get_input(f"Filter by status ({', '.join(self.tasks.VALID_STATUSES)}): ", allow_empty=True)
        status_filter = status_filter if status_filter in self.tasks.VALID_STATUSES else None
        
        assignee_input = self.get_input("Filter by assignee ID: ", allow_empty=True)
        assignee_filter = None
        if assignee_input:
            try:
                assignee_filter = int(assignee_input)
            except ValueError:
                pass
        
        due_from = self.get_input("Due date from (YYYY-MM-DD): ", allow_empty=True)
        due_to = self.get_input("Due date to (YYYY-MM-DD): ", allow_empty=True)
        
        tasks = self.tasks.list_tasks(
            project_id, status_filter, assignee_filter,
            due_from if due_from else None,
            due_to if due_to else None
        )
        
        self.clear_screen()
        self.print_header(f"TASKS - {project['name']}")
        
        if not tasks:
            print("\nNo tasks found.")
        else:
            print(f"\nFound {len(tasks)} task(s):\n")
            for task in tasks:
                status_icon = {"todo": "○", "in-progress": "◐", "done": "●"}
                priority_icon = {"low": "↓", "medium": "→", "high": "↑"}
                
                print(f"{status_icon.get(task['status'], '○')} ID: {task['id']} | {task['title']}")
                print(f"  Status: {task['status']} | Priority: {priority_icon.get(task['priority'], '')} {task['priority']}")
                print(f"  Assignee: {task['assignee_name'] or 'Unassigned'}")
                print(f"  Due: {task['due_date'] or 'No due date'}")
                self.print_separator()
        
        self.pause()
    
    def view_task(self):
        """View task details."""
        self.clear_screen()
        self.print_header("VIEW TASK")
        
        task_id = self.get_input("\nEnter task ID: ")
        
        try:
            task_id = int(task_id)
        except ValueError:
            print("\n✗ Invalid task ID.")
            self.pause()
            return
        
        task = self.tasks.get_task(task_id)
        
        if not task:
            print("\n✗ Task not found.")
            self.pause()
            return
        
        print(f"\n📋 {task['title']}")
        self.print_separator()
        print(f"ID: {task['id']}")
        print(f"Project: {task['project_name']}")
        print(f"Description: {task['description'] or 'N/A'}")
        print(f"Status: {task['status']}")
        print(f"Priority: {task['priority']}")
        print(f"Due Date: {task['due_date'] or 'Not set'}")
        print(f"Assignee: {task['assignee_name'] or 'Unassigned'}")
        print(f"Creator: {task['creator_name']}")
        print(f"Created: {task['created_at']}")
        
        self.pause()
    
    def edit_task(self):
        """Edit a task."""
        self.clear_screen()
        self.print_header("EDIT TASK")
        
        task_id = self.get_input("\nEnter task ID: ")
        
        try:
            task_id = int(task_id)
        except ValueError:
            print("\n✗ Invalid task ID.")
            self.pause()
            return
        
        task = self.tasks.get_task(task_id)
        if not task:
            print("\n✗ Task not found.")
            self.pause()
            return
        
        project = self.projects.get_project(task['project_id'])
        
        print(f"\nEditing: {task['title']}")
        print("\n--- Enter new values or press Enter to keep current ---\n")
        
        title = self.get_input(f"Title [{task['title']}]: ", allow_empty=True)
        description = self.get_input(f"Description [{task['description'] or 'N/A'}]: ", allow_empty=True)
        
        print(f"\nStatus options: {', '.join(self.tasks.VALID_STATUSES)}")
        status = self.get_input(f"Status [{task['status']}]: ", allow_empty=True)
        
        print(f"\nPriority options: {', '.join(self.tasks.VALID_PRIORITIES)}")
        priority = self.get_input(f"Priority [{task['priority']}]: ", allow_empty=True)
        
        due_date = self.get_input(f"Due date [{task['due_date'] or 'Not set'}]: ", allow_empty=True)
        
        updates = {}
        if title:
            updates['title'] = title
        if description:
            updates['description'] = description
        if status:
            updates['status'] = status
        if priority:
            updates['priority'] = priority
        if due_date:
            updates['due_date'] = due_date
        
        if not updates:
            print("\n⚠ No changes made.")
            self.pause()
            return
        
        success, message = self.tasks.update_task(
            task_id, self.current_user['id'], project['owner_id'], **updates
        )
        
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def delete_task(self):
        """Delete a task."""
        self.clear_screen()
        self.print_header("DELETE TASK")
        
        task_id = self.get_input("\nEnter task ID: ")
        
        try:
            task_id = int(task_id)
        except ValueError:
            print("\n✗ Invalid task ID.")
            self.pause()
            return
        
        task = self.tasks.get_task(task_id)
        if not task:
            print("\n✗ Task not found.")
            self.pause()
            return
        
        project = self.projects.get_project(task['project_id'])
        
        print(f"\n⚠ WARNING: This will delete task '{task['title']}'!")
        confirm = self.get_input("Type 'yes' to confirm: ")
        
        if confirm.lower() == 'yes':
            success, message = self.tasks.delete_task(
                task_id, self.current_user['id'], project['owner_id']
            )
            print(f"\n{'✓' if success else '✗'} {message}")
        else:
            print("\n⚠ Deletion cancelled.")
        
        self.pause()
    
    def change_task_status(self):
        """Change task status quickly."""
        self.clear_screen()
        self.print_header("CHANGE TASK STATUS")
        
        task_id = self.get_input("\nEnter task ID: ")
        
        try:
            task_id = int(task_id)
        except ValueError:
            print("\n✗ Invalid task ID.")
            self.pause()
            return
        
        task = self.tasks.get_task(task_id)
        if not task:
            print("\n✗ Task not found.")
            self.pause()
            return
        
        project = self.projects.get_project(task['project_id'])
        
        print(f"\nTask: {task['title']}")
        print(f"Current status: {task['status']}")
        print(f"\nStatus options: {', '.join(self.tasks.VALID_STATUSES)}")
        
        new_status = self.get_choice("\nNew status: ", self.tasks.VALID_STATUSES)
        
        success, message = self.tasks.update_task(
            task_id, self.current_user['id'], project['owner_id'],
            status=new_status
        )
        
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def assign_task(self):
        """Assign or reassign a task."""
        self.clear_screen()
        self.print_header("ASSIGN TASK")
        
        task_id = self.get_input("\nEnter task ID: ")
        
        try:
            task_id = int(task_id)
        except ValueError:
            print("\n✗ Invalid task ID.")
            self.pause()
            return
        
        task = self.tasks.get_task(task_id)
        if not task:
            print("\n✗ Task not found.")
            self.pause()
            return
        
        project = self.projects.get_project(task['project_id'])
        
        print(f"\nTask: {task['title']}")
        print(f"Current assignee: {task['assignee_name'] or 'Unassigned'}")
        
        users = self.auth.get_all_users()
        print("\nAvailable users:")
        for user in users:
            print(f"  {user['id']}: {user['username']}")
        
        assignee_input = self.get_input("\nEnter user ID (or 0 to unassign): ")
        
        try:
            assignee_id = int(assignee_input)
            if assignee_id == 0:
                assignee_id = None
        except ValueError:
            print("\n✗ Invalid user ID.")
            self.pause()
            return
        
        success, message = self.tasks.update_task(
            task_id, self.current_user['id'], project['owner_id'],
            assignee_id=assignee_id
        )
        
        print(f"\n{'✓' if success else '✗'} {message}")
        self.pause()
    
    def export_tasks(self):
        """Export project tasks to CSV."""
        self.clear_screen()
        self.print_header("EXPORT TASKS TO CSV")
        
        project_id = self.get_input("\nEnter project ID: ")
        
        try:
            project_id = int(project_id)
        except ValueError:
            print("\n✗ Invalid project ID.")
            self.pause()
            return
        
        project = self.projects.get_project(project_id)
        if not project:
            print("\n✗ Project not found.")
            self.pause()
            return
        
        csv_data = self.tasks.export_tasks_to_csv(project_id)
        
        if csv_data == "No tasks to export.":
            print(f"\n⚠ {csv_data}")
        else:
            filename = f"tasks_{project['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    f.write(csv_data)
                print(f"\n✓ Tasks exported successfully to: {filename}")
            except Exception as e:
                print(f"\n✗ Error exporting tasks: {str(e)}")
        
        self.pause()
    
    def run(self):
        """Main application loop."""
        while True:
            if not self.current_user:
                self.show_welcome()
                print("1. Login")
                print("2. Create Account")
                print("3. Exit")
                
                choice = self.get_input("\nChoose an option (1-3): ")
                
                if choice == '1':
                    if self.login_flow():
                        self.main_menu()
                elif choice == '2':
                    self.register_flow()
                elif choice == '3':
                    print("\n👋 Goodbye!")
                    sys.exit(0)
                else:
                    print("\n⚠ Invalid choice. Please try again.")
                    self.pause()
            else:
                self.main_menu()


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Application entry point."""
    try:
        app = HighCommandCLI()
        app.run()
    except KeyboardInterrupt:
        print("\n\n👋 Application interrupted. Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ An unexpected error occurred: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
