import os
import base64
from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from models import db, ProductModel, UserModel, ProductCreate, UserCreate, UserLogin, CartItem, CheckoutRequest
from datetime import datetime, timedelta
import uuid

app = Flask(__name__)
app.secret_key = "super-secret-key-ecommerce"
app.config['JWT_SECRET_KEY'] = "jwt-secret-key-ecommerce"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

db.init_app(app)
jwt = JWTManager(app)

# Create Database tables
with app.app_context():
    db.create_all()
    # Add initial data if empty
    if not ProductModel.query.first():
        initial_products = [
            ProductModel(
                name="Nova Headphones",
                description="Premium wireless noise-cancelling headphones for an immersive experience.",
                price=199.99,
                category="Electronics",
                image_base64=None
            ),
            ProductModel(
                name="Smart Watch Pro",
                description="Tracks your health, notifications, and fitness goals with style.",
                price=249.50,
                category="Wearables",
                image_base64=None
            ),
            ProductModel(
                name="Minimalist Lamp",
                description="Sleek wooden base lamp for a modern and warm workspace ambiance.",
                price=45.00,
                category="Home Decor",
                image_base64=None
            )
        ]
        db.session.bulk_save_objects(initial_products)
        db.session.commit()

# Helper: Convert Image to Base64
def get_image_base64(file):
    if file and file.filename != '':
        file_data = file.read()
        encoded_string = base64.b64encode(file_data).decode('utf-8')
        # Return proper data URL format
        return f"data:{file.content_type};base64,{encoded_string}"
    return None

# --- AUTH ROUTES ---
@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = UserCreate(**request.json)
        if UserModel.query.filter_by(username=data.username).first():
            return jsonify({"error": "User already exists"}), 400
        
        new_user = UserModel(
            username=data.username,
            email=data.email,
            password=data.password # In production, hash this!
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = UserLogin(**request.json)
        user = UserModel.query.filter_by(username=data.username, password=data.password).first()
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401
        
        access_token = create_access_token(identity=data.username, expires_delta=timedelta(hours=24))
        session['username'] = data.username # Store in web session for navbar
        return jsonify(access_token=access_token), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- PRODUCT REST ENDPOINTS ---
@app.route('/api/items', methods=['GET'])
def get_items():
    category = request.args.get('category')
    search = request.args.get('search')
    
    query = ProductModel.query
    if category:
        query = query.filter(ProductModel.category.ilike(category))
    if search:
        query = query.filter(
            (ProductModel.name.ilike(f'%{search}%')) | 
            (ProductModel.description.ilike(f'%{search}%'))
        )
        
    products_list = query.all()
    result = []
    for p in products_list:
        result.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "price": p.price,
            "category": p.category,
            "image_base64": p.image_base64,
            "created_at": p.created_at.isoformat()
        })
    return jsonify(result)

