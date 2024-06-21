from flask import Flask, render_template, url_for, flash, redirect, current_app
from flask_login import login_required, current_user
from config import Config
from werkzeug.utils import secure_filename
from PIL import Image
from models import db, Product, User, Category, Order, Review
from forms import ProductForm
from datetime import datetime
import os
import secrets


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    total_products = Product.query.count()
    total_orders = Order.query.count()
    total_sales = db.session.query(db.func.sum(Order.total_price)).scalar()
    total_users = User.query.count()
    recent_orders = Order.query.order_by(Order.created_at.desc()).limit(5).all()

    return render_template('admin/dashboard.html',
                           total_products=total_products,
                           total_orders=total_orders,
                           total_sales=total_sales,
                           total_users=total_users,
                           recent_orders=recent_orders)

@app.route('/admin/add_product', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    product_form = ProductForm()
    product_form.category.choices = [(c.id, c.name) for c in Category.query.order_by('name')]

    if product_form.validate_on_submit():
        Product = Product(
            name=product_form.name.data,
            description=product_form.description.data,
            price=product_form.price.data,
            stock=product_form.stock.data,
            category_id=product_form.category.data
        )

        db.session.add(Product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/add_product.html', product_form=product_form)



if __name__=='__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 