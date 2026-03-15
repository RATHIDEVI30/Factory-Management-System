from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from flask_mail import Mail, Message
from datetime import datetime
import os
import smtplib
from functools import wraps

app = Flask(__name__)
app.secret_key = 'kks_sago_factory_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kks_factory.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Rathi%402006@localhost/kks_factory'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Base Gmail SMTP Config (credentials loaded dynamically from DB) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = None
app.config['MAIL_PASSWORD'] = None
app.config['MAIL_DEFAULT_SENDER'] = None

mail = Mail(app)
db = SQLAlchemy(app)


@app.context_processor
def inject_globals():
    try:
        configs = {c.key: c.value for c in SystemConfig.query.all()}
    except Exception:
        configs = {}

    class FactoryConfig:
        factory_name    = configs.get('factory_name',    'KKS Sago Factory')
        factory_phone   = configs.get('factory_phone',   '')
        factory_email   = configs.get('factory_email',   '')
        factory_address = configs.get('factory_address', '')

    return dict(
        factory_config=FactoryConfig(),
        today_date=datetime.now().strftime('%Y-%m-%d'),
        current_user=get_current_user(),
    )

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='manager')


def get_current_user():
    if 'user_id' in session:
        return User.query.get(session['user_id'])
    return None

class ProducerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    packet_size = db.Column(db.Float, default=25.0)
    price_per_packet = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    address = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending')

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(50), unique=True)
    quantity = db.Column(db.Float, default=0.0)
    unit = db.Column(db.String(10))

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(50), nullable=False)

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
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    reply = db.Column(db.Text)
    reply_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='New')


# ---------------------------------------------------------------------------
# EMAIL HELPER — loads credentials fresh from DB on every call,
# reconfigures Flask-Mail, then sends.
# ---------------------------------------------------------------------------
def send_email(subject: str, recipients: list, body: str) -> tuple[bool, str]:
    """
    Send an email using credentials stored in SystemConfig.

    Returns (success: bool, error_message: str).
    """
    try:
        # 1. Pull credentials from DB
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        smtp_email = configs.get('smtp_email', '').strip()
        # Strip ALL whitespace (including spaces accidentally pasted into App Password)
        smtp_password = configs.get('smtp_password', '').replace(' ', '').strip()

        if not smtp_email or not smtp_password:
            msg = "SMTP credentials not configured. Set smtp_email and smtp_password in Settings."
            print(f"[EMAIL ERROR] {msg}")
            return False, "Please configure SMTP Email & Password in Settings."

        # 2. Reconfigure Flask-Mail with the live credentials
        app.config.update(
            MAIL_SERVER='smtp.gmail.com',
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
            MAIL_USE_SSL=False,
            MAIL_USERNAME=smtp_email,
            MAIL_PASSWORD=smtp_password,
            MAIL_DEFAULT_SENDER=smtp_email,
        )
        mail.init_app(app)

        # 3. Ensure recipients is always a list
        if isinstance(recipients, str):
            recipients = [recipients]

        # 4. Build and send message
        with app.app_context():
            msg = Message(subject=subject, recipients=recipients, body=body)
            mail.send(msg)

        print(f"[EMAIL OK] Sent '{subject}' → {recipients}")
        return True, ""

    except smtplib.SMTPAuthenticationError:
        err = "Gmail authentication failed. Check your App Password (not your account password)."
        print(f"[EMAIL ERROR] SMTPAuthenticationError: {err}")
        return False, err

    except smtplib.SMTPException as e:
        err = f"SMTP error: {e}"
        print(f"[EMAIL ERROR] {err}")
        return False, err

    except Exception as e:
        err = f"Unexpected error while sending email: {e}"
        print(f"[EMAIL ERROR] {err}")
        return False, err


