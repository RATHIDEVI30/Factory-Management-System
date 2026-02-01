from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from flask_mail import Mail, Message
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'kks_sago_factory_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///kks_factory.db'
# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Rathi%402006@localhost/kks_factory'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Email Configuration (Gmail Example) ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'  # REPLACE WITH YOUR EMAIL
app.config['MAIL_PASSWORD'] = 'your-app-password'     # REPLACE WITH YOUR APP PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = 'your-email@gmail.com' # REPLACE WITH YOUR EMAIL

mail = Mail(app)

db = SQLAlchemy(app)

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)

class ProducerRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False) # Packets
    packet_size = db.Column(db.Float, default=25.0) # Kg per packet
    price_per_packet = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    address = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Pending') # Pending, Approved, Rejected, Paid

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(50), unique=True)
    quantity = db.Column(db.Float, default=0.0) # In KG
    unit = db.Column(db.String(10))

class SystemConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(50), nullable=False)

class Production(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    input_qty = db.Column(db.Float, nullable=False) # In KG
    output_qty = db.Column(db.Float, nullable=False) # In KG
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='Completed')

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    quantity = db.Column(db.Float, nullable=False) # In KG
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
    status = db.Column(db.String(20), default='New') # New, Replied

# --- Initialization ---
def init_db():
    with app.app_context():
        db.create_all()
        # Create Admin if not exists
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', password='password123') # Simple text for demo
            db.session.add(admin)
        
        # Initialize Inventory items if not exist
        if not Inventory.query.filter_by(item_name='Raw Cassava').first():
            db.session.add(Inventory(item_name='Raw Cassava', quantity=0, unit='Kg')) # Changed to Kg for consistency
        if not Inventory.query.filter_by(item_name='Finished Sago').first():
            db.session.add(Inventory(item_name='Finished Sago', quantity=0, unit='Kg')) # Changed to Kg for consistency
        
        # Initialize Packet Config
        if not SystemConfig.query.filter_by(key='packet_weight').first():
            db.session.add(SystemConfig(key='packet_weight', value='25.0'))
        
        # Initialize Production Config
        if not SystemConfig.query.filter_by(key='conversion_ratio').first():
            db.session.add(SystemConfig(key='conversion_ratio', value='0.35'))
        
        # Initialize Company Info
        if not SystemConfig.query.filter_by(key='factory_name').first():
            db.session.add(SystemConfig(key='factory_name', value='KKS Sago Factory'))
        if not SystemConfig.query.filter_by(key='factory_phone').first():
            db.session.add(SystemConfig(key='factory_phone', value='+91 98765 43210'))
        if not SystemConfig.query.filter_by(key='factory_email').first():
            db.session.add(SystemConfig(key='factory_email', value='admin@kkssago.com'))
        if not SystemConfig.query.filter_by(key='factory_address').first():
            db.session.add(SystemConfig(key='factory_address', value='Mallur, Salem'))
            
        db.session.commit()

# --- Routes ---

@app.route('/')
def index():
    # Get Configured Packet Weight
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
    
    new_req = ProducerRequest(name=name, phone=phone, quantity=quantity, 
                              packet_size=packet_size, price_per_packet=price_per_packet, 
                              total_amount=total_amount, address=address)
    db.session.add(new_req)
    db.session.commit()
    
    # Return JSON for AJAX or redirect
    return jsonify({'success': True, 'message': 'Request Submitted Successfully!'})

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid Credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

def check_auth():
    if 'user_id' not in session:
        return False
    return True

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if not check_auth(): return redirect(url_for('login'))
    
    # Fetch all configs
    configs = {c.key: c for c in SystemConfig.query.all()}
    
    if request.method == 'POST':
        # Helper to update or create
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
        
        db.session.commit()
        flash('Settings Updated Successfully!', 'success')
        return redirect(url_for('settings'))
        
    # Prepare values for template (use defaults if missing)
    context = {
        'packet_weight': configs.get('packet_weight').value if 'packet_weight' in configs else '25.0',
        'conversion_ratio': configs.get('conversion_ratio').value if 'conversion_ratio' in configs else '0.35',
        'factory_name': configs.get('factory_name').value if 'factory_name' in configs else 'KKS Sago Factory',
        'factory_phone': configs.get('factory_phone').value if 'factory_phone' in configs else '',
        'factory_email': configs.get('factory_email').value if 'factory_email' in configs else '',
        'factory_address': configs.get('factory_address').value if 'factory_address' in configs else ''
    }
        
    return render_template('settings.html', **context)

