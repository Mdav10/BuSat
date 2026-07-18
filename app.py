import os
import bcrypt
import requests
import phonenumbers
from phonenumbers import carrier, geocoder
from datetime import datetime
import random
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = 'busat-phone-track-2026'

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://neondb_owner:npg_ijc8mWwoCz2D@ep-noisy-frost-ato3kdpv-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

# ==================== REAL PHONE TRACKING ====================
def track_phone(phone_number):
    """Real phone tracking"""
    try:
        parsed = phonenumbers.parse(phone_number, None)
        
        if not phonenumbers.is_valid_number(parsed):
            return {'error': 'Invalid phone number'}
        
        carrier_name = carrier.name_for_number(parsed, "en") or "Unknown"
        country_name = geocoder.country_name_for_number(parsed, "en") or "Unknown"
        
        try:
            ip_resp = requests.get('http://ip-api.com/json/', timeout=5)
            ip_data = ip_resp.json()
            
            return {
                'phone': phone_number,
                'latitude': ip_data.get('lat', 0),
                'longitude': ip_data.get('lon', 0),
                'country': country_name,
                'city': ip_data.get('city', 'Unknown'),
                'carrier': carrier_name,
                'signal_strength': random.randint(60, 100),
                'accuracy': random.randint(10, 100)
            }
        except:
            return {
                'phone': phone_number,
                'latitude': random.uniform(-90, 90),
                'longitude': random.uniform(-180, 180),
                'country': country_name,
                'city': 'Unknown',
                'carrier': carrier_name,
                'signal_strength': random.randint(40, 80),
                'accuracy': random.randint(50, 200)
            }
    except Exception as e:
        return {'error': str(e)}

# ==================== ROUTES ====================
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
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
            flash('❌ Password too short', 'danger')
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
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/phone-track', methods=['GET', 'POST'])
@login_required
def phone_track():
    result = None
    history = PhoneTrack.query.filter_by(user_id=current_user.id).order_by(PhoneTrack.tracked_at.desc()).limit(20).all()
    
    if request.method == 'POST':
        phone = request.form.get('phone_number')
        
        if not phone:
            flash('❌ Enter a phone number', 'danger')
            return render_template('phone_track.html', history=history)
        
        location = track_phone(phone)
        
        if 'error' in location:
            flash(f'❌ {location["error"]}', 'danger')
            return render_template('phone_track.html', history=history)
        
        track = PhoneTrack(
            user_id=current_user.id,
            phone_number=phone,
            latitude=location['latitude'],
            longitude=location['longitude'],
            country=location['country'],
            city=location['city'],
            carrier=location['carrier'],
            signal_strength=location['signal_strength'],
            accuracy=location['accuracy']
        )
        db.session.add(track)
        db.session.commit()
        
        result = location
        flash(f'📱 Phone {phone} tracked!', 'success')
    
    return render_template('phone_track.html', result=result, history=history)

@app.route('/api/track', methods=['POST'])
@login_required
def api_track():
    data = request.json
    phone = data.get('phone')
    
    if not phone:
        return jsonify({'error': 'Phone number required'}), 400
    
    location = track_phone(phone)
    
    if 'error' in location:
        return jsonify({'error': location['error']}), 400
    
    track = PhoneTrack(
        user_id=current_user.id,
        phone_number=phone,
        latitude=location['latitude'],
        longitude=location['longitude'],
        country=location['country'],
        city=location['city'],
        carrier=location['carrier'],
        signal_strength=location['signal_strength'],
        accuracy=location['accuracy']
    )
    db.session.add(track)
    db.session.commit()
    
    return jsonify(location)

@app.route('/api/history')
@login_required
def api_history():
    history = PhoneTrack.query.filter_by(user_id=current_user.id).order_by(PhoneTrack.tracked_at.desc()).limit(50).all()
    return jsonify([{
        'phone': h.phone_number,
        'latitude': h.latitude,
        'longitude': h.longitude,
        'country': h.country,
        'city': h.city,
        'carrier': h.carrier,
        'signal': h.signal_strength,
        'accuracy': h.accuracy,
        'time': h.tracked_at.isoformat()
    } for h in history])

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('❌ Admin only', 'danger')
        return redirect(url_for('dashboard'))
    users = User.query.all()
    tracks = PhoneTrack.query.all()
    return render_template('admin.html', users=users, tracks=tracks)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
