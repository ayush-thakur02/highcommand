#!/usr/bin/env python3
"""
HighCommand Web Application - Flask-based brutalist UI

A minimal brutalist web interface for the project management system.
Uses Flask with session-based authentication and stark white design.

Usage:
    python web_app.py

Then navigate to: http://localhost:5000
"""

from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
from datetime import datetime
import secrets

# Import backend modules from app.py
from app import Database, AuthManager, ProjectManager, TaskManager

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['SESSION_COOKIE_HTTPONLY'] = True

# Initialize backend
db = Database()
auth = AuthManager(db)
projects = ProjectManager(db)
tasks = TaskManager(db)


# ============================================================================
# DECORATORS
# ============================================================================

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/')
def index():
    """Landing page - redirects to dashboard or login."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = auth.authenticate(username, password)
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash(f'Welcome back, {user["username"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        if password != password_confirm:
            flash('Passwords do not match.', 'error')
        else:
            success, message = auth.create_user(username, password)
            if success:
                flash(message, 'success')
                return redirect(url_for('login'))
            else:
                flash(message, 'error')
    
    return render_template('register.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user."""
    username = session.get('username', 'User')
    session.clear()
    flash(f'Goodbye, {username}!', 'success')
    return redirect(url_for('login'))


# ============================================================================
# DASHBOARD
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard - shows stats for projects user is part of."""
    user_id = session['user_id']
    
    # Get projects where user is a member (including owner)
    user_projects = projects.list_user_projects(user_id)
    
    # Filter in-progress projects
    in_progress_projects = [p for p in user_projects if p.get('status') == 'in-progress']
    
    # Get tasks assigned to the user that are todo or in-progress
    user_tasks_todo = tasks.get_user_assigned_tasks(user_id, 'todo')
    user_tasks_in_progress = tasks.get_user_assigned_tasks(user_id, 'in-progress')
    
    stats = {
        'total_projects': len(in_progress_projects),
        'tasks_todo': len(user_tasks_todo),
        'tasks_in_progress': len(user_tasks_in_progress)
    }
    
    return render_template('dashboard.html', stats=stats)


# ============================================================================
# PROJECT ROUTES
# ============================================================================

@app.route('/projects')
@login_required
def project_list():
    """List all projects."""
    all_projects = projects.list_projects()
    user_id = session['user_id']
    
    # Add membership status for each project
    for project in all_projects:
        project['is_member'] = projects.is_member(project['id'], user_id)
        project['is_owner'] = project['owner_id'] == user_id
    
    return render_template('projects.html', projects=all_projects, view='all')


@app.route('/projects/mine')
@login_required
def my_projects():
    """List user's projects (where they are a member or owner)."""
    user_projects = projects.list_user_projects(session['user_id'])
    
    # Add ownership status
    for project in user_projects:
        project['is_owner'] = project['owner_id'] == session['user_id']
    
    return render_template('projects.html', projects=user_projects, view='mine')