@app.route('/payments')
def payments():
    if not check_auth(): return redirect(url_for('login'))
    # Get all Approved/Paid requests
    requests = ProducerRequest.query.filter(ProducerRequest.status.in_(['Approved', 'Paid'])).order_by(ProducerRequest.date.desc()).all()
    
    # Calculate Summary
    total_payable = sum(r.total_amount for r in requests)
    total_paid = sum(r.total_amount for r in requests if r.status == 'Paid')
    pending_balance = total_payable - total_paid
    
    return render_template('payments.html', requests=requests, total_payable=total_payable, total_paid=total_paid, pending_balance=pending_balance)

@app.route('/dashboard')
def dashboard():
    if not check_auth(): return redirect(url_for('login'))
    
    # --- Stats ---
    # Total Procured in KG = Sum(quantity * packet_size)
    total_procured_kg = db.session.query(
        db.func.sum(ProducerRequest.quantity * ProducerRequest.packet_size)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0
    
    raw_stock = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago_stock = Inventory.query.filter_by(item_name='Finished Sago').first()
    
    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    
    # Calculate Procurement Cost (Sum of all approved/paid producer requests total_amount)
    procurement_cost = db.session.query(
        db.func.sum(ProducerRequest.total_amount)
    ).filter(ProducerRequest.status != 'Rejected').scalar() or 0
    
    # Profit = Total Sales - Total Procurement Cost
    net_profit = total_sales - procurement_cost
    
    # --- Chart Data Preparation ---
    current_year = datetime.now().year
    
    # 1. Cassava Supply by Producer (Bar)
    producer_stats = db.session.query(
        ProducerRequest.name,
        db.func.sum(ProducerRequest.quantity * ProducerRequest.packet_size)
    ).filter(ProducerRequest.status.in_(['Approved', 'Paid']))\
     .group_by(ProducerRequest.name).all()
     
    prod_names = [p[0] for p in producer_stats]
    prod_qtys = [p[1] for p in producer_stats]
    
    # 2. Inventory Distribution (Pie)
    inv_labels = ['Raw Cassava (Kg)', 'Finished Sago (Kg)']
    inv_data = [raw_stock.quantity, sago_stock.quantity]
    
    # 3. Monthly Powder Sales & 4. Production Cost (Bar)
    # Get Production Cost by Month (Based on Procurement Date/Cost)
    # Note: To show "Production Cost" by month, we can use the date of procurement payments
    cost_query = db.session.query(
        extract('month', ProducerRequest.date),
        db.func.sum(ProducerRequest.total_amount)
    ).filter(
        extract('year', ProducerRequest.date) == current_year,
        ProducerRequest.status != 'Rejected'
    ).group_by(extract('month', ProducerRequest.date)).all()

    # Get Sales by Month
    sales_query = db.session.query(
        extract('month', Sale.date),
        db.func.sum(Sale.total_amount)
    ).filter(extract('year', Sale.date) == current_year)\
     .group_by(extract('month', Sale.date)).all()
     
    cost_data = [0] * 12
    sales_data_chart = [0] * 12
    
    for month, cost in cost_query:
        cost_data[int(month)-1] = cost
        
    for month, revenue in sales_query:
        sales_data_chart[int(month)-1] = revenue
        
    months_labels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

    # 5. Profit vs Loss (Pie)
    pl_labels = ['Profit', 'Loss']
    if net_profit >= 0:
        pl_data = [net_profit, 0]
    else:
        pl_data = [0, abs(net_profit)]

    # Trend (Last 7 Sales)
    last_sales = Sale.query.order_by(Sale.date.asc()).limit(10).all()
    trend_labels = [s.date.strftime('%d-%b') for s in last_sales]
    trend_data = [s.total_amount for s in last_sales]
    
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
                           trend_data=trend_data)

@app.route('/procurement')
def procurement():
    if not check_auth(): return redirect(url_for('login'))
    requests = ProducerRequest.query.order_by(ProducerRequest.date.desc()).all()
    
    # Calculate Stats
    pending_count = ProducerRequest.query.filter_by(status='Pending').count()
    
    # Total Volume (Approved/Paid requests submitted today)
    today = datetime.utcnow().date()
    total_volume_today = db.session.query(db.func.sum(ProducerRequest.quantity)).filter(
        ProducerRequest.status.in_(['Approved', 'Paid']),
        db.func.date(ProducerRequest.date) == today
    ).scalar() or 0
    
    # Active Producers (Distinct producers)
    active_producers_count = db.session.query(db.func.count(db.distinct(ProducerRequest.name))).scalar() or 0
    
    # Payouts Pending (Approved but not Paid)
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
def procurement_action(id, action):
    if not check_auth(): return redirect(url_for('login'))
    req = ProducerRequest.query.get(id)
    if req:
        if action == 'approve':
            req.status = 'Approved'
            # Add to Inventory (Convert Packets to Kg)
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
def procurement_pay():
    if not check_auth(): return redirect(url_for('login'))
    
    req_id = request.form.get('req_id')
    payment_mode = request.form.get('payment_mode')
    transaction_ref = request.form.get('transaction_ref')
    
    req = ProducerRequest.query.get(req_id)
    if req:
        req.status = 'Paid'
        # In a real app, we would save payment_mode and transaction_ref to the database
        # For now, we just simulate the integration success
        # TODO: Add Payment model or columns to store payment details
        db.session.commit()
        flash(f'Payment of ₹{req.total_amount} to {req.name} Successful! Ref: {transaction_ref}', 'success')
        
    return redirect(url_for('procurement'))

