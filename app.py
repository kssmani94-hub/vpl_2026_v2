import os
import csv
from io import StringIO
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# --- Configuration ---
app.config['SECRET_KEY'] = 'Siva2026_VPL_Secure_Key'
# Absolute path helps prevent 'Database not found' errors on local machines
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///vpl_database.db')
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='editor')

class ActivityLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    action = db.Column(db.String(200))
    target_id = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vpl_id = db.Column(db.String(20), unique=True)
    full_name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer) 
    phone = db.Column(db.String(15), unique=True, nullable=False)
    level = db.Column(db.String(50))
    ch_mobile = db.Column(db.String(15))
    ch_name = db.Column(db.String(100))
    current_team = db.Column(db.String(100))
    prev_team = db.Column(db.String(100))
    role = db.Column(db.String(50))
    style = db.Column(db.String(100))
    photo = db.Column(db.String(200))
    shirt_name = db.Column(db.String(50))
    shirt_number = db.Column(db.Integer)
    shirt_size = db.Column(db.String(10))
    sleeves = db.Column(db.String(20))
    payment_method = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Pending Approval')
    payment_screenshot = db.Column(db.String(200))

# Create database and tables automatically
with app.app_context():
    db.create_all()

# --- Helper for Logging ---
def log_activity(action, target_id="N/A"):
    current_user = session.get('username', 'System/Guest')
    new_log = ActivityLog(username=current_user, action=action, target_id=target_id)
    db.session.add(new_log)
    db.session.commit()

# --- Public Routes ---

@app.route('/')
def home():
    # Total slots updated to 200
    total_slots = 200 
    registered_count = Player.query.count()
    remaining = total_slots - registered_count
    return render_template('index.html', remaining=remaining, total_slots=total_slots)

@app.route('/register', methods=['GET', 'POST'])
def register():
    # Registration Deadline
    if datetime.now() > datetime(2026, 1, 24, 23, 59):
        flash('Registration closed on 24th Jan 2026.', 'danger')
        return redirect(url_for('home'))

    # Capacity Check
    if Player.query.count() >= 200:
        flash('Registration is full!', 'warning')
        return redirect(url_for('home'))

    if request.method == 'POST':
        phone = request.form.get('phone')
        if Player.query.filter_by(phone=phone).first():
            flash('This mobile number is already registered!', 'danger')
            return redirect(url_for('register'))
        
        # ID generation logic (Gap filling)
        existing_numbers = [int(p.vpl_id.split('-')[1]) for p in Player.query.all() if p.vpl_id and '-' in p.vpl_id]
        new_id_num = 1
        while new_id_num in existing_numbers:
            new_id_num += 1
        v_id = f"VPL-{new_id_num:03d}"
        
        file = request.files.get('photo')
        photo_fn = f"{v_id}.jpg"
        if file: 
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], photo_fn))
        else:
            photo_fn = 'default.jpg'

        new_p = Player(
            vpl_id=v_id, full_name=request.form.get('full_name'), 
            age=request.form.get('age'), phone=phone, level=request.form.get('level'), 
            ch_mobile=request.form.get('ch_mobile'), ch_name=request.form.get('ch_name'),
            current_team=request.form.get('current_team'), 
            prev_team=request.form.get('prev_team'), 
            role=request.form.get('role'), style=request.form.get('style'), 
            photo=photo_fn, shirt_name=request.form.get('shirt_name'), 
            shirt_number=request.form.get('shirt_number'), shirt_size=request.form.get('shirt_size'), 
            sleeves=request.form.get('sleeves')
        )
        db.session.add(new_p)
        db.session.commit()
        return redirect(url_for('payment', player_id=new_p.id))

    return render_template('register.html')

@app.route('/payment/<int:player_id>', methods=['GET', 'POST'])
def payment(player_id):
    player = Player.query.get_or_404(player_id)
    if request.method == 'POST':
        method = request.form.get('payment_method')
        player.payment_method = method
        if method == 'UPI':
            file = request.files.get('screenshot')
            if file:
                pay_name = f"PAY_{player.vpl_id}.jpg"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], pay_name))
                player.payment_screenshot = pay_name
        
        player.status = 'Pending Approval'
        db.session.commit()
        return render_template('payment.html', player=player, success=True)
    return render_template('payment.html', player=player, success=False)