# --- Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', password='password123', role='admin')
            db.session.add(admin_user)
        else:
            if getattr(admin_user, 'role', None) != 'admin':
                admin_user.role = 'admin'

        manager_user = User.query.filter_by(username='manager').first()
        if not manager_user:
            manager_user = User(username='manager', password='password123', role='manager')
            db.session.add(manager_user)
        else:
            if getattr(manager_user, 'role', None) != 'manager':
                manager_user.role = 'manager'

        if not Inventory.query.filter_by(item_name='Raw Cassava').first():
            db.session.add(Inventory(item_name='Raw Cassava', quantity=0, unit='Kg'))
        if not Inventory.query.filter_by(item_name='Finished Sago').first():
            db.session.add(Inventory(item_name='Finished Sago', quantity=0, unit='Kg'))

        defaults = {
            'packet_weight': '25.0',
            'conversion_ratio': '0.35',
            'factory_name': 'KKS Sago Factory',
            'factory_phone': '+91 98765 43210',
            'factory_email': 'admin@kkssago.com',
            'factory_address': 'Mallur, Salem',
            # SMTP credentials — update via Settings page
            'smtp_email': '',
            'smtp_password': '',
        }
        for key, value in defaults.items():
            if not SystemConfig.query.filter_by(key=key).first():
                db.session.add(SystemConfig(key=key, value=value))

        db.session.commit()


# --- Routes ---

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

    # Notify admin (non-blocking — failure is logged, not raised)
    configs = {c.key: c.value for c in SystemConfig.query.all()}
    admin_email = configs.get('smtp_email', '').strip()
    if admin_email:
        send_email(
            subject=f"New Cassava Sell Request from {name}",
            recipients=[admin_email],
            body=(
                f"New sell request received.\n\n"
                f"Name: {name}\nPhone: {phone}\nAddress: {address}\n"
                f"Packets: {quantity} × {packet_size} Kg = {quantity * packet_size} Kg\n"
                f"Price/Pkt: ₹{price_per_packet}\nTotal: ₹{total_amount}"
            ),
        )

    return jsonify({'success': True, 'message': 'Request Submitted Successfully!'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['user_role'] = user.role
            print("LOGIN SUCCESS:", user.username, user.role)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_role', None)
    return redirect(url_for('index'))

def check_auth():
    return 'user_id' in session


def manager_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user = User.query.get(session['user_id'])

        if not user or user.role != 'manager':
            flash('Access Denied. Manager role required.', 'danger')
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))

        user = User.query.get(session['user_id'])

        if not user or user.role != 'admin':
            flash('Access Denied. Admin role required.', 'danger')
            return redirect(url_for('dashboard'))

        return f(*args, **kwargs)
    return decorated

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

        update_config('packet_weight',    request.form.get('packetWeight'))
        update_config('conversion_ratio', request.form.get('conversionRatio'))
        update_config('factory_name',     request.form.get('factoryName'))
        update_config('factory_phone',    request.form.get('factoryPhone'))
        update_config('factory_email',    request.form.get('factoryEmail'))
        update_config('factory_address',  request.form.get('factoryAddress'))
        # SMTP credentials
        smtp_email = (request.form.get('smtpEmail') or '').strip()
        smtp_password = (request.form.get('smtpPassword') or '').replace(' ', '').strip()
        update_config('smtp_email',    smtp_email)
        update_config('smtp_password', smtp_password)

        db.session.commit()
        flash('Settings Updated Successfully!', 'success')
        return redirect(url_for('settings'))

    context = {
        'packet_weight':    configs.get('packet_weight').value    if 'packet_weight'    in configs else '25.0',
        'conversion_ratio': configs.get('conversion_ratio').value if 'conversion_ratio' in configs else '0.35',
        'factory_name':     configs.get('factory_name').value     if 'factory_name'     in configs else 'KKS Sago Factory',
        'factory_phone':    configs.get('factory_phone').value    if 'factory_phone'    in configs else '',
        'factory_email':    configs.get('factory_email').value    if 'factory_email'    in configs else '',
        'factory_address':  configs.get('factory_address').value  if 'factory_address'  in configs else '',
        'smtp_email':       configs.get('smtp_email').value       if 'smtp_email'       in configs else '',
        'smtp_password':    configs.get('smtp_password').value    if 'smtp_password'    in configs else '',
    }
    return render_template('settings.html', **context)

@app.route('/payments')
def payments():
    if not check_auth(): return redirect(url_for('login'))
    requests = ProducerRequest.query.filter(
        ProducerRequest.status.in_(['Approved', 'Paid'])
    ).order_by(ProducerRequest.date.desc()).all()

    total_payable  = sum(r.total_amount for r in requests)
    total_paid     = sum(r.total_amount for r in requests if r.status == 'Paid')
    pending_balance = total_payable - total_paid

    return render_template('payments.html', requests=requests,
                           total_payable=total_payable,
                           total_paid=total_paid,
                           pending_balance=pending_balance)

