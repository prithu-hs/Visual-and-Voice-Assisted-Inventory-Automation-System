from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit
import sqlite3
import json
import datetime
import os
import cv2
import numpy as np
import base64
from io import BytesIO, StringIO  # Add this import
import io  # Add this import
from PIL import Image
import uuid
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# Import our custom modules
from yolo_detector import detector
from speech_recognizer import speech_recognizer

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

socketio = SocketIO(app, cors_allowed_origins="*")
@app.errorhandler(404)
def not_found(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Endpoint not found'}), 404
    return error

@app.errorhandler(500)
def internal_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
    return error

@app.errorhandler(Exception)
def handle_exception(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'error': f'Server error: {str(error)}'}), 500
    return error
# Database initialization
def init_db():
    conn = sqlite3.connect('inventory.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user', -- 'admin' or 'user'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    # Default admin user
    c.execute('''INSERT OR IGNORE INTO users (username, email, password, role)VALUES ('admin', 'admin@inventory.com', 'admin123', 'admin')''')
    
    # Products table
    c.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            price REAL,
            current_stock INTEGER DEFAULT 0,
            min_stock_level INTEGER DEFAULT 5,
            image_path TEXT,
            barcode TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Transactions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            transaction_type TEXT, -- 'sale', 'restock', 'adjustment'
            quantity INTEGER,
            previous_stock INTEGER,
            new_stock INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notes TEXT,
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Suppliers table
    c.execute('''
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contact_info TEXT,
            email TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Product-Supplier relationship
    c.execute('''
        CREATE TABLE IF NOT EXISTS product_suppliers (
            product_id INTEGER,
            supplier_id INTEGER,
            PRIMARY KEY (product_id, supplier_id),
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
        )
    ''')
    
    # Voice commands log
    c.execute('''
        CREATE TABLE IF NOT EXISTS voice_commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            command_text TEXT,
            processed_result TEXT,
            confidence REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN
        )
    ''')
    
    # Shopping sessions table
    # Shopping sessions table
    c.execute('''
        CREATE TABLE IF NOT EXISTS shopping_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            session_token TEXT UNIQUE,
            total_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Order items table (for shopping sessions)
    c.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            unit_price REAL,
            total_price REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES shopping_sessions (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Orders table for user purchases (backward compatibility)
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER DEFAULT 1,
            total_price REAL,
            order_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            session_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        )
    ''')
    
    # Insert sample data
    sample_products = [
        ('Apple', 'Fresh red apples', 'Fruits', 0.50, 100, 10, 'apple.jpg', '123456789012'),
        ('Banana', 'Yellow bananas', 'Fruits', 0.30, 150, 15, 'banana.jpg', '123456789013'),
        ('Orange', 'orange', 'Fruits', 1.20, 50, 5, 'orange.jpg', '123456789014'),
        ('Carrot', 'carrot', 'Fruits', 2.50, 30, 8, 'carrot.jpg', '123456789015'),
        ('Bottle', 'Water bottle 500ml', 'Beverages', 1.00, 80, 10, 'bottle.jpg', '123456789016'),
        ('Book', 'Notebook', 'Stationery', 3.50, 40, 5, 'book.jpg', '123456789017'),
    ]
    
    c.executemany('''
        INSERT OR IGNORE INTO products (name, description, category, price, current_stock, min_stock_level, image_path, barcode)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', sample_products)
    
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect('inventory.db')
    conn.row_factory = sqlite3.Row
    return conn

# Authentication Routes
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', 
                         (username, email, password))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('register.html', error="Username or email already exists")
        conn.close()
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and user['password']==password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            
            # Clear any existing shopping session
            session.pop('current_shopping_session', None)
            session.pop('current_session_id', None)
            
            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            return render_template('login.html', error="Invalid credentials")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login'))

# User Routes
@app.route('/user_dashboard')
def user_dashboard():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    
    return render_template('user_dashboard.html', username=session['username'], products=products)