@app.route('/api/items', methods=['POST'])
@jwt_required()
def add_item():
    try:
        data = ProductCreate(**request.json)
        new_product = ProductModel(
            name=data.name,
            description=data.description,
            price=data.price,
            category=data.category,
            image_base64=data.image_base64
        )
        db.session.add(new_product)
        db.session.commit()
        return jsonify({
            "id": new_product.id,
            "name": new_product.name,
            "message": "Product created"
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/items/<int:item_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_item_api(item_id):
    product = ProductModel.query.get(item_id)
    if not product:
        return jsonify({"error": "Item not found"}), 404
    
    try:
        # Check if it's JSON or Form Data
        if request.is_json:
            data = ProductCreate(**request.json)
            product.name = data.name
            product.description = data.description
            product.price = data.price
            product.category = data.category
            product.image_base64 = data.image_base64
        else:
            # Handle Form Data (File Upload)
            if 'name' in request.form: product.name = request.form.get('name')
            if 'description' in request.form: product.description = request.form.get('description')
            if 'price' in request.form: product.price = float(request.form.get('price'))
            if 'category' in request.form: product.category = request.form.get('category')
            
            file = request.files.get('image')
            if file and file.filename != '':
                product.image_base64 = get_image_base64(file)
        
        db.session.commit()
        return jsonify({"message": "Product updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/items/<int:item_id>', methods=['DELETE'])
@jwt_required()
def delete_item(item_id):
    product = ProductModel.query.get(item_id)
    if not product:
        return jsonify({"error": "Item not found"}), 404
    
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": "Item deleted"}), 200

# --- CART & CHECKOUT ---
@app.route('/api/cart/add', methods=['POST'])
def add_to_cart():
    item_id = request.json.get('product_id')
    product = ProductModel.query.get(item_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    
    if 'cart' not in session:
        session['cart'] = []
    
    cart = session['cart']
    found = False
    for c_item in cart:
        if c_item['id'] == item_id:
            c_item['quantity'] += 1
            found = True
            break
    
    if not found:
        cart.append({
            "id": product.id,
            "quantity": 1
        })
    
    session['cart'] = cart
    session.modified = True
    return jsonify({"message": "Added to cart", "cart_count": len(session['cart'])})

@app.route('/api/cart/remove', methods=['POST'])
def remove_from_cart():
    item_id = request.json.get('product_id')
    if 'cart' not in session:
        return jsonify({"error": "Cart is empty"}), 400
    
    session['cart'] = [item for item in session['cart'] if item['id'] != item_id]
    session.modified = True
    return jsonify({"message": "Removed from cart", "cart_count": len(session['cart'])})

# Helper: Hydrate Cart from DB
def get_cart_details():
    cart = session.get('cart', [])
    detailed_cart = []
    total = 0
    for item in cart:
        product = ProductModel.query.get(item['id'])
        if product:
            item_total = product.price * item['quantity']
            total += item_total
            detailed_cart.append({
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "category": product.category,
                "image_base64": product.image_base64,
                "quantity": item['quantity'],
                "total": item_total
            })
    return detailed_cart, total

@app.route('/api/checkout', methods=['POST'])
def checkout():
    detailed_cart, total = get_cart_details()
    if not detailed_cart:
        return jsonify({"error": "Cart is empty"}), 400
    
    try:
        data = CheckoutRequest(**request.json)
        order_summary = {
            "order_id": str(uuid.uuid4()),
            "items": detailed_cart,
            "total": total,
            "status": "Paid",
            "payment": data.payment_method,
            "address": data.address
        }
        session['cart'] = [] # Clear cart
        session.modified = True
        return jsonify({"message": "Order processed successfully", "order": order_summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/login')
def login_page():
    return render_template('login.html', cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/register')
def register_page():
    return render_template('register.html', cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/logout')
def logout():
    session.pop('username', None) # Clear web session
    return redirect(url_for('home'))

# --- PAGES (FRONTEND) ---
@app.route('/')
def home():
    cat = request.args.get('category')
    search = request.args.get('search')
    
    query = ProductModel.query
    if cat:
        query = query.filter_by(category=cat)
    if search:
        query = query.filter(ProductModel.name.ilike(f'%{search}%'))
        
    display_products = query.all()
    categories = sorted(list(set(p.category for p in ProductModel.query.all())))
    return render_template('home.html', products=display_products, categories=categories, cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/product/<int:p_id>')
def product_detail(p_id):
    product = ProductModel.query.get(p_id)
    if not product:
        return "Product Not Found", 404
    return render_template('product_detail.html', product=product, cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/edit/<int:p_id>', methods=['GET', 'POST'])
def edit_page(p_id):
    product = ProductModel.query.get(p_id)
    if not product:
        return "Product Not Found", 404
    
    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        product.category = request.form.get('category')
        product.description = request.form.get('description')
        
        file = request.files.get('image')
        if file and file.filename != '':
            product.image_base64 = get_image_base64(file)
        
        db.session.commit()
        flash("Product updated successfully!")
        return redirect(url_for('product_detail', p_id=product.id))
        
    return render_template('edit.html', product=product, cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/upload', methods=['GET', 'POST'])
def upload_page():
    if request.method == 'POST':
        name = request.form.get('name')
        price = float(request.form.get('price'))
        category = request.form.get('category')
        description = request.form.get('description')
        file = request.files.get('image')
        
        image_base64 = get_image_base64(file)
        
        new_product = ProductModel(
            name=name,
            price=price,
            category=category,
            description=description,
            image_base64=image_base64
        )
        db.session.add(new_product)
        db.session.commit()
        
        flash("Product uploaded successfully!")
        return redirect(url_for('home'))
        
    return render_template('upload.html', cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/cart')
def cart_page():
    detailed_cart, total = get_cart_details()
    return render_template('cart.html', cart=detailed_cart, total=total, cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/checkout')
def checkout_view():
    detailed_cart, total = get_cart_details()
    if not detailed_cart:
        return redirect(url_for('cart_page'))
    return render_template('checkout.html', total=total, cart_count=len(session.get('cart', [])), username=session.get('username'))

@app.route('/results')
def results_page():
    order_id = request.args.get('order_id')
    status = request.args.get('status', 'success')
    return render_template('results.html', order_id=order_id, status=status, cart_count=0, username=session.get('username'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