@app.route('/dashboard')
def dashboard():
    if not check_auth(): return redirect(url_for('login'))

    total_procured_kg = db.session.query(
        db.func.sum(ProducerRequest.quantity * ProducerRequest.packet_size)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0

    raw_stock  = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago_stock = Inventory.query.filter_by(item_name='Finished Sago').first()
    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0

    procurement_cost = db.session.query(
        db.func.sum(ProducerRequest.total_amount)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0

    net_profit = total_sales - procurement_cost
    current_year = datetime.now().year

    producer_stats = db.session.query(
        ProducerRequest.name,
        db.func.sum(ProducerRequest.quantity * ProducerRequest.packet_size)
    ).filter(ProducerRequest.status.in_(['Approved', 'Paid']))\
     .group_by(ProducerRequest.name).all()

    prod_names = [p[0] for p in producer_stats]
    prod_qtys  = [p[1] for p in producer_stats]

    inv_labels = ['Raw Cassava (Kg)', 'Finished Sago (Kg)']
    inv_data   = [raw_stock.quantity, sago_stock.quantity]

    selected_year = request.args.get('year', default=datetime.now().year, type=int)
    available_years = [2024, 2025, 2026]

    cost_query = db.session.query(
        extract('month', ProducerRequest.date),
        db.func.sum(ProducerRequest.total_amount)
    ).filter(
        extract('year', ProducerRequest.date) == selected_year,
        ProducerRequest.status != 'Rejected'
    ).group_by(extract('month', ProducerRequest.date)).all()

    sales_query = db.session.query(
        extract('month', Sale.date),
        db.func.sum(Sale.total_amount)
    ).filter(extract('year', Sale.date) == selected_year)\
     .group_by(extract('month', Sale.date)).all()

    cost_data        = [0] * 12
    sales_data_chart = [0] * 12

    for month, cost in cost_query:
        cost_data[int(month)-1] = cost
    for month, revenue in sales_query:
        sales_data_chart[int(month)-1] = revenue

    months_labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

    pl_labels = ['Profit', 'Loss']
    pl_data   = [net_profit, 0] if net_profit >= 0 else [0, abs(net_profit)]

    last_sales   = Sale.query.order_by(Sale.date.asc()).limit(10).all()
    trend_labels = [s.date.strftime('%d-%b') for s in last_sales]
    trend_data   = [s.total_amount for s in last_sales]

    today_date = datetime.now().strftime('%Y-%m-%d')

    return render_template('dashboard.html',
                           today_date=today_date,
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
                           pl_data=pl_data,
                           trend_labels=trend_labels,
                           trend_data=trend_data,
                           selected_year=selected_year,
                           available_years=available_years)

@app.route('/procurement')
def procurement():
    if not check_auth(): return redirect(url_for('login'))
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

    return render_template('procurement.html',
                           requests=requests,
                           pending_count=pending_count,
                           total_volume_today=total_volume_today,
                           active_producers_count=active_producers_count,
                           payouts_pending=payouts_pending)

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
        elif action == 'reject':
            req.status = 'Rejected'
        elif action == 'pay':
            req.status = 'Paid'
        db.session.commit()
    return redirect(url_for('procurement'))

@app.route('/procurement/pay', methods=['POST'])
@manager_required
def procurement_pay():

    req_id         = request.form.get('req_id')
    payment_mode   = request.form.get('payment_mode')
    transaction_ref = request.form.get('transaction_ref')

    req = ProducerRequest.query.get(req_id)
    if req:
        req.status = 'Paid'
        db.session.commit()
        flash(f'Payment of ₹{req.total_amount} to {req.name} Successful! Ref: {transaction_ref}', 'success')

    return redirect(url_for('procurement'))

@app.route('/inventory')
def inventory():
    if not check_auth(): return redirect(url_for('login'))
    raw  = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago = Inventory.query.filter_by(item_name='Finished Sago').first()
    return render_template('inventory.html', raw=raw, sago=sago)

@app.route('/production', methods=['GET', 'POST'])
def production():
    if not check_auth(): return redirect(url_for('login'))

    if request.method == 'POST':
        user = get_current_user()
        if not user or user.role != 'manager':
            flash('Access Denied. Only Manager can start production.', 'danger')
            return redirect(url_for('production'))

        input_qty = float(request.form.get('inputQty'))
        raw  = Inventory.query.filter_by(item_name='Raw Cassava').first()
        sago = Inventory.query.filter_by(item_name='Finished Sago').first()

        if raw.quantity >= input_qty:
            ratio_config = SystemConfig.query.filter_by(key='conversion_ratio').first()
            ratio = float(ratio_config.value) if ratio_config else 0.35
            output_qty = input_qty * ratio

            raw.quantity  -= input_qty
            sago.quantity += output_qty

            db.session.add(Production(input_qty=input_qty, output_qty=output_qty))
            db.session.commit()
            flash('Production Batch Completed!', 'success')
        else:
            flash('Insufficient Raw Material!', 'danger')

    batches = Production.query.order_by(Production.date.desc()).all()
    raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
    return render_template('production.html', batches=batches, raw_stock=raw.quantity)

@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if not check_auth(): return redirect(url_for('login'))

    if request.method == 'POST':
        user = get_current_user()
        if not user or user.role != 'manager':
            flash('Access Denied. Only Manager can record sales.', 'danger')
            return redirect(url_for('sales'))

        qty   = float(request.form.get('qty'))
        rate  = float(request.form.get('rate'))
        total = qty * rate

        sago = Inventory.query.filter_by(item_name='Finished Sago').first()
        if sago.quantity >= qty:
            sago.quantity -= qty
            db.session.add(Sale(quantity=qty, rate=rate, total_amount=total))
            db.session.commit()
            flash('Sale Recorded!', 'success')
        else:
            flash('Insufficient Stock!', 'danger')

    sales_history = Sale.query.order_by(Sale.date.desc()).all()
    sago = Inventory.query.filter_by(item_name='Finished Sago').first()
    return render_template('sales.html', sales=sales_history, stock=sago.quantity)

@app.route('/reports')
def reports():
    if not check_auth(): return redirect(url_for('login'))

    producer_data  = ProducerRequest.query.order_by(ProducerRequest.date.desc()).all()
    inventory_data = Inventory.query.all()
    production_data = Production.query.order_by(Production.date.desc()).all()
    sales_data     = Sale.query.order_by(Sale.date.desc()).all()
    payment_data   = ProducerRequest.query.filter(
        ProducerRequest.status.in_(['Approved', 'Paid'])
    ).all()

    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    total_cost  = db.session.query(
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

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name    = request.form.get('name')
        email   = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        db.session.add(Contact(name=name, email=email, subject=subject, message=message))
        db.session.commit()

        # Notify admin
        configs = {c.key: c.value for c in SystemConfig.query.all()}
        admin_email = configs.get('smtp_email', '').strip()
        if admin_email:
            send_email(
                subject=f"New Contact Message from {name}: {subject}",
                recipients=[admin_email],
                body=f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\nMessage:\n{message}",
            )

        flash('Message Sent Successfully!', 'success')
        return redirect(url_for('contact'))

    return render_template('contact.html')

@app.route('/admin/messages')
def admin_messages():
    if not check_auth(): return redirect(url_for('login'))
    messages = Contact.query.order_by(Contact.date.desc()).all()
    return render_template('messages.html', messages=messages)

@app.route('/admin/messages/reply', methods=['POST'])
@manager_required
def admin_reply():
    if not check_auth(): return redirect(url_for('login'))

    msg_id     = request.form.get('msg_id')
    reply_text = request.form.get('reply')

    msg = Contact.query.get(msg_id)
    if msg:
        msg.reply      = reply_text
        msg.reply_date = datetime.utcnow()
        msg.status     = 'Replied'
        db.session.commit()

        # Send reply email to the original sender
        success, error = send_email(
            subject=f"Re: {msg.subject} - KKS Sago Factory",
            recipients=[msg.email],          # always a list inside send_email()
            body=(
                f"Dear {msg.name},\n\n"
                f"{reply_text}\n\n"
                f"Best Regards,\nAdmin\nKKS Sago Factory"
            ),
        )

        if success:
            flash('Reply sent successfully via Email!', 'success')
        else:
            flash(f'Reply saved, but email could not be sent. {error}', 'warning')

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


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)