@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def project_new():
    """Create new project."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        vm_ip = request.form.get('vm_ip', '').strip()
        
        success, message = projects.create_project(name, description, session['user_id'], vm_ip)
        if success:
            flash(message, 'success')
            return redirect(url_for('my_projects'))
        else:
            flash(message, 'error')
    
    return render_template('project_form.html', action='Create')


@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    """View project details."""
    project = projects.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('project_list'))
    
    # Check if user is a member
    user_id = session['user_id']
    is_member = projects.is_member(project_id, user_id)
    is_owner = project['owner_id'] == user_id
    
    # Get project members
    members = projects.get_project_members(project_id)
    
    # Get pending requests (only for owner)
    pending_requests = []
    if is_owner:
        pending_requests = projects.get_pending_requests(project_id)
    
    # Get project tasks (only for members)
    project_tasks = []
    task_stats = {'total': 0, 'todo': 0, 'in_progress': 0, 'done': 0}
    
    if is_member:
        project_tasks = tasks.list_tasks(project_id)
        task_stats = {
            'total': len(project_tasks),
            'todo': sum(1 for t in project_tasks if t['status'] == 'todo'),
            'in_progress': sum(1 for t in project_tasks if t['status'] == 'in-progress'),
            'done': sum(1 for t in project_tasks if t['status'] == 'done')
        }
    
    return render_template('project_detail.html', 
                         project=project, 
                         tasks=project_tasks,
                         task_stats=task_stats,
                         is_owner=is_owner,
                         is_member=is_member,
                         members=members,
                         pending_requests=pending_requests)


@app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def project_edit(project_id):
    """Edit project."""
    project = projects.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('project_list'))
    
    if project['owner_id'] != session['user_id']:
        flash('Only the project owner can edit this project.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', '').strip()
        vm_ip = request.form.get('vm_ip', '').strip()
        
        success, message = projects.update_project(
            project_id, session['user_id'], name, description, vm_ip
        )
        if success and status:
            success2, message2 = projects.update_project_status(project_id, session['user_id'], status)
            if not success2:
                flash(message2, 'error')
        
        if success:
            flash('Project updated successfully!', 'success')
            return redirect(url_for('project_detail', project_id=project_id))
        else:
            flash(message, 'error')
    
    return render_template('project_form.html', 
                         action='Edit', 
                         project=project)


@app.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def project_delete(project_id):
    """Delete project."""
    success, message = projects.delete_project(project_id, session['user_id'])
    if success:
        flash(message, 'success')
        return redirect(url_for('my_projects'))
    else:
        flash(message, 'error')
        return redirect(url_for('project_detail', project_id=project_id))


@app.route('/projects/<int:project_id>/join', methods=['POST'])
@login_required
def project_join_request(project_id):
    """Request to join a project."""
    success, message = projects.request_to_join(project_id, session['user_id'])
    flash(message, 'success' if success else 'error')
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/projects/<int:project_id>/requests/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_join_request(project_id, request_id):
    """Approve a join request."""
    success, message = projects.approve_request(request_id, session['user_id'])
    flash(message, 'success' if success else 'error')
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/projects/<int:project_id>/requests/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_join_request(project_id, request_id):
    """Reject a join request."""
    success, message = projects.reject_request(request_id, session['user_id'])
    flash(message, 'success' if success else 'error')
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/projects/<int:project_id>/members/<int:user_id>/remove', methods=['POST'])
@login_required
def remove_member(project_id, user_id):
    """Remove a member from a project."""
    success, message = projects.remove_member(project_id, user_id, session['user_id'])
    flash(message, 'success' if success else 'error')
    return redirect(url_for('project_members', project_id=project_id))


@app.route('/projects/<int:project_id>/members')
@login_required
def project_members(project_id):
    """View project team members."""
    project = projects.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('project_list'))
    
    user_id = session['user_id']
    is_member = projects.is_member(project_id, user_id)
    is_owner = project['owner_id'] == user_id
    
    if not is_member:
        flash('Only project members can view the team.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    members = projects.get_project_members(project_id)
    
    # Get pending requests (only for owner)
    pending_requests = []
    if is_owner:
        pending_requests = projects.get_pending_requests(project_id)
    
    return render_template('project_members.html',
                         project=project,
                         members=members,
                         pending_requests=pending_requests,
                         is_owner=is_owner)


# ============================================================================
# TASK ROUTES
# ============================================================================

@app.route('/tasks/mine')
@login_required
def my_tasks():
    """View all tasks assigned to the user."""
    user_id = session['user_id']
    
    # Get tasks for all statuses
    todo_tasks = tasks.get_user_assigned_tasks(user_id, 'todo')
    in_progress_tasks = tasks.get_user_assigned_tasks(user_id, 'in-progress')
    done_tasks = tasks.get_user_assigned_tasks(user_id, 'done')
    
    all_tasks = todo_tasks + in_progress_tasks + done_tasks
    
    return render_template('my_tasks.html', 
                         tasks=all_tasks,
                         todo_count=len(todo_tasks),
                         in_progress_count=len(in_progress_tasks))


@app.route('/projects/<int:project_id>/tasks/new', methods=['GET', 'POST'])
@login_required
def task_new(project_id):
    """Create new task."""
    project = projects.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('project_list'))
    
    # Check if user is a member
    if not projects.is_member(project_id, session['user_id']):
        flash('Only project members can create tasks.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', 'todo')
        priority = request.form.get('priority', 'medium')
        due_date = request.form.get('due_date', '').strip()
        
        # Get multiple assignees
        assignee_ids = request.form.getlist('assignee_ids')
        assignee_ids = [int(aid) for aid in assignee_ids if aid]
        
        due_date = due_date if due_date else None
        
        success, message = tasks.create_task(
            project_id, title, description, status, priority,
            due_date, assignee_ids, session['user_id']
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('project_detail', project_id=project_id))
        else:
            flash(message, 'error')
    
    # Get project members for assignment
    members = projects.get_project_members(project_id)
    
    return render_template('task_form.html', 
                         action='Create',
                         project=project,
                         members=members,
                         statuses=tasks.VALID_STATUSES,
                         priorities=tasks.VALID_PRIORITIES)


@app.route('/tasks/<int:task_id>')
@login_required
def task_detail(task_id):
    """View task details."""
    task = tasks.get_task(task_id)
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('dashboard'))
    
    project = projects.get_project(task['project_id'])
    
    # Check if user is a member of the project
    if not projects.is_member(task['project_id'], session['user_id']):
        flash('You do not have access to this task.', 'error')
        return redirect(url_for('dashboard'))
    
    can_edit = (task['creator_id'] == session['user_id'] or 
                project['owner_id'] == session['user_id'])
    
    return render_template('task_detail.html', 
                         task=task, 
                         project=project,
                         can_edit=can_edit)


@app.route('/tasks/<int:task_id>/edit', methods=['GET', 'POST'])
@login_required
def task_edit(task_id):
    """Edit task."""
    task = tasks.get_task(task_id)
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('dashboard'))
    
    project = projects.get_project(task['project_id'])
    can_edit = (task['creator_id'] == session['user_id'] or 
                project['owner_id'] == session['user_id'])
    
    if not can_edit:
        flash('You do not have permission to edit this task.', 'error')
        return redirect(url_for('task_detail', task_id=task_id))
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        status = request.form.get('status', '')
        priority = request.form.get('priority', '')
        due_date = request.form.get('due_date', '').strip()
        
        # Get multiple assignees
        assignee_ids = request.form.getlist('assignee_ids')
        assignee_ids = [int(aid) for aid in assignee_ids if aid]
        
        due_date = due_date if due_date else None
        
        success, message = tasks.update_task(
            task_id, session['user_id'], project['owner_id'],
            title=title, description=description, status=status,
            priority=priority, due_date=due_date, assignee_ids=assignee_ids
        )
        if success:
            flash(message, 'success')
            return redirect(url_for('task_detail', task_id=task_id))
        else:
            flash(message, 'error')
    
    # Get project members for assignment
    members = projects.get_project_members(task['project_id'])
    
    return render_template('task_form.html', 
                         action='Edit',
                         project=project,
                         task=task,
                         members=members,
                         statuses=tasks.VALID_STATUSES,
                         priorities=tasks.VALID_PRIORITIES)


@app.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def task_delete(task_id):
    """Delete task."""
    task = tasks.get_task(task_id)
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('dashboard'))
    
    project_id = task['project_id']
    project = projects.get_project(project_id)
    
    success, message = tasks.delete_task(task_id, session['user_id'], project['owner_id'])
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/tasks/<int:task_id>/complete', methods=['POST'])
@login_required
def task_mark_complete(task_id):
    """Mark a task as complete."""
    task = tasks.get_task(task_id)
    if not task:
        flash('Task not found.', 'error')
        return redirect(url_for('dashboard'))
    
    project = projects.get_project(task['project_id'])
    
    # Check if user can edit (is creator, project owner, or assignee)
    is_assignee = session['user_id'] in [a['id'] for a in task.get('assignees', [])]
    can_edit = (task['creator_id'] == session['user_id'] or 
                project['owner_id'] == session['user_id'] or
                is_assignee)
    
    if not can_edit:
        flash('You do not have permission to complete this task.', 'error')
        return redirect(url_for('task_detail', task_id=task_id))
    
    success, message = tasks.update_task(
        task_id, session['user_id'], project['owner_id'],
        status='done'
    )
    
    if success:
        flash('Task marked as complete!', 'success')
    else:
        flash(message, 'error')
    
    # Redirect back to the referring page
    referer = request.headers.get('Referer')
    if referer:
        return redirect(referer)
    return redirect(url_for('task_detail', task_id=task_id))


@app.route('/projects/<int:project_id>/export')
@login_required
def project_export(project_id):
    """Export project tasks to CSV."""
    project = projects.get_project(project_id)
    if not project:
        flash('Project not found.', 'error')
        return redirect(url_for('project_list'))
    
    # Check if user is a member
    if not projects.is_member(project_id, session['user_id']):
        flash('Only project members can export tasks.', 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    from flask import Response
    csv_data = tasks.export_tasks_to_csv(project_id)
    
    if csv_data == "No tasks to export.":
        flash(csv_data, 'error')
        return redirect(url_for('project_detail', project_id=project_id))
    
    filename = f"tasks_{project['name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(e):
    """404 error handler."""
    return render_template('error.html', error='404', message='Page not found'), 404


@app.errorhandler(500)
def server_error(e):
    """500 error handler."""
    return render_template('error.html', error='500', message='Internal server error'), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("  HighCommand Web Application")
    print("="*70)
    print("\n  Server starting at: http://localhost:5000")
    print("  Press CTRL+C to quit\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