@app.route('/total_players')
def total_players():
    players_list = Player.query.order_by(Player.vpl_id).all()
    return render_template('total_players.html', players=players_list)

# --- Admin Section ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        # Super-admin check
        if username == 'admin' and password == 'Siva2124':
            session['admin_logged_in'] = True
            session['username'] = 'admin'
            log_activity("Admin logged in")
            return redirect(url_for('players'))
        # Regular committee member check
        elif user and check_password_hash(user.password, password):
            session['admin_logged_in'] = True
            session['username'] = user.username
            log_activity("Committee member logged in")
            return redirect(url_for('players'))
        flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/players')
def players():
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    return render_template('players.html', players=Player.query.all())

@app.route('/edit_player/<int:id>', methods=['GET', 'POST'])
def edit_player(id):
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    player = Player.query.get_or_404(id)
    if request.method == 'POST':
        player.full_name = request.form.get('full_name')
        player.status = request.form.get('status')
        db.session.commit()
        log_activity("Edited player details", player.vpl_id)
        flash('Player updated successfully!', 'success')
        return redirect(url_for('players'))
    return render_template('edit_player.html', player=player)

@app.route('/delete_player/<int:id>', methods=['POST'])
def delete_player(id):
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    player = Player.query.get_or_404(id)
    v_id = player.vpl_id
    db.session.delete(player)
    db.session.commit()
    log_activity("Deleted player profile", v_id)
    flash('Player removed from league.', 'success')
    return redirect(url_for('players'))

# --- User Management (Super Admin Only) ---

@app.route('/admin/manage_users')
def manage_users():
    if not session.get('admin_logged_in') or session.get('username') != 'admin':
        return redirect(url_for('login'))
    return render_template('manage_users.html', users=User.query.all())

@app.route('/admin/create_user', methods=['GET', 'POST'])
def create_user():
    if not session.get('admin_logged_in') or session.get('username') != 'admin':
        return redirect(url_for('players'))

    if request.method == 'POST':
        username = request.form.get('new_username')
        password = request.form.get('new_password')
        role = request.form.get('role')

        if User.query.filter_by(username=username).first():
            flash('Username already exists!', 'warning')
        else:
            hashed_pw = generate_password_hash(password)
            new_user = User(username=username, password=hashed_pw, role=role)
            db.session.add(new_user)
            db.session.commit()
            log_activity(f"Created user: {username}")
            flash('User created successfully!', 'success')
            return redirect(url_for('manage_users'))
    return render_template('create_user.html')

@app.route('/admin/delete_user/<int:id>', methods=['POST'])
def delete_user(id):
    if not session.get('admin_logged_in') or session.get('username') != 'admin':
        return redirect(url_for('login'))
    
    user_to_delete = User.query.get_or_404(id)
    if user_to_delete.username == 'admin':
        flash("Master Admin cannot be deleted!", "danger")
    else:
        username = user_to_delete.username
        db.session.delete(user_to_delete)
        db.session.commit()
        log_activity(f"Deleted committee member: {username}")
        flash("User removed successfully.", "success")
    return redirect(url_for('manage_users'))

# --- Data Management ---

@app.route('/export_players')
def export_players():
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    players_list = Player.query.all()
    si = StringIO()
    cw = csv.writer(si)
    
    # Header Row with all registration fields
    cw.writerow([
        'VPL ID', 'Full Name', 'Age', 'Phone', 'Cric Level', 
        'CH Name', 'CH Mobile', 'Current Team', 'Previous VPL Team', 
        'Role', 'Playing Style', 'Jersey Name', 'Jersey No', 
        'Jersey Size', 'Sleeves', 'Payment Method', 'Status'
    ])
    
    for p in players_list:
        cw.writerow([
            p.vpl_id, p.full_name, p.age, p.phone, p.level, 
            p.ch_name, p.ch_mobile, p.current_team, p.prev_team, 
            p.role, p.style, p.shirt_name, p.shirt_number, 
            p.shirt_size, p.sleeves, p.payment_method, p.status
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=VPL_Full_Export_2026.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/activity_logs')
def activity_logs():
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    return render_template('logs.html', logs=logs)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)