@app.route('/inventory')
def inventory():
    if not check_auth(): return redirect(url_for('login'))
    raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
    sago = Inventory.query.filter_by(item_name='Finished Sago').first()
    return render_template('inventory.html', raw=raw, sago=sago)

@app.route('/production', methods=['GET', 'POST'])
def production():
    if not check_auth(): return redirect(url_for('login'))
    
    if request.method == 'POST':
        input_qty = float(request.form.get('inputQty')) # Kg
        raw = Inventory.query.filter_by(item_name='Raw Cassava').first()
        sago = Inventory.query.filter_by(item_name='Finished Sago').first()
        
        if raw.quantity >= input_qty:
            # Process (Use configured ratio or default 0.35)
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
def sales():
    if not check_auth(): return redirect(url_for('login'))
    
    if request.method == 'POST':
        qty = float(request.form.get('qty')) # Kg
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

@app.route('/reports')
def reports():
    if not check_auth(): return redirect(url_for('login'))
    
    # Producer Supply Report
    producer_data = ProducerRequest.query.order_by(ProducerRequest.date.desc()).all()
    
    # Inventory Report
    inventory_data = Inventory.query.all()
    
    # Production Cost Report
    production_data = Production.query.order_by(Production.date.desc()).all()
    
    # Sales Report
    sales_data = Sale.query.order_by(Sale.date.desc()).all()
    
    # Payment Settlement Report
    payment_data = ProducerRequest.query.filter(ProducerRequest.status.in_(['Approved', 'Paid'])).all()
    
    # Profit/Loss Summary
    total_sales = db.session.query(db.func.sum(Sale.total_amount)).scalar() or 0
    
    # Calculate Total Procurement Cost (as Production Cost)
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

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        
        new_contact = Contact(name=name, email=email, subject=subject, message=message)
        db.session.add(new_contact)
        db.session.commit()

        # Send Email Notification to Admin
        try:
            admin_email = app.config['MAIL_USERNAME']
            msg = Message(
                subject=f"New Contact Message from {name}: {subject}",
                recipients=[admin_email],
                body=f"Name: {name}\nEmail: {email}\nSubject: {subject}\n\nMessage:\n{message}"
            )
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send email notification: {e}")

        flash('Message Sent Successfully!', 'success')
        return redirect(url_for('contact'))
        
    return render_template('contact.html')

@app.route('/admin/messages')
def admin_messages():
    if not check_auth(): return redirect(url_for('login'))
    messages = Contact.query.order_by(Contact.date.desc()).all()
    return render_template('messages.html', messages=messages)

@app.route('/admin/messages/reply', methods=['POST'])
def admin_reply():
    if not check_auth(): return redirect(url_for('login'))
    
    msg_id = request.form.get('msg_id')
    reply_text = request.form.get('reply')
    
    msg = Contact.query.get(msg_id)
    if msg:
        msg.reply = reply_text
        msg.reply_date = datetime.utcnow()
        msg.status = 'Replied'
        
        # Send Email
        try:
            email_msg = Message(
                subject=f"Re: {msg.subject} - KKS Sago Factory",
                recipients=[msg.email],
                body=f"Dear {msg.name},\n\n{reply_text}\n\nBest Regards,\nAdmin\nKKS Sago Factory"
            )
            mail.send(email_msg)
            flash('Reply sent successfully via Email!', 'success')
        except Exception as e:
            print(f"Email Error: {e}")
            flash(f'Reply saved, but Email failed to send: {e}', 'warning')
            
        db.session.commit()
        
    return redirect(url_for('admin_messages'))

@app.route('/admin/messages/delete/<int:msg_id>', methods=['POST'])
def delete_message(msg_id):
    if not check_auth(): return redirect(url_for('login'))
    
    msg = Contact.query.get(msg_id)
    if msg:
        db.session.delete(msg)
        db.session.commit()
        flash('Message deleted successfully!', 'success')
    else:
        flash('Message not found.', 'danger')
        
    return redirect(url_for('admin_messages'))

if __name__ == '__main__':
    # if not os.path.exists('kks_factory.db'):
    init_db()
    app.run(debug=True, port=5000)
