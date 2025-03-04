from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:xvst2z1bpk@localhost/order_db'  # Change credentials as needed
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app)

# Database Models
class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    address = db.Column(db.String(255), nullable=True)
    orders = db.relationship('Order', backref='customer', lazy=True)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='Pending')
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)

# Routes
@app.route('/')
def index():
    orders = Order.query.all()
    customers = Customer.query.all()  # Fetch all customers from the database
    return render_template('index.html', orders=orders, customers=customers)

@app.route('/add_order', methods=['POST'])
def add_order():
    product_name = request.form['product_name']
    quantity = request.form['quantity']
    price = request.form['price']
    customer_id = request.form['customer_id']
    
    order = Order(product_name=product_name, quantity=int(quantity), price=float(price), customer_id=int(customer_id))
    db.session.add(order)
    db.session.commit()
    flash('Order Added Successfully!')
    return redirect(url_for('index'))

@app.route('/update_order/<int:id>', methods=['POST'])
def update_order(id):
    order = Order.query.get(id)
    order.status = request.form['status']
    db.session.commit()
    flash('Order Updated Successfully!')
    return redirect(url_for('index'))

@app.route('/delete_order/<int:id>')
def delete_order(id):
    order = Order.query.get(id)
    db.session.delete(order)
    db.session.commit()
    flash('Order Deleted Successfully!')
    return redirect(url_for('index'))

@app.route('/customers')
def customers():
    customers = Customer.query.all()
    return jsonify([{"id": c.id, "name": c.name, "email": c.email, "phone": c.phone, "address": c.address} for c in customers])

@app.route('/orders')
def get_orders():
    orders = Order.query.all()
    return jsonify([{
        "id": order.id,
        "product_name": order.product_name,
        "quantity": order.quantity,
        "price": order.price,
        "status": order.status,
        "customer_name": order.customer.name
    } for order in orders])

if __name__ == '__main__':
    # Ensure the app context is active when creating the tables
    with app.app_context():
        db.create_all()
    app.run(debug=True)