@app.route('/user_orders')
def user_orders():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))

    conn = get_db_connection()
    orders = conn.execute('''
        SELECT o.id, o.order_time, o.quantity, o.total_price,
               p.name as product_name, p.image_path
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.user_id = ?
        ORDER BY o.order_time DESC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('user_orders.html', username=session['username'], orders=orders)

@app.route('/user_shop')
def user_shop():
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))
    return render_template('user_shop.html', user_id=session['user_id'])

# Admin Routes
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get inventory summary
    low_stock = conn.execute('''
        SELECT COUNT(*) as count FROM products 
        WHERE current_stock <= min_stock_level
    ''').fetchone()['count']
    
    total_products = conn.execute('SELECT COUNT(*) as count FROM products').fetchone()['count']
    out_of_stock = conn.execute('SELECT COUNT(*) as count FROM products WHERE current_stock = 0').fetchone()['count']
    
    # Get recent transactions
    recent_transactions = conn.execute('''
        SELECT t.*, p.name as product_name 
        FROM transactions t 
        JOIN products p ON t.product_id = p.id 
        ORDER BY t.timestamp DESC 
        LIMIT 10
    ''').fetchall()
    
    conn.close()
    
    return render_template('dashboard.html',
                         low_stock=low_stock,
                         total_products=total_products,
                         out_of_stock=out_of_stock,
                         recent_transactions=recent_transactions)

@app.route('/products')
def products():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY name').fetchall()
    conn.close()
    return render_template('products.html', products=products)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    transactions = conn.execute('''
        SELECT * FROM transactions 
        WHERE product_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 20
    ''', (product_id,)).fetchall()
    conn.close()
    return render_template('product_detail.html', product=product, transactions=transactions)

@app.route('/transactions')
def transactions():
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    transactions = conn.execute('''
        SELECT t.*, p.name as product_name 
        FROM transactions t 
        JOIN products p ON t.product_id = p.id 
        ORDER BY t.timestamp DESC
    ''').fetchall()
    conn.close()
    return render_template('transactions.html', transactions=transactions)

@app.route('/api/start_shopping_session', methods=['POST'])
def start_shopping_session():
    """Start a new shopping session with comprehensive error handling"""
    print("=== START_SHOPPING_SESSION CALLED ===")
    
    try:
        # Check if user is logged in
        if 'user_id' not in session:
            print("ERROR: User not logged in")
            return jsonify({'success': False, 'error': 'Not logged in'}), 401
        
        user_id = session['user_id']
        username = session.get('username', 'unknown')
        print(f"Starting shopping session for user: {username} (ID: {user_id})")
        
        # Generate session token
        session_token = str(uuid.uuid4())
        print(f"Generated session token: {session_token}")
        
        # Database operations
        conn = None
        try:
            conn = get_db_connection()
            print("Database connection established")
            
            # Check if user exists
            user = conn.execute('SELECT id, username FROM users WHERE id = ?', (user_id,)).fetchone()
            if not user:
                print(f"ERROR: User {user_id} not found in database")
                return jsonify({'success': False, 'error': 'User not found in database'}), 404
            
            print(f"User verified: {user['username']}")
            
            # Create new shopping session
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shopping_sessions (user_id, session_token, status)
                VALUES (?, ?, 'active')
            ''', (user_id, session_token))
            
            session_id = cursor.lastrowid
            print(f"Session created with ID: {session_id}")
            
            # Verify the session was created
            new_session = conn.execute(
                'SELECT id, session_token, status FROM shopping_sessions WHERE id = ?', 
                (session_id,)
            ).fetchone()
            
            if not new_session:
                print("ERROR: Failed to verify session creation")
                return jsonify({'success': False, 'error': 'Failed to verify session creation'}), 500
            
            print(f"Session verified: ID={new_session['id']}, Token={new_session['session_token']}, Status={new_session['status']}")
            
            conn.commit()
            print("Database transaction committed")
            
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            if conn:
                conn.rollback()
            return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500
        finally:
            if conn:
                conn.close()
                print("Database connection closed")
        
        # Store session in Flask session
        session['current_shopping_session'] = session_token
        session['current_session_id'] = session_id
        
        print(f"Session stored in Flask session: {session_token}")
        
        response_data = {
            'success': True, 
            'session_token': session_token,
            'session_id': session_id,
            'message': 'Shopping session started successfully'
        }
        
        print(f"Returning response: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"UNEXPECTED ERROR in start_shopping_session: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({'success': False, 'error': f'Unexpected error: {str(e)}'}), 500
@app.route('/api/remove_from_cart', methods=['POST'])
def remove_from_cart():
    """Remove item from shopping cart"""
    if 'user_id' not in session or 'current_shopping_session' not in session:
        return jsonify({'success': False, 'error': 'No active shopping session'})
    
    data = request.json
    item_id = data.get('item_id')
    
    conn = get_db_connection()
    
    # Verify the item belongs to the current session
    item = conn.execute('''
        SELECT oi.* FROM order_items oi
        JOIN shopping_sessions ss ON oi.session_id = ss.id
        WHERE oi.id = ? AND ss.id = ? AND ss.user_id = ?
    ''', (item_id, session['current_session_id'], session['user_id'])).fetchone()
    
    if not item:
        conn.close()
        return jsonify({'success': False, 'error': 'Item not found in cart'})
    
    # Remove the item
    conn.execute('DELETE FROM order_items WHERE id = ?', (item_id,))
    
    # Update session total
    session_total = conn.execute('''
        SELECT SUM(total_price) as total FROM order_items 
        WHERE session_id = ?
    ''', (session['current_session_id'],)).fetchone()['total'] or 0
    
    conn.execute('''
        UPDATE shopping_sessions SET total_amount = ?
        WHERE id = ?
    ''', (session_total, session['current_session_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Item removed from cart',
        'cart_total': session_total
    })
@app.route('/api/add_to_cart', methods=['POST'])
def add_to_cart():
    """Add product to shopping cart"""
    if 'user_id' not in session or 'current_shopping_session' not in session:
        return jsonify({'success': False, 'error': 'No active shopping session'})
    
    data = request.json
    product_name = data.get('product_name')
    quantity = data.get('quantity', 1)
    
    conn = get_db_connection()
    
    # Get product details
    product = conn.execute(
        'SELECT id, name, price FROM products WHERE name LIKE ?',
        (f'%{product_name}%',)
    ).fetchone()
    
    if not product:
        conn.close()
        return jsonify({'success': False, 'error': 'Product not found'})
    
    # Check if item already in cart
    existing_item = conn.execute('''
        SELECT id, quantity FROM order_items 
        WHERE session_id = ? AND product_id = ?
    ''', (session['current_session_id'], product['id'])).fetchone()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item['quantity'] + quantity
        total_price = new_quantity * product['price']
        conn.execute('''
            UPDATE order_items SET quantity = ?, total_price = ?
            WHERE id = ?
        ''', (new_quantity, total_price, existing_item['id']))
    else:
        # Add new item
        total_price = quantity * product['price']
        conn.execute('''
            INSERT INTO order_items (session_id, product_id, quantity, unit_price, total_price)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['current_session_id'], product['id'], quantity, product['price'], total_price))
    
    # Update session total
    session_total = conn.execute('''
        SELECT SUM(total_price) as total FROM order_items 
        WHERE session_id = ?
    ''', (session['current_session_id'],)).fetchone()['total'] or 0
    
    conn.execute('''
        UPDATE shopping_sessions SET total_amount = ?
        WHERE id = ?
    ''', (session_total, session['current_session_id']))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Added {quantity} {product["name"]} to cart',
        'cart_total': session_total
    })

@app.route('/api/get_cart', methods=['GET'])
def get_cart():
    """Get current shopping cart contents"""
    if 'user_id' not in session or 'current_shopping_session' not in session:
        return jsonify({'success': False, 'error': 'No active shopping session'})
    
    conn = get_db_connection()
    
    cart_items = conn.execute('''
        SELECT oi.*, p.name as product_name, p.image_path
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.session_id = ?
    ''', (session['current_session_id'],)).fetchall()
    
    session_total = conn.execute('''
        SELECT total_amount FROM shopping_sessions 
        WHERE id = ?
    ''', (session['current_session_id'],)).fetchone()['total_amount'] or 0
    
    conn.close()
    
    return jsonify({
        'success': True,
        'items': [dict(item) for item in cart_items],
        'total_amount': session_total
    })

@app.route('/api/complete_purchase', methods=['POST'])
def complete_purchase():
    """Complete the purchase and generate bill"""
    if 'user_id' not in session or 'current_shopping_session' not in session:
        return jsonify({'success': False, 'error': 'No active shopping session'})
    
    conn = get_db_connection()
    
    # Get cart items
    cart_items = conn.execute('''
        SELECT oi.*, p.name as product_name, p.current_stock
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.session_id = ?
    ''', (session['current_session_id'],)).fetchall()
    
    # Check stock availability
    for item in cart_items:
        if item['current_stock'] < item['quantity']:
            conn.close()
            return jsonify({
                'success': False, 
                'error': f'Not enough stock for {item["product_name"]}. Available: {item["current_stock"]}'
            })
    
    # Process each item - update stock and create transactions
    for item in cart_items:
        new_stock = item['current_stock'] - item['quantity']
        
        # Update product stock
        conn.execute('UPDATE products SET current_stock = ? WHERE id = ?', 
                    (new_stock, item['product_id']))
        
        # Record transaction
        conn.execute('''
            INSERT INTO transactions (product_id, transaction_type, quantity, previous_stock, new_stock, notes)
            VALUES (?, 'sale', ?, ?, ?, ?)
        ''', (item['product_id'], item['quantity'], item['current_stock'], new_stock, 'Shopping session purchase'))
        
        # Create order record (for backward compatibility)
        conn.execute('''
            INSERT INTO orders (user_id, product_id, quantity, total_price, session_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (session['user_id'], item['product_id'], item['quantity'], item['total_price'], session['current_session_id']))
    
    # Mark session as completed
    conn.execute('''
        UPDATE shopping_sessions 
        SET status = 'completed', completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (session['current_session_id'],))
    
    # Get final session details for bill
    session_details = conn.execute('''
        SELECT ss.*, u.username, u.email
        FROM shopping_sessions ss
        JOIN users u ON ss.user_id = u.id
        WHERE ss.id = ?
    ''', (session['current_session_id'],)).fetchone()
    
    conn.commit()
    conn.close()
    
    # Store session ID for bill generation
    session_id = session['current_session_id']
    
    # Clear current session
    session.pop('current_shopping_session', None)
    session.pop('current_session_id', None)
    
    return jsonify({
        'success': True,
        'message': 'Purchase completed successfully!',
        'session_id': session_id,
        'total_amount': session_details['total_amount']
    })

# Bill Generation Routes
@app.route('/download_bill/<int:order_id>')
def download_bill(order_id):
    """Generate and download bill for a specific order"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    # Get order details with product and user information
    order = conn.execute('''
        SELECT o.*, p.name as product_name, p.price as unit_price, 
               u.username, u.email,
               (o.quantity * p.price) as calculated_total
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.user_id = u.id
        WHERE o.id = ? AND o.user_id = ?
    ''', (order_id, session['user_id'])).fetchone()

    if not order:
        conn.close()
        return "Order not found", 404

    conn.close()

    # Create PDF bill
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Bill Header
    p.setFont("Helvetica-Bold", 20)
    p.drawString(100, height - 100, "INVOICE")
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 120, f"Invoice #: INV-{order_id:06d}")
    p.drawString(100, height - 135, f"Date: {order['order_time']}")

    # Company Info
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, height - 170, "AI Inventory System")
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 185, "123 Business Street")
    p.drawString(100, height - 200, "Business City, BC 12345")
    p.drawString(100, height - 215, "Phone: (555) 123-4567")

    # Customer Info
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, height - 170, "Bill To:")
    p.setFont("Helvetica", 10)
    p.drawString(350, height - 185, order['username'])
    p.drawString(350, height - 200, order['email'])

    # Line separator
    p.line(100, height - 240, width - 100, height - 240)

    # Order Details Header
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, height - 260, "Product")
    p.drawString(300, height - 260, "Quantity")
    p.drawString(400, height - 260, "Unit Price")
    p.drawString(500, height - 260, "Total")

    # Order Details
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 280, order['product_name'])
    p.drawString(300, height - 280, str(order['quantity']))
    p.drawString(400, height - 280, f"₹{order['unit_price']:.2f}")
    p.drawString(500, height - 280, f"₹{order['calculated_total']:.2f}")

    # Total
    p.setFont("Helvetica-Bold", 12)
    p.drawString(400, height - 320, "GRAND TOTAL:")
    p.drawString(500, height - 320, f"₹{order['calculated_total']:.2f}")

    # Footer
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(100, 100, "Thank you for your purchase!")
    p.drawString(100, 85, "This is a computer-generated invoice.")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"invoice_{order_id}.pdf",
        mimetype='application/pdf'
    )

@app.route('/download_all_bills')
def download_all_bills():
    """Generate and download bills for all user orders"""
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    # Get all user orders
    orders = conn.execute('''
        SELECT o.*, p.name as product_name, p.price as unit_price, 
               u.username, u.email,
               (o.quantity * p.price) as calculated_total
        FROM orders o
        JOIN products p ON o.product_id = p.id
        JOIN users u ON o.user_id = u.id
        WHERE o.user_id = ?
        ORDER BY o.order_time DESC
    ''', (session['user_id'],)).fetchall()

    conn.close()

    if not orders:
        return "No orders found", 404

    # Create PDF with all bills
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    for i, order in enumerate(orders):
        # Start new page for each order after the first
        if i > 0:
            p.showPage()

        # Bill Header
        p.setFont("Helvetica-Bold", 20)
        p.drawString(100, height - 100, "INVOICE")
        p.setFont("Helvetica", 10)
        p.drawString(100, height - 120, f"Invoice #: INV-{order['id']:06d}")
        p.drawString(100, height - 135, f"Date: {order['order_time']}")

        # Company Info
        p.setFont("Helvetica-Bold", 12)
        p.drawString(100, height - 170, "AI Inventory System")
        p.setFont("Helvetica", 10)
        p.drawString(100, height - 185, "123 Business Street")
        p.drawString(100, height - 200, "Business City, BC 12345")

        # Customer Info
        p.setFont("Helvetica-Bold", 12)
        p.drawString(350, height - 170, "Bill To:")
        p.setFont("Helvetica", 10)
        p.drawString(350, height - 185, order['username'])
        p.drawString(350, height - 200, order['email'])

        # Line separator
        p.line(100, height - 240, width - 100, height - 240)

        # Order Details Header
        p.setFont("Helvetica-Bold", 12)
        p.drawString(100, height - 260, "Product")
        p.drawString(300, height - 260, "Quantity")
        p.drawString(400, height - 260, "Unit Price")
        p.drawString(500, height - 260, "Total")

        # Order Details
        p.setFont("Helvetica", 10)
        p.drawString(100, height - 280, order['product_name'])
        p.drawString(300, height - 280, str(order['quantity']))
        p.drawString(400, height - 280, f"₹{order['unit_price']:.2f}")
        p.drawString(500, height - 280, f"₹{order['calculated_total']:.2f}")

        # Total
        p.setFont("Helvetica-Bold", 12)
        p.drawString(400, height - 320, "GRAND TOTAL:")
        p.drawString(500, height - 320, f"₹{order['calculated_total']:.2f}")

        # Footer
        p.setFont("Helvetica-Oblique", 8)
        p.drawString(100, 100, "Thank you for your purchase!")

    p.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"all_invoices_{session['user_id']}.pdf",
        mimetype='application/pdf'
    )

@app.route('/download_session_bill/<int:session_id>')
def download_session_bill(session_id):
    """Generate and download bill for a complete shopping session"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    # Get session details
    session_details = conn.execute('''
        SELECT ss.*, u.username, u.email
        FROM shopping_sessions ss
        JOIN users u ON ss.user_id = u.id
        WHERE ss.id = ? AND ss.user_id = ?
    ''', (session_id, session['user_id'])).fetchone()

    if not session_details:
        conn.close()
        return "Session not found", 404

    # Get all items in this session
    items = conn.execute('''
        SELECT oi.*, p.name as product_name, p.image_path
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.session_id = ?
    ''', (session_id,)).fetchall()

    conn.close()

    # Create PDF bill
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Bill Header
    p.setFont("Helvetica-Bold", 20)
    p.drawString(100, height - 100, "SHOPPING INVOICE")
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 120, f"Invoice #: SESS-{session_id:06d}")
    p.drawString(100, height - 135, f"Date: {session_details['completed_at'] or session_details['created_at']}")

    # Store Info
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, height - 170, "AI Inventory Smart Store")
    p.setFont("Helvetica", 10)
    p.drawString(100, height - 185, "123 Tech Street")
    p.drawString(100, height - 200, "Innovation City, IC 12345")
    p.drawString(100, height - 215, "Phone: (555) 123-TECH")

    # Customer Info
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, height - 170, "Bill To:")
    p.setFont("Helvetica", 10)
    p.drawString(350, height - 185, session_details['username'])
    p.drawString(350, height - 200, session_details['email'])
    p.drawString(350, height - 215, f"Session: {session_details['session_token'][:8]}...")

    # Line separator
    p.line(100, height - 240, width - 100, height - 240)

    # Order Details Header
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, height - 260, "Product")
    p.drawString(300, height - 260, "Qty")
    p.drawString(350, height - 260, "Unit Price")
    p.drawString(450, height - 260, "Total")

    # Order Details
    p.setFont("Helvetica", 10)
    y_position = height - 280
    total_amount = 0
    
    for item in items:
        p.drawString(100, y_position, item['product_name'])
        p.drawString(300, y_position, str(item['quantity']))
        p.drawString(350, y_position, f"₹{item['unit_price']:.2f}")
        p.drawString(450, y_position, f"₹{item['total_price']:.2f}")
        total_amount += item['total_price']
        y_position -= 20
        
        # Add new page if needed
        if y_position < 150:
            p.showPage()
            y_position = height - 100
            p.setFont("Helvetica", 10)

    # Total Section
    p.line(100, y_position - 20, width - 100, y_position - 20)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(350, y_position - 40, "GRAND TOTAL:")
    p.drawString(450, y_position - 40, f"₹{total_amount:.2f}")

    # Footer
    p.setFont("Helvetica-Oblique", 8)
    p.drawString(100, 100, "Thank you for shopping with AI Inventory Smart Store!")
    p.drawString(100, 85, "This is a computer-generated invoice.")
    p.drawString(100, 70, f"Items purchased: {len(items)} | Session completed: {session_details['completed_at']}")

    p.showPage()
    p.save()

    buffer.seek(0)
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"shopping_invoice_{session_id}.pdf",
        mimetype='application/pdf'
    )

# AI Integration Routes
@app.route('/api/detect_products', methods=['POST'])
def detect_products():
    """API endpoint for product detection using YOLO"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': 'No image provided'})
        
        image_file = request.files['image']
        if image_file.filename == '':
            return jsonify({'success': False, 'error': 'No image selected'})
        
        # Read and process image
        image = Image.open(image_file.stream)
        
        # Run YOLO detection
        result = detector.detect_products(image)
        
        # Draw bounding boxes on image
        if result.get('success') and result.get('detections'):
            image_with_boxes = detector.draw_detections(image, result['detections'])
            
            # Convert to base64 for response
            _, buffer = cv2.imencode('.jpg', image_with_boxes)
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            result['annotated_image'] = f"data:image/jpeg;base64,{image_base64}"
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/process_voice_command', methods=['POST'])
def process_voice_command():
    """API endpoint for processing voice commands"""
    try:
        data = request.json
        command_text = data.get('command', '').strip()
        user_id = session.get('user_id')
        print("user_id==",user_id)
        print("command_text==",command_text)
        
        if not command_text:
            return jsonify({'success': False, 'error': 'No command provided'})
        
        # Process the voice command
        response = speech_recognizer.process_voice_command(command_text, user_id=user_id)
        
        # Emit real-time update if stock was modified
        if response.get('action_taken') in ['add_stock', 'remove_stock']:
            socketio.emit('voice_command_processed', response)
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start_voice_listening', methods=['POST'])
def start_voice_listening():
    """Start continuous voice listening"""
    try:
        user_id = session.get('user_id')
        def voice_callback(text, success):
            socketio.emit('voice_input', {
                'text': text,
                'success': success,
                'timestamp': datetime.datetime.now().isoformat()
            })
            
            # Process the command if successful
            if success and text and not text.startswith('Could not'):
                
                print("user_id==",user_id)
                response = speech_recognizer.process_voice_command(text, user_id=user_id)
                socketio.emit('voice_command_response', response)
                
                # Optional: Convert response to speech
                if response.get('processed'):
                    speech_recognizer.text_to_speech(response['message'])
        
        speech_recognizer.start_continuous_listening(voice_callback)
        return jsonify({'success': True, 'message': 'Voice listening started'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop_voice_listening', methods=['POST'])
def stop_voice_listening():
    """Stop continuous voice listening"""
    try:
        speech_recognizer.stop_continuous_listening()
        return jsonify({'success': True, 'message': 'Voice listening stopped'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/capture_from_camera', methods=['POST'])
def capture_from_camera():
    """Capture image from webcam and detect products"""
    try:
        data = request.json
        image_data = data.get('image_data', '')  # Base64 image data from webcam
        
        if not image_data:
            return jsonify({'success': False, 'error': 'No image data provided'})
        
        # Convert base64 to image
        image_data = image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))
        
        # Run YOLO detection
        result = detector.detect_products(image)
        print("result==",result)
        
        # Draw bounding boxes
        if result.get('success') and result.get('detections'):
            image_with_boxes = detector.draw_detections(image, result['detections'])
            
            # Convert back to base64
            _, buffer = cv2.imencode('.jpg', image_with_boxes)
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            result['annotated_image'] = f"data:image/jpeg;base64,{image_base64}"
        
        # Emit real-time detection results
        socketio.emit('detection_results', result)
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# Existing API routes
@app.route('/api/products', methods=['GET'])
def api_products():
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products').fetchall()
    conn.close()
    return jsonify([dict(product) for product in products])

@app.route('/api/update_stock', methods=['POST'])
def update_stock():
    data = request.json
    product_id = data.get('product_id')
    quantity = data.get('quantity')
    action = data.get('action')  # 'add', 'remove', 'set'
    
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    
    if not product:
        conn.close()
        return jsonify({'success': False, 'error': 'Product not found'})
    
    current_stock = product['current_stock']
    
    if action == 'add':
        new_stock = current_stock + quantity
        transaction_type = 'restock'
    elif action == 'remove':
        new_stock = current_stock - quantity
        transaction_type = 'sale'
    else:  # set
        new_stock = quantity
        transaction_type = 'adjustment'
    
    # Update product stock
    conn.execute('UPDATE products SET current_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (new_stock, product_id))
    
    # Record transaction
    conn.execute('''
        INSERT INTO transactions (product_id, transaction_type, quantity, previous_stock, new_stock, notes)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (product_id, transaction_type, abs(quantity), current_stock, new_stock, data.get('notes', '')))
    
    conn.commit()
    conn.close()
    
    # Emit real-time update
    socketio.emit('stock_update', {
        'product_id': product_id,
        'product_name': product['name'],
        'new_stock': new_stock,
        'action': action
    })
    
    return jsonify({'success': True, 'new_stock': new_stock})

# Page Routes
@app.route('/visual_search')
def visual_search():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('visual_search.html')

@app.route('/voice_control')
def voice_control():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('voice_control.html')

if __name__ == '__main__':
    if not os.path.exists('inventory.db'):
        init_db()
    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('models', exist_ok=True)
    print("AI Inventory System starting...")
    print("YOLO Detector Status:", "Initialized" if detector.is_initialized else "Failed")
    print("Speech Recognizer Status: Initialized")
    socketio.run(app, debug=True, use_reloader=False, host='0.0.0.0', port=5000)