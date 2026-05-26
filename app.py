from flask import Flask, render_template, request, redirect, session, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'secret123'

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

db = SQLAlchemy(app)


class Event(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200))
    department  = db.Column(db.String(100))
    year        = db.Column(db.String(20))
    description = db.Column(db.String(100))
    filename    = db.Column(db.String(200))
    upload_date = db.Column(db.String(50))
    category    = db.Column(db.String(100))


class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(100), unique=True)
    password   = db.Column(db.String(100))
    department = db.Column(db.String(50))
    role       = db.Column(db.String(20))


with app.app_context():
    db.create_all()


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



# ── HOME PAGE (Bubble landing) ──────────────────────────────
@app.route('/')
def home():
    return "Website is live"


# ── DEPARTMENT LOGIN ────────────────────────────────────────
@app.route('/login/<department>', methods=['GET', 'POST'])
def login(department):

    error = None

    # Department credentials
    department_users = {
        'CSE': {'username': 'cse', 'password': 'cse123'},
        'ECE': {'username': 'ece', 'password': 'ece123'},
        'ISE': {'username': 'ise', 'password': 'ise123'},
        'EEE': {'username': 'eee', 'password': 'eee123'},
        'ADMIN': {'username': 'admin', 'password': 'admin123'}
    }

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        dept_data = department_users.get(department)

        if dept_data and username == dept_data['username'] and password == dept_data['password']:

            session['user'] = username
            session['department'] = department

            if department == 'ADMIN':
              return redirect('/admin-dashboard')

            else:
                return redirect('/dashboard')

        else:
            error = 'Invalid credentials'

    return render_template(
        'login.html',
        error=error,
        department=department
    )

# ── DASHBOARD ───────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    if session.get('role') == 'admin':
        all_events   = Event.query.order_by(Event.id.desc()).all()
        total_events = len(all_events)
        recent       = all_events[:5]
        departments  = db.session.query(Event.department).distinct().all()
        dept_stats   = {
            d[0]: Event.query.filter_by(department=d[0]).count()
            for d in departments
        }
        return render_template('admin_dashboard.html',
            total_events=total_events,
            recent=recent,
            dept_stats=dept_stats,
            departments=departments
        )
    else:
        dept         = session.get('department', '')
        events       = Event.query.filter_by(department=dept).order_by(Event.id.desc()).all()
        total_events = len(events)
        recent       = events[:5]
        return render_template('dashboard.html',
            events=events,
            total_events=total_events,
            recent=recent
        )

@app.route('/admin-dashboard')
def admin_dashboard():

    if 'user' not in session:
        return redirect('/')

    events = Event.query.order_by(
        Event.id.desc()
    ).all()

    total_events = Event.query.count()

    departments = db.session.query(
        Event.department
    ).distinct().all()

    recent = Event.query.order_by(
        Event.id.desc()
    ).limit(5).all()
    
    dept_stats = {
        d[0]: Event.query.filter_by(department=d[0]).count()
        for d in departments
    }
    return render_template(
        'admin_dashboard.html',
        events=events,
        total_events=total_events,
        departments=departments,
        dept_stats=dept_stats,
        recent=recent
    )

# ── UPLOAD ──────────────────────────────────────────────────
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'user' not in session:
        return redirect('/')
    success = None
    error   = None
    if request.method == 'POST':
        category    = request.form['category']
        title       = request.form['title']
        department  = session.get('department')
        year        = request.form['year']
        description = request.form['description']
        file        = request.files['file']

        if not title or not department or not year:
            error = 'Please fill all required fields.'
        elif file and allowed_file(file.filename):
            filename  = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            filename  = f"{timestamp}_{filename}"
            filepath  = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            new_event = Event(
                title=title,
                department=department,
                year=year,
                description=description,
                filename=filename,
                upload_date=datetime.now().strftime('%d-%m-%Y'),
                category=category
            )
            db.session.add(new_event)
            db.session.commit()
            return redirect('/dashboard')
        else:
            error = 'Invalid file. Only PDF, JPG, PNG allowed.'
    return render_template('upload.html', success=success, error=error)


# ── EVENTS ──────────────────────────────────────────────────
@app.route('/events')
def events():
    if 'user' not in session:
        return redirect('/')

    search          = request.args.get('search', '')
    dept_filter     = request.args.get('department', '')
    year_filter     = request.args.get('year', '')
    category_filter = request.args.get('category', '')
    department      = session.get('department')

    if department == 'ADMIN':
        query = Event.query
    else:
        query = Event.query.filter_by(department=department)

    if search:
        query = query.filter(Event.title.contains(search))
    if dept_filter:
        query = query.filter(Event.department == dept_filter)
    if year_filter:
        query = query.filter(Event.year == year_filter)
    if category_filter:
        query = query.filter(Event.category == category_filter)

    events      = query.order_by(Event.id.desc()).all()
    departments = db.session.query(Event.department).distinct().all()
    years       = db.session.query(Event.year).distinct().all()

    return render_template('events.html',
        events=events,
        departments=departments,
        years=years,
        search=search,
        dept_filter=dept_filter,
        year_filter=year_filter,
        category_filter=category_filter
    )


# ── DELETE ──────────────────────────────────────────────────
@app.route('/delete/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'user' not in session:
        return redirect('/')
    event    = Event.query.get_or_404(event_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], event.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(event)
    db.session.commit()
    return redirect('/dashboard')


# ── SERVE UPLOADED FILES ────────────────────────────────────
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ── LOGOUT ──────────────────────────────────────────────────
@app.route('/logout')
def logout():
    session.pop('user', None)
    session.pop('department', None)
    session.pop('role', None)
    return redirect('/')


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)