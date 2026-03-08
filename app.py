from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from flask_mail import Mail, Message
from datetime import datetime, date
from functools import wraps
import os
import random

app = Flask(__name__)
app.secret_key = 'kks_sago_factory_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kks_factory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Email Configuration (defaults, overridden at runtime from SystemConfig) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = ''
app.config['MAIL_PASSWORD'] = ''
app.config['MAIL_DEFAULT_SENDER'] = ''

mail = Mail(app)

def _load_smtp_config():
    """
    Load SMTP credentials from SystemConfig and apply them to Flask-Mail config.
    Returns (smtp_email, smtp_password).
    """
    smtp_email_obj = SystemConfig.query.filter_by(key='smtp_email').first()
    smtp_password_obj = SystemConfig.query.filter_by(key='smtp_password').first()

    smtp_email = (smtp_email_obj.value if smtp_email_obj else '').strip()
    smtp_password = (smtp_password_obj.value if smtp_password_obj else '').strip()

    # Required Gmail SMTP settings
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USE_SSL'] = False
    app.config['MAIL_USERNAME'] = smtp_email
    app.config['MAIL_PASSWORD'] = smtp_password
    app.config['MAIL_DEFAULT_SENDER'] = smtp_email
    mail.init_app(app)
    return smtp_email, smtp_password

def send_email(subject, recipients, body):
    """
    Send an email using SMTP credentials stored in SystemConfig.
    Reloads SMTP config from DB on each call to ensure settings are current.
    Returns True if email was sent, False otherwise.
    """
    try:
        smtp_email, smtp_password = _load_smtp_config()

        if not smtp_email or not smtp_password:
            app.logger.warning(
                "[EMAIL] SMTP credentials not configured. smtp_email present=%s, smtp_password present=%s",
                bool(smtp_email), bool(smtp_password)
            )
            return False

        # Keep Flask-Mail extension in sync with updated app config.
        to_recipients = recipients if isinstance(recipients, list) else [recipients]
        to_recipients = [r.strip() for r in to_recipients if r and r.strip()]
        if not to_recipients:
            app.logger.warning("[EMAIL] No valid recipient email provided. Raw recipients=%s", recipients)
            return False

        msg = Message(
            subject=subject,
            recipients=to_recipients,
            body=body,
            sender=smtp_email
        )

        app.logger.info("[EMAIL] Sending to=%s subject=%s smtp_user=%s", to_recipients, subject, smtp_email)
        mail.send(msg)
        app.logger.info("[EMAIL] Email sent successfully to=%s", to_recipients)
        return True

    except Exception as e:
        print("EMAIL ERROR:", e)
        import traceback
        traceback.print_exc()
        return False
db = SQLAlchemy(app)

# =============================================================================
# MODELS
# =============================================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    # FEATURE 1: role column added
    role = db.Column(db.String(20), default='admin')  # 'admin' or 'manager'

class ProducerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)  # Packets
    packet_size = db.Column(db.Float, default=25.0)  # Kg per packet
    price_per_packet = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    address = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending')  # Pending, Approved, Rejected, Paid

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(50), unique=True)
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(10))

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(200), nullable=False)

class Production(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    input_qty = db.Column(db.Float, nullable=False)
    output_qty = db.Column(db.Float, nullable=False)
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Completed')

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    quantity = db.Column(db.Float, nullable=False)
    rate = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    agent_name = db.Column(db.String(100), default='Global Sago Traders')

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), default='')  # Phone number for direct contact
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    reply = db.Column(db.Text)
    reply_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='New')  # New, Replied, Resolved

# FEATURE 2: PaymentRecord model
class PaymentRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    producer_request_id = db.Column(db.Integer, db.ForeignKey('producer_request.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(30), default='UPI_QR')
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid
    transaction_ref = db.Column(db.String(100))
    verified_by = db.Column(db.String(80))
    verified_date = db.Column(db.DateTime)
    created_date = db.Column(db.DateTime, default=datetime.utcnow)
    # Relationship
    producer_request = db.relationship('ProducerRequest', backref='payment_record', uselist=False)

# =============================================================================
# FEATURE 1: AUTH DECORATORS
# =============================================================================

def check_auth():
    return 'user_id' in session

def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def manager_required(f):
    """Only managers can access operational actions."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return redirect(url_for('login'))
        user = get_current_user()
        if not user or user.role != 'manager':
            flash('Access Denied. This action requires Manager permissions.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    """Only admins can access settings and configuration."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not check_auth():
            return redirect(url_for('login'))
        user = get_current_user()
        if not user or user.role != 'admin':
            flash('Access Denied. This action requires Admin permissions.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

# =============================================================================
# CONTEXT PROCESSOR — injects current_user and today_date into all templates
# =============================================================================

@app.context_processor
def inject_globals():
    # Load factory config for use in ALL templates (footer, contact page, etc.)
    factory_config = {}
    try:
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        factory_config = {
            'factory_name': configs.get('factory_name', 'KKS Sago Factory'),
            'factory_phone': configs.get('factory_phone', ''),
            'factory_email': configs.get('factory_email', ''),
            'factory_address': configs.get('factory_address', ''),
        }
    except Exception:
        factory_config = {
            'factory_name': 'KKS Sago Factory',
            'factory_phone': '',
            'factory_email': '',
            'factory_address': '',
        }
    return {
        'current_user': get_current_user(),
        'today_date': datetime.now().strftime('%d %b %Y'),
        'factory_config': factory_config
    }

# =============================================================================
# FEATURE 4: MOCK ANALYTICS DATA GENERATOR
# =============================================================================

def seed_mock_analytics():
    """
    Seeds 2 years of mock analytics data for factory operating months:
    December, January, February, March, April.
    Revenue: 100,000–150,000 INR/month. Profit: 20-30% of revenue.
    """
    # Only seed if no sales exist
    if Sale.query.count() > 0:
        return

    current_year = datetime.now().year
    operating_months = [12, 1, 2, 3, 4]
    random.seed(42)

    raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago = Inventory.query.filter_by(item_name='Finished Sago').first()

    for year_offset in range(2, 0, -1):  # 2 years ago, 1 year ago
        base_year = current_year - year_offset

        for month in operating_months:
            # Determine actual year for December (belongs to previous calendar year)
            actual_year = base_year if month != 12 else base_year
            if month == 12:
                record_year = base_year
            else:
                record_year = base_year + 1

            # Random revenue in range
            revenue = random.randint(100000, 150000)
            profit_pct = random.uniform(0.20, 0.30)
            profit = revenue * profit_pct
            cost = revenue - profit

            # Determine day (mid-month)
            record_day = random.randint(10, 20)
            try:
                record_date = datetime(record_year, month, record_day)
            except ValueError:
                record_date = datetime(record_year, month, 15)

            # Create a procurement request (cost side)
            qty_packets = random.randint(80, 120)
            price_per_packet = round(cost / qty_packets, 2)
            total_kg = qty_packets * 25.0

            proc = ProducerRequest(
                name=random.choice(['Ravi Kumar', 'Murugan S', 'Selvi A', 'Anbu K', 'Lakshmi P']),
                phone=f'9{random.randint(100000000, 999999999)}',
                quantity=qty_packets,
                packet_size=25.0,
                price_per_packet=price_per_packet,
                total_amount=round(cost, 2),
                address='Salem District, Tamil Nadu',
                date=record_date,
                status='Paid'
            )
            db.session.add(proc)

            # Create production record
            input_kg = total_kg
            output_kg = input_kg * 0.35
            prod = Production(
                date=record_date,
                input_qty=input_kg,
                output_qty=output_kg,
                cost=round(cost, 2),
                status='Completed'
            )
            db.session.add(prod)

            # Create sale record
            rate_per_kg = round(revenue / output_kg, 2)
            sale = Sale(
                date=record_date,
                quantity=output_kg,
                rate=rate_per_kg,
                total_amount=round(revenue, 2),
                agent_name='Global Sago Traders'
            )
            db.session.add(sale)

    # Update inventory to realistic current values
    if raw:
        raw.quantity = 2500.0
    if sago:
        sago.quantity = 875.0

    db.session.commit()

# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_db():
    with app.app_context():
        db.create_all()

        # Admin user
        if not User.query.filter_by(username='admin').first():
            db.session.add(User(username='admin', password='password123', role='admin'))

        # Manager user (new)
        if not User.query.filter_by(username='manager').first():
            db.session.add(User(username='manager', password='manager123', role='manager'))

        # Inventory
        if not Inventory.query.filter_by(item_name='Raw Cassava').first():
            db.session.add(Inventory(item_name='Raw Cassava', quantity=0, unit='Kg'))
        if not Inventory.query.filter_by(item_name='Finished Sago').first():
            db.session.add(Inventory(item_name='Finished Sago', quantity=0, unit='Kg'))

        # System configs
        defaults = {
            'packet_weight': '25.0',
            'conversion_ratio': '0.35',
            'factory_name': 'KKS Sago Factory',
            'factory_phone': '07947113238',
            'factory_email': 'admin@kkssago.com',
            'factory_address': 'Mallur, Annamalaipatti, Near Paravasulagam Park, Salem-636203',
            # FEATURE 2: UPI/QR payment info
            'owner_name': 'KKS Factory Owner',
            'upi_id': 'kksfactory@upi',
            'upi_mobile': '07947113238',
            # SMTP email credentials for sending emails
            'smtp_email': '',
            'smtp_password': '',
        }
        for key, value in defaults.items():
            if not SystemConfig.query.filter_by(key=key).first():
                db.session.add(SystemConfig(key=key, value=value))

        db.session.commit()

        # Seed mock analytics data (Feature 4)
        seed_mock_analytics()

# =============================================================================
# PUBLIC ROUTES
# =============================================================================

@app.route('/')
def index():
    pkt_config = SystemConfig.query.filter_by(key='packet_weight').first()
    packet_weight = float(pkt_config.value) if pkt_config else 25.0
    return render_template('index.html', packet_weight=packet_weight)

@app.route('/sell_request', methods=['POST'])
def sell_request():
    name = request.form.get('producerName')
    phone = request.form.get('phone')
    quantity = float(request.form.get('quantity'))
    packet_size = float(request.form.get('packetSize', 25.0))
    price_per_packet = float(request.form.get('pricePerPacket', 0.0))
    address = request.form.get('address')
    total_amount = quantity * price_per_packet

    new_req = ProducerRequest(
        name=name, phone=phone, quantity=quantity,
        packet_size=packet_size, price_per_packet=price_per_packet,
        total_amount=total_amount, address=address
    )
    db.session.add(new_req)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Request Submitted Successfully!'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role  # Store role in session
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    return redirect(url_for('index'))

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone', '')
        subject = request.form.get('subject')
        message = request.form.get('message')

        new_contact = Contact(name=name, email=email, phone=phone, subject=subject, message=message)
        db.session.add(new_contact)
        db.session.commit()

        # Try to send email notification to factory admin
        try:
            factory_email_config = SystemConfig.query.filter_by(key='factory_email').first()
            recipient = factory_email_config.value if factory_email_config else ''
            if recipient:
                send_email(
                    subject=f"New Contact Message from {name}: {subject}",
                    recipients=[recipient],
                    body=f"Name: {name}\nEmail: {email}\nPhone: {phone}\nSubject: {subject}\n\nMessage:\n{message}"
                )
        except Exception as e:
            print(f"Failed to send email notification: {e}")

        flash('Message Sent Successfully!', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')

# =============================================================================
# ADMIN ROUTES (View-only for admin role)
# =============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    current_year = datetime.now().year

    total_procured_kg = db.session.query(
        db.func.sum(ProducerRequest.quantity * ProducerRequest.packet_size)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0

    raw_stock = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago_stock = Inventory.query.filter_by(item_name='Finished Sago').first()

    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    procurement_cost = db.session.query(
        db.func.sum(ProducerRequest.total_amount)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0
    net_profit = total_sales - procurement_cost

    # Chart: Cassava Supply by Producer
    producer_stats = db.session.query(
        ProducerRequest.name,
        db.func.sum(ProducerRequest.quantity * ProducerRequest.packet_size)
    ).filter(ProducerRequest.status.in_(['Approved', 'Paid']))\
     .group_by(ProducerRequest.name).all()

    prod_names = [p[0] for p in producer_stats]
    prod_qtys = [round(p[1], 2) for p in producer_stats]

    # Inventory distribution
    inv_labels = ['Raw Cassava (Kg)', 'Finished Sago (Kg)']
    inv_data = [raw_stock.quantity, sago_stock.quantity]

    # Monthly cost & sales (last 2 years — all operating months)
    # Build data for last 24 months across operating months only
    operating_months = [12, 1, 2, 3, 4]
    months_labels = []
    cost_data = []
    sales_data_chart = []

    for year_offset in range(1, -1, -1):  # last year, then current year
        yr = current_year - year_offset
        for m in [1, 2, 3, 4, 12]:  # Jan–Apr then Dec
            display_year = yr if m != 12 else yr
            month_label = datetime(display_year, m, 1).strftime('%b %Y')
            months_labels.append(month_label)

            cost_val = db.session.query(db.func.sum(ProducerRequest.total_amount)).filter(
                extract('month', ProducerRequest.date) == m,
                extract('year', ProducerRequest.date) == display_year,
                ProducerRequest.status != 'Rejected'
            ).scalar() or 0

            sales_val = db.session.query(db.func.sum(Sale.total_amount)).filter(
                extract('month', Sale.date) == m,
                extract('year', Sale.date) == display_year
            ).scalar() or 0

            cost_data.append(round(cost_val, 2))
            sales_data_chart.append(round(sales_val, 2))

    # Profit vs Loss
    pl_labels = ['Profit', 'Cost']
    if net_profit >= 0:
        pl_data = [round(net_profit, 2), round(procurement_cost, 2)]
    else:
        pl_data = [0, round(abs(net_profit), 2)]

    return render_template('dashboard.html',
                           total_procured=total_procured_kg,
                           current_stock=sago_stock.quantity,
                           raw_stock_count=raw_stock.quantity,
                           sago_stock_count=sago_stock.quantity,
                           total_sales=total_sales,
                           net_profit=net_profit,
                           months_labels=months_labels,
                           prod_names=prod_names,
                           prod_qtys=prod_qtys,
                           inv_labels=inv_labels,
                           inv_data=inv_data,
                           sales_data_chart=sales_data_chart,
                           cost_data=cost_data,
                           pl_labels=pl_labels,
                           pl_data=pl_data)

@app.route('/inventory')
@login_required
def inventory():
    raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago = Inventory.query.filter_by(item_name='Finished Sago').first()
    return render_template('inventory.html', raw=raw, sago=sago)

@app.route('/reports')
@login_required
def reports():
    producer_data = ProducerRequest.query.order_by(ProducerRequest.date.desc()).all()
    inventory_data = Inventory.query.all()
    production_data = Production.query.order_by(Production.date.desc()).all()
    sales_data = Sale.query.order_by(Sale.date.desc()).all()
    payment_data = ProducerRequest.query.filter(ProducerRequest.status.in_(['Approved', 'Paid'])).all()

    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    total_cost = db.session.query(
        db.func.sum(ProducerRequest.total_amount)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0
    profit = total_sales - total_cost

    return render_template('reports.html',
                           producer_data=producer_data,
                           inventory_data=inventory_data,
                           production_data=production_data,
                           sales_data=sales_data,
                           payment_data=payment_data,
                           total_sales=total_sales,
                           total_cost=total_cost,
                           profit=profit)

@app.route('/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    configs = {c.key: c for c in SystemConfig.query.all()}

    if request.method == 'POST':
        def update_config(key, value):
            if key in configs:
                configs[key].value = value
            else:
                db.session.add(SystemConfig(key=key, value=value))

        update_config('packet_weight', request.form.get('packetWeight'))
        update_config('conversion_ratio', request.form.get('conversionRatio'))
        update_config('factory_name', request.form.get('factoryName'))
        update_config('factory_phone', request.form.get('factoryPhone'))
        update_config('factory_email', request.form.get('factoryEmail'))
        update_config('factory_address', request.form.get('factoryAddress'))
        # Feature 2: UPI settings
        update_config('owner_name', request.form.get('ownerName'))
        update_config('upi_id', request.form.get('upiId'))
        update_config('upi_mobile', request.form.get('upiMobile'))
        # SMTP email settings
        update_config('smtp_email', request.form.get('smtpEmail', ''))
        update_config('smtp_password', request.form.get('smtpPassword', ''))

        db.session.commit()
        flash('Settings Updated Successfully!', 'success')
        return redirect(url_for('settings'))

    context = {
        'packet_weight': configs.get('packet_weight').value if 'packet_weight' in configs else '25.0',
        'conversion_ratio': configs.get('conversion_ratio').value if 'conversion_ratio' in configs else '0.35',
        'factory_name': configs.get('factory_name').value if 'factory_name' in configs else 'KKS Sago Factory',
        'factory_phone': configs.get('factory_phone').value if 'factory_phone' in configs else '',
        'factory_email': configs.get('factory_email').value if 'factory_email' in configs else '',
        'factory_address': configs.get('factory_address').value if 'factory_address' in configs else '',
        'owner_name': configs.get('owner_name').value if 'owner_name' in configs else '',
        'upi_id': configs.get('upi_id').value if 'upi_id' in configs else '',
        'upi_mobile': configs.get('upi_mobile').value if 'upi_mobile' in configs else '',
        'smtp_email': configs.get('smtp_email').value if 'smtp_email' in configs else '',
        'smtp_password': configs.get('smtp_password').value if 'smtp_password' in configs else '',
    }
    return render_template('settings.html', **context)

# =============================================================================
# MANAGER ROUTES — Operational Actions
# =============================================================================

@app.route('/procurement')
@login_required
def procurement():
    requests = ProducerRequest.query.order_by(ProducerRequest.date.desc()).all()

    pending_count = ProducerRequest.query.filter_by(status='Pending').count()
    today = datetime.utcnow().date()
    total_volume_today = db.session.query(db.func.sum(ProducerRequest.quantity)).filter(
        ProducerRequest.status.in_(['Approved', 'Paid']),
        db.func.date(ProducerRequest.date) == today
    ).scalar() or 0

    active_producers_count = db.session.query(
        db.func.count(db.distinct(ProducerRequest.name))
    ).scalar() or 0

    payouts_pending = db.session.query(db.func.sum(ProducerRequest.total_amount)).filter(
        ProducerRequest.status == 'Approved'
    ).scalar() or 0

    # FEATURE 2: Get QR/UPI config for payment display
    configs = {c.key: c.value for c in SystemConfig.query.all()}

    return render_template('procurement.html',
                           requests=requests,
                           pending_count=pending_count,
                           total_volume_today=total_volume_today,
                           active_producers_count=active_producers_count,
                           payouts_pending=payouts_pending,
                           upi_configs=configs)

@app.route('/procurement/action/<int:id>/<action>')
@manager_required
def procurement_action(id, action):
    req = ProducerRequest.query.get(id)
    if req:
        if action == 'approve':
            req.status = 'Approved'
            total_kg = req.quantity * req.packet_size
            inv = Inventory.query.filter_by(item_name='Raw Cassava').first()
            inv.quantity += total_kg

            # FEATURE 2: Create a PaymentRecord when approved
            existing = PaymentRecord.query.filter_by(producer_request_id=req.id).first()
            if not existing:
                pr = PaymentRecord(
                    producer_request_id=req.id,
                    amount=req.total_amount,
                    payment_method='UPI_QR',
                    payment_status='pending'
                )
                db.session.add(pr)

        elif action == 'reject':
            req.status = 'Rejected'

        db.session.commit()
        flash(f'Request {action.title()}d successfully.', 'success')
    return redirect(url_for('procurement'))

@app.route('/procurement/pay', methods=['POST'])
@manager_required
def procurement_pay():
    req_id = request.form.get('req_id')
    transaction_ref = request.form.get('transaction_ref', '')

    req = ProducerRequest.query.get(req_id)
    if req:
        req.status = 'Paid'

        # Update PaymentRecord
        payment = PaymentRecord.query.filter_by(producer_request_id=req.id).first()
        if payment:
            payment.payment_status = 'paid'
            payment.transaction_ref = transaction_ref
            payment.verified_by = session.get('user_role', 'manager')
            payment.verified_date = datetime.utcnow()
        else:
            # Create if missing
            payment = PaymentRecord(
                producer_request_id=req.id,
                amount=req.total_amount,
                payment_method='UPI_QR',
                payment_status='paid',
                transaction_ref=transaction_ref,
                verified_by=session.get('user_role', 'manager'),
                verified_date=datetime.utcnow()
            )
            db.session.add(payment)

        db.session.commit()
        flash(f'Payment of ₹{req.total_amount} to {req.name} marked as Paid!', 'success')

    return redirect(url_for('procurement'))

@app.route('/production', methods=['GET', 'POST'])
@login_required
def production():
    if request.method == 'POST':
        # Only manager can submit production
        user = get_current_user()
        if not user or user.role != 'manager':
            flash('Access Denied. Manager role required.', 'danger')
            return redirect(url_for('production'))

        input_qty = float(request.form.get('inputQty'))
        raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
        sago = Inventory.query.filter_by(item_name='Finished Sago').first()

        if raw.quantity >= input_qty:
            ratio_config = SystemConfig.query.filter_by(key='conversion_ratio').first()
            ratio = float(ratio_config.value) if ratio_config else 0.35
            output_qty = input_qty * ratio

            raw.quantity -= input_qty
            sago.quantity += output_qty

            new_prod = Production(input_qty=input_qty, output_qty=output_qty)
            db.session.add(new_prod)
            db.session.commit()
            flash('Production Batch Completed!', 'success')
        else:
            flash('Insufficient Raw Material!', 'danger')

    batches = Production.query.order_by(Production.date.desc()).all()
    raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
    return render_template('production.html', batches=batches, raw_stock=raw.quantity)

@app.route('/sales', methods=['GET', 'POST'])
@login_required
def sales():
    if request.method == 'POST':
        user = get_current_user()
        if not user or user.role != 'manager':
            flash('Access Denied. Manager role required.', 'danger')
            return redirect(url_for('sales'))

        qty = float(request.form.get('qty'))
        rate = float(request.form.get('rate'))
        total = qty * rate

        sago = Inventory.query.filter_by(item_name='Finished Sago').first()

        if sago.quantity >= qty:
            sago.quantity -= qty
            new_sale = Sale(quantity=qty, rate=rate, total_amount=total)
            db.session.add(new_sale)
            db.session.commit()
            flash('Sale Recorded!', 'success')
        else:
            flash('Insufficient Stock!', 'danger')

    sales_history = Sale.query.order_by(Sale.date.desc()).all()
    sago = Inventory.query.filter_by(item_name='Finished Sago').first()
    return render_template('sales.html', sales=sales_history, stock=sago.quantity)

@app.route('/payments')
@login_required
def payments():
    requests = ProducerRequest.query.filter(
        ProducerRequest.status.in_(['Approved', 'Paid'])
    ).order_by(ProducerRequest.date.desc()).all()

    total_payable = sum(r.total_amount for r in requests)
    total_paid = sum(r.total_amount for r in requests if r.status == 'Paid')
    pending_balance = total_payable - total_paid

    # FEATURE 2: Load QR/UPI config
    configs = {c.key: c.value for c in SystemConfig.query.all()}

    return render_template('payments.html',
                           requests=requests,
                           total_payable=total_payable,
                           total_paid=total_paid,
                           pending_balance=pending_balance,
                           upi_configs=configs)

# =============================================================================
# FEATURE 3: IMPROVED MESSAGE SYSTEM
# =============================================================================

@app.route('/admin/messages')
@login_required
def admin_messages():
    messages = Contact.query.order_by(Contact.date.desc()).all()
    return render_template('messages.html', messages=messages)

@app.route('/admin/messages/reply', methods=['POST'])
@manager_required
def admin_reply():
    msg_id = request.form.get('msg_id')
    reply_text = request.form.get('reply')

    msg = Contact.query.get(msg_id)
    if msg:
        msg.reply = reply_text
        msg.reply_date = datetime.utcnow()
        msg.status = 'Replied'
        db.session.commit()

        # Get factory name for the email signature
        factory_name_config = SystemConfig.query.filter_by(key='factory_name').first()
        factory_name = factory_name_config.value if factory_name_config else 'KKS Sago Factory'

        # Send reply email to the message sender
        email_sent = send_email(
            subject=f"Re: {msg.subject} - {factory_name}",
            recipients=[msg.email],
            body=f"Dear {msg.name},\n\n{reply_text}\n\nBest Regards,\n{factory_name}"
        )

        if email_sent:
            flash('Reply sent successfully via Email!', 'success')
        else:
            app.logger.error(
                "[EMAIL] Reply email failed for message_id=%s sender_email=%s",
                msg.id, msg.email
            )
            flash('Reply saved but email could not be sent. Please configure SMTP Email & Password in Settings.', 'warning')

    return redirect(url_for('admin_messages'))

@app.route('/admin/messages/resolve/<int:msg_id>', methods=['POST'])
@manager_required
def resolve_message(msg_id):
    msg = Contact.query.get(msg_id)
    if msg:
        msg.status = 'Resolved'
        db.session.commit()
        flash('Message marked as Resolved.', 'success')
    return redirect(url_for('admin_messages'))

@app.route('/admin/messages/delete/<int:msg_id>', methods=['POST'])
@manager_required
def delete_message(msg_id):
    msg = Contact.query.get(msg_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
        flash('Message deleted successfully!', 'success')
    else:
        flash('Message not found.', 'danger')
    return redirect(url_for('admin_messages'))

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
