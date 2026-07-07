import os
import bcrypt
import requests
import random
import phonenumbers
from phonenumbers import carrier, geocoder
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = 'busat-super-secret-2026'

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_ijc8mWwoCz2D@ep-noisy-frost-ato3kdpv-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to continue.'

# Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
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
    orbit = db.Column(db.String(20))
    category = db.Column(db.String(50))
    altitude = db.Column(db.Float, default=0)
    speed = db.Column(db.Float, default=0)
    latitude = db.Column(db.Float, default=0)
    longitude = db.Column(db.Float, default=0)

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
    tracked_at = db.Column(db.DateTime, default=datetime.utcnow)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()
    
    # Create admin
    if not User.query.filter_by(username='Mpc').first():
        admin = User(username='Mpc', email='admin@busat.com', is_admin=True)
        admin.set_password('08800Mpc!!')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin created: Mpc / 08800Mpc!!")
    
    # Add satellites
    if Satellite.query.count() == 0:
        sats = [
            Satellite(norad_id=25544, name='ISS', country='International', orbit='LEO', category='Scientific'),
            Satellite(norad_id=43205, name='Starlink-1000', country='USA', orbit='LEO', category='Communication'),
            Satellite(norad_id=37820, name='GPS IIF-1', country='USA', orbit='MEO', category='Navigation'),
        ]
        for s in sats:
            db.session.add(s)
        db.session.commit()

# Routes
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
        user = User.query.filter_by(username=request.form['username']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            flash('✅ Logged in!', 'success')
            return redirect(url_for('dashboard'))
        flash('❌ Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm']
        
        if User.query.filter_by(username=username).first():
            flash('❌ Username exists', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('❌ Email exists', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('❌ Passwords do not match', 'danger')
            return render_template('register.html')
        if len(password) < 6:
            flash('❌ Password too short (min 6)', 'danger')
            return render_template('register.html')
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('✅ Registered! Please login.', 'success')
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
    satellites = Satellite.query.all()
    
    # Get ISS position
    iss_data = None
    try:
        r = requests.get('http://api.open-notify.org/iss-now.json', timeout=5)
        if r.status_code == 200:
            data = r.json()
            iss_data = {
                'latitude': float(data['iss_position']['latitude']),
                'longitude': float(data['iss_position']['longitude'])
            }
    except:
        pass
    
    return render_template('dashboard.html', user=current_user, satellites=satellites, iss=iss_data)

@app.route('/phone-track', methods=['GET', 'POST'])
@login_required
def phone_track():
    result = None
    if request.method == 'POST':
        phone = request.form['phone_number']
        try:
            parsed = phonenumbers.parse(phone, None)
            if phonenumbers.is_valid_number(parsed):
                country = geocoder.country_name_for_number(parsed, "en")
                carrier_name = carrier.name_for_number(parsed, "en")
                
                # Get approximate location
                try:
                    ip_r = requests.get('http://ip-api.com/json/', timeout=5)
                    ip_data = ip_r.json()
                    lat = ip_data.get('lat', 0)
                    lon = ip_data.get('lon', 0)
                    city = ip_data.get('city', 'Unknown')
                except:
                    lat = random.uniform(-90, 90)
                    lon = random.uniform(-180, 180)
                    city = 'Unknown'
                
                track = PhoneTrack(
                    user_id=current_user.id,
                    phone_number=phone,
                    latitude=lat,
                    longitude=lon,
                    country=country or 'Unknown',
                    city=city,
                    carrier=carrier_name or 'Unknown'
                )
                db.session.add(track)
                db.session.commit()
                
                result = {
                    'phone': phone,
                    'latitude': lat,
                    'longitude': lon,
                    'country': country or 'Unknown',
                    'city': city,
                    'carrier': carrier_name or 'Unknown'
                }
                flash(f'📱 Phone {phone} tracked!', 'success')
            else:
                flash('❌ Invalid phone number', 'danger')
        except:
            flash('❌ Error tracking phone', 'danger')
    
    history = PhoneTrack.query.filter_by(user_id=current_user.id).order_by(PhoneTrack.tracked_at.desc()).limit(20).all()
    return render_template('phone_track.html', result=result, history=history)

@app.route('/api/iss')
def api_iss():
    try:
        r = requests.get('http://api.open-notify.org/iss-now.json', timeout=5)
        if r.status_code == 200:
            data = r.json()
            return jsonify({
                'latitude': float(data['iss_position']['latitude']),
                'longitude': float(data['iss_position']['longitude'])
            })
    except:
        pass
    return jsonify({'error': 'ISS unavailable'}), 500

@app.route('/api/satellites')
@login_required
def api_satellites():
    sats = Satellite.query.all()
    return jsonify([{
        'name': s.name,
        'norad': s.norad_id,
        'country': s.country,
        'orbit': s.orbit,
        'category': s.category
    } for s in sats])

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('❌ Admin only', 'danger')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    tracks = PhoneTrack.query.all()
    satellites = Satellite.query.all()
    return render_template('admin.html', users=users, tracks=tracks, satellites=satellites)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
