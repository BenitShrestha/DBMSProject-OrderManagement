from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import logging

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:xvst2z1bpk@localhost/order_management_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Updated Database Models with Additional Features
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    orders = db.relationship('Order', backref='user', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    order_items = db.relationship('OrderItem', backref='product', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending', nullable=False)
    shipping_address = db.Column(db.String(255), nullable=True)
    order_items = db.relationship('OrderItem', backref='order', lazy=True)
    payment = db.relationship('Payment', uselist=False, backref='order', lazy=True)
    cancelled_order = db.relationship('CancelledOrder', uselist=False, backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    amount_paid = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='Pending', nullable=False)

class CancelledOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False)
    cancelled_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reason = db.Column(db.String(255), nullable=True)

# Enhanced Routes with More Features
@app.route('/')
def index():
    try:
        products = Product.query.all()
        users = User.query.all()
        orders = Order.query.all()
        return render_template('index.html', products=products, users=users, orders=orders)
    except Exception as e:
        logger.error(f"Error in index route: {e}")
        flash('An error occurred while loading the page.')
        return render_template('index.html')

@app.route('/add_order', methods=['POST'])
def add_order():
    try:
        # Validate input
        user_id = request.form.get('user_id')
        product_id = request.form.get('product_id')
        quantity = request.form.get('quantity')
        
        if not all([user_id, product_id, quantity]):
            flash('All fields are required!')
            return redirect(url_for('index'))
        
        quantity = int(quantity)
        
        # Fetch user and product
        user = User.query.get(user_id)
        product = Product.query.get(product_id)
        
        if not user or not product:
            flash('Invalid user or product!')
            return redirect(url_for('index'))
        
        # Stock check with more detailed validation
        if product.stock < quantity:
            flash(f'Insufficient stock. Only {product.stock} {product.name}(s) available.')
            return redirect(url_for('index'))
        
        # Calculate total amount with potential for future discounts
        total_amount = product.price * quantity
        
        # Create order with more details
        order = Order(
            user_id=user.id, 
            total_amount=total_amount,
            status='Pending',
            shipping_address=user.address  # Default to user's address
        )
        db.session.add(order)
        db.session.flush()  # Get the order ID
        
        # Create order item
        order_item = OrderItem(
            order_id=order.id, 
            product_id=product.id, 
            quantity=quantity, 
            subtotal=total_amount
        )
        db.session.add(order_item)
        
        # Update product stock
        product.stock -= quantity
        
        # Create payment record
        payment = Payment(
            order_id=order.id,
            payment_method='Not Specified',
            amount_paid=total_amount,
            status='Pending'
        )
        db.session.add(payment)
        
        # Commit all changes
        db.session.commit()
        
        # Log successful order
        logger.info(f"Order {order.id} placed successfully for user {user.name}")
        flash('Order Placed Successfully!')
        return redirect(url_for('index'))
    
    except ValueError:
        flash('Invalid quantity. Please enter a valid number.')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error placing order: {e}")
        flash(f'Error placing order. Please try again.')
        return redirect(url_for('index'))

@app.route('/cancel_order/<int:id>', methods=['POST'])
def cancel_order(id):
    try:
        order = Order.query.get_or_404(id)
        reason = request.form.get('reason', 'No reason provided')
        
        # Prevent cancelling already cancelled or completed orders
        if order.status in ['Cancelled', 'Delivered']:
            flash(f'Cannot cancel order with status {order.status}')
            return redirect(url_for('index'))
        
        # Change order status
        order.status = 'Cancelled'
        
        # Create cancelled order record
        cancelled_order = CancelledOrder(
            order_id=order.id, 
            reason=reason
        )
        db.session.add(cancelled_order)
        
        # Restore product stock
        for item in order.order_items:
            product = item.product
            product.stock += item.quantity
        
        # Update payment status
        if order.payment:
            order.payment.status = 'Cancelled'
        
        db.session.commit()
        
        # Log cancellation
        logger.info(f"Order {id} cancelled. Reason: {reason}")
        flash('Order Cancelled Successfully!')
        return redirect(url_for('index'))
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error cancelling order {id}: {e}")
        flash('Error cancelling order.')
        return redirect(url_for('index'))

@app.route('/add_product', methods=['POST'])
def add_product():
    try:
        name = request.form.get('name')
        price = request.form.get('price')
        stock = request.form.get('stock')
        description = request.form.get('description', '')
        category = request.form.get('category', 'Uncategorized')
        
        # Validate inputs
        if not all([name, price, stock]):
            flash('Name, price, and stock are required!')
            return redirect(url_for('index'))
        
        product = Product(
            name=name, 
            price=float(price), 
            stock=int(stock),
            description=description,
            category=category
        )
        db.session.add(product)
        db.session.commit()
        
        # Log product addition
        logger.info(f"New product added: {name}")
        flash('Product Added Successfully!')
        return redirect(url_for('index'))
    
    except ValueError:
        flash('Invalid price or stock value.')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding product: {e}")
        flash('Error adding product.')
        return redirect(url_for('index'))

def create_initial_data():
    try:
        # Create admin user
        admin_user = User.query.filter_by(email='admin@example.com').first()
        if not admin_user:
            admin_user = User(
                name='Admin', 
                email='admin@example.com', 
                phone='0000000000', 
                address='Admin Headquarters',
                is_admin=True
            )
            db.session.add(admin_user)
        
        # Create initial users
        if User.query.count() < 2:
            users = [
                User(name='John Doe', email='john@example.com', phone='1234567890', address='123 Main St'),
                User(name='Jane Smith', email='jane@example.com', phone='0987654321', address='456 Elm St')
            ]
            db.session.bulk_save_objects(users)
        
        # Create initial products
        if Product.query.count() < 3:
            products = [
                Product(name='Laptop', price=999.99, stock=10, category='Electronics'),
                Product(name='Smartphone', price=599.99, stock=20, category='Electronics'),
                Product(name='Headphones', price=149.99, stock=50, category='Accessories')
            ]
            db.session.bulk_save_objects(products)
        
        db.session.commit()
        logger.info("Initial data created successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating initial data: {e}")

# Call this function in your main block
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_initial_data()  # Add this line
    app.run(debug=True)