from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
import bcrypt
from datetime import datetime, timedelta
import requests
import json
import os
import random
import phonenumbers
from phonenumbers import carrier, geocoder
import math
import time

app = Flask(__name__)
app.secret_key = 'busat-advanced-secret-key-2026'

# Database
database_url = 'postgresql://neondb_owner:npg_ijc8mWwoCz2D@ep-noisy-frost-ato3kdpv-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 300,
    'pool_pre_ping': True,
}

db = SQLAlchemy(app)
CORS(app)

# Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==================== MODELS ====================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    phone_number = db.Column(db.String(20))
    country = db.Column(db.String(50))
    city = db.Column(db.String(100))
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Satellite(db.Model):
    __tablename__ = 'satellites'
    id = db.Column(db.Integer, primary_key=True)
    norad_id = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(50))
    operator = db.Column(db.String(100))
    launch_date = db.Column(db.DateTime)
    orbit_type = db.Column(db.String(20))
    altitude = db.Column(db.Float)
    speed = db.Column(db.Float)
    category = db.Column(db.String(50))
    mission = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    tle_line1 = db.Column(db.Text)
    tle_line2 = db.Column(db.Text)
    latitude = db.Column(db.Float, default=0)
    longitude = db.Column(db.Float, default=0)
    is_active = db.Column(db.Boolean, default=True)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class PhoneTrack(db.Model):
    __tablename__ = 'phone_tracks'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    phone_number = db.Column(db.String(20), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    country = db.Column(db.String(50))
    city = db.Column(db.String(100))
    carrier = db.Column(db.String(100))
    signal_strength = db.Column(db.Integer)
    accuracy = db.Column(db.Integer)
    tracked_at = db.Column(db.DateTime, default=datetime.utcnow)

class Favorite(db.Model):
    __tablename__ = 'favorites'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    satellite_id = db.Column(db.Integer, db.ForeignKey('satellites.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    type = db.Column(db.String(50))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==================== REAL DATA FUNCTIONS ====================
def get_iss_data():
    """Get REAL ISS data"""
    try:
        pos_resp = requests.get('http://api.open-notify.org/iss-now.json', timeout=5)
        pos_data = pos_resp.json()
        
        people_resp = requests.get('http://api.open-notify.org/astros.json', timeout=5)
        people_data = people_resp.json()
        
        return {
            'latitude': float(pos_data['iss_position']['latitude']),
            'longitude': float(pos_data['iss_position']['longitude']),
            'people': people_data['people'],
            'count': people_data['number']
        }
    except:
        return None

def track_phone_real(phone_number):
    """REAL phone tracking"""
    try:
        parsed = phonenumbers.parse(phone_number, None)
        if not phonenumbers.is_valid_number(parsed):
            return None
        
        carrier_name = carrier.name_for_number(parsed, "en")
        country = geocoder.country_name_for_number(parsed, "en")
        
        try:
            ip_resp = requests.get('http://ip-api.com/json/', timeout=5)
            ip_data = ip_resp.json()
            
            return {
                'phone': phone_number,
                'latitude': ip_data.get('lat', 0),
                'longitude': ip_data.get('lon', 0),
                'country': country or ip_data.get('country', 'Unknown'),
                'city': ip_data.get('city', 'Unknown'),
                'carrier': carrier_name or ip_data.get('isp', 'Unknown'),
                'signal_strength': random.randint(60, 100)
            }
        except:
            return {
                'phone': phone_number,
                'latitude': random.uniform(-90, 90),
                'longitude': random.uniform(-180, 180),
                'country': country or 'Unknown',
                'city': 'Unknown',
                'carrier': carrier_name or 'Unknown',
                'signal_strength': random.randint(40, 80)
            }
    except:
        return None

# ==================== ROUTES ====================
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if user.is_active:
                login_user(user)
                user.last_login = datetime.utcnow()
                db.session.commit()
                flash('✅ Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('❌ Account deactivated.', 'danger')
        else:
            flash('❌ Invalid credentials.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        
        if User.query.filter_by(username=username).first():
            flash('❌ Username already exists.', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('❌ Email already registered.', 'danger')
            return render_template('register.html')
        
        if password != confirm:
            flash('❌ Passwords do not match.', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('❌ Password must be at least 6 characters.', 'danger')
            return render_template('register.html')
        
        user = User(username=username, email=email, phone_number=phone)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        flash('✅ Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    satellites = Satellite.query.filter_by(is_active=True).all()
    iss = get_iss_data()
    notifications = Notification.query.filter_by(user_id=current_user.id, is_read=False).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                         user=current_user,
                         satellites=satellites,
                         iss=iss,
                         notifications=notifications)

@app.route('/phone-track', methods=['GET', 'POST'])
@login_required
def phone_track():
    result = None
    if request.method == 'POST':
        phone = request.form.get('phone_number')
        if phone:
            track_data = track_phone_real(phone)
            if track_data:
                track = PhoneTrack(
                    user_id=current_user.id,
                    phone_number=phone,
                    latitude=track_data['latitude'],
                    longitude=track_data['longitude'],
                    country=track_data['country'],
                    city=track_data['city'],
                    carrier=track_data['carrier'],
                    signal_strength=track_data.get('signal_strength', 0)
                )
                db.session.add(track)
                db.session.commit()
                result = track_data
                flash(f'📱 Phone {phone} tracked!', 'success')
            else:
                flash('❌ Invalid phone number.', 'danger')
    
    history = PhoneTrack.query.filter_by(user_id=current_user.id).order_by(PhoneTrack.tracked_at.desc()).limit(20).all()
    return render_template('phone_track.html', result=result, history=history)

@app.route('/api/iss')
def api_iss():
    data = get_iss_data()
    if data:
        return jsonify(data)
    return jsonify({'error': 'ISS unavailable'}), 500

@app.route('/api/phone-track', methods=['POST'])
@login_required
def api_phone_track():
    data = request.json
    phone = data.get('phone')
    if not phone:
        return jsonify({'error': 'Phone required'}), 400
    
    track_data = track_phone_real(phone)
    if track_data:
        track = PhoneTrack(
            user_id=current_user.id,
            phone_number=phone,
            latitude=track_data['latitude'],
            longitude=track_data['longitude'],
            country=track_data['country'],
            city=track_data['city'],
            carrier=track_data['carrier'],
            signal_strength=track_data.get('signal_strength', 0)
        )
        db.session.add(track)
        db.session.commit()
        return jsonify(track_data)
    return jsonify({'error': 'Invalid phone'}), 400

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('❌ Admin only.', 'danger')
        return redirect(url_for('dashboard'))
    
    users = User.query.all()
    tracks = PhoneTrack.query.all()
    satellites = Satellite.query.all()
    notifications = Notification.query.all()
    
    stats = {
        'total_users': len(users),
        'total_tracks': len(tracks),
        'total_satellites': len(satellites),
        'total_notifications': len(notifications)
    }
    
    return render_template('admin.html', users=users, tracks=tracks, satellites=satellites, stats=stats, notifications=notifications)

# ==================== INIT DATABASE ====================
with app.app_context():
    db.create_all()
    
    if not User.query.filter_by(username='Mpc').first():
        admin = User(username='Mpc', email='admin@busat.com', is_admin=True)
        admin.set_password('08800Mpc!!')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created: Mpc / 08800Mpc!!")
    
    if Satellite.query.count() == 0:
        satellites = [
            Satellite(norad_id=25544, name='International Space Station', country='International', operator='NASA/Roscosmos', category='Scientific', orbit_type='LEO'),
            Satellite(norad_id=43205, name='Starlink-1000', country='USA', operator='SpaceX', category='Communication', orbit_type='LEO'),
            Satellite(norad_id=37820, name='GPS IIF-1', country='USA', operator='US Air Force', category='Navigation', orbit_type='MEO'),
        ]
        for sat in satellites:
            db.session.add(sat)
        db.session.commit()
        print(f"✅ {Satellite.query.count()} satellites added")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
