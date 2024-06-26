from flask import Flask, render_template, url_for, flash, redirect, current_app, request
from flask_login import login_required, current_user, LoginManager, login_user, logout_user
from flask_bcrypt import Bcrypt
from config import Config
from werkzeug.utils import secure_filename
from PIL import Image
from models import db, Product, User, Category, Order, Review, Address, SupportTicket
from sqlalchemy.orm import joinedload, Session
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, func, event, distinct
from flask_bootstrap import Bootstrap
from flask_migrate import Migrate
from forms import ProductForm, LoginForm, RegistrationForm, ReviewForm, AddressForm, SupportTicketForm
from datetime import datetime
import os
import secrets


app = Flask(__name__)
app.config.from_object(Config)
year = datetime.now().year
migrate = Migrate(app, db)
Bootstrap(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

db.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    login_form = LoginForm()

    if login_form.validate_on_submit():

        email=login_form.email.data
        password=login_form.password.data
        
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('Incorrect credentials!', 'warning')
            return redirect(url_for('login'))
        elif not bcrypt.check_password_hash(user.password, password):
                flash('Incorrect credentials!, please try again.', 'warning')
                return redirect(url_for('login'))
        else:
            # Update status to 'active'
            new_status = request.form.get('status')
            if new_status not in ['active', 'inactive']:
                flash('Invalid status.', 'warning')
                return redirect(url_for('login'))
        
            user.status = new_status
            db.session.commit()
            login_user(user)
            
            flash('You have been logged in successfully!', 'success')
            next_page = request.args.get('next')

            if next_page:
                return redirect(next_page)
            else:
                return redirect(url_for('home'))
                
    return render_template("login.html", login_form=login_form)

@app.route('/logout')
@login_required
def logout():
    try:
        # Update status to 'inactive'
        new_status = request.args.get('status', 'inactive')
        print(new_status)
        current_user.status = new_status
        db.session.commit()
        print(f"Status after commit: {current_user.status}")

        logout_user()
        flash("You have been logged out!", 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error during logout: {e}")
        flash("An error occurred during logout.", 'error')
    finally:
        db.session.close()

    return redirect(url_for('login'))


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
                           recent_orders=recent_orders
                           )

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
            brand=product_form.brand.data,
            sku=product_form.sku.data,
            price=product_form.price.data,
            discount_price=product_form.discount_price.data,
            stock=product_form.stock.data,
            category_id=product_form.category.data
        )

        db.session.add(Product)
        db.session.commit()
        flash('Your product has been created!', 'success')
        return redirect(url_for('admin_dashboard'))
    
    return render_template('admin/add_product.html', product_form=product_form, title='New Product', legend='New Product')

@app.route("/review/new/<int:product_id>", methods=['GET', 'POST'])
@login_required
def new_review(product_id):
    review_form = ReviewForm()
    if review_form.validate_on_submit():
        review = Review(
            rating=review_form.rating.data, 
            review_text=review_form.review_text.data, 
            user_id=current_user.id, 
            product_id=product_id
            )
        db.session.add(review)
        db.session.commit()
        flash('Your review has been posted!', 'success')
        return redirect(url_for('product', product_id=product_id))
    return render_template('create_review.html', title='New Review', review_form=review_form, legend='New Review')


@app.route("/register", methods=['GET', 'POST'])
def register():
    register_form = RegistrationForm()
    if register_form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(register_form.password.data).decode('utf-8')
        user = User(
            username=register_form.username.data, 
            email=register_form.email.data, 
            password_hash=hashed_password
            )
        db.session.add(user)
        db.session.commit()
        flash('Your account has been created!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', register_form=register_form)

@app.route("/address/new", methods=['GET', 'POST'])
@login_required
def new_address():
    address_form = AddressForm()
    if address_form.validate_on_submit():
        address = Address(
            user_id=current_user.id, 
            address_type=address_form.address_type.data, 
            street=address_form.street.data,
            city=address_form.city.data, 
            state=address_form.state.data, 
            zip_code=address_form.zip_code.data, 
            country=address_form.country.data
            )
        db.session.add(address)
        db.session.commit()
        flash('Your address has been saved!', 'success')
        return redirect(url_for('account'))
    return render_template('create_address.html', title='New Address', address_form=address_form, legend='New Address')

@app.route("/support/new", methods=['GET', 'POST'])
@login_required
def new_ticket():
    support_ticket_form = SupportTicketForm()
    if support_ticket_form.validate_on_submit():
        ticket = SupportTicket(
            user_id=current_user.id, 
            subject=support_ticket_form.subject.data, 
            description=support_ticket_form.description.data, 
            priority=support_ticket_form.priority.data
            )
        db.session.add(ticket)
        db.session.commit()
        flash('Your support ticket has been submitted!', 'success')
        return redirect(url_for('account'))
    return render_template('create_ticket.html', title='New Support Ticket', support_ticket_form=support_ticket_form, legend='New Support Ticket')

@app.routje("/", methods=['GET', 'POST'])
@login_required
def shop_collection():
    products = Product.query.all()
    return render_template("shop.html", products=products)

if __name__=='__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 