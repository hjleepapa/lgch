from flask import Flask, render_template, request # Added request
import os
from dotenv import load_dotenv
import hashlib
from extensions import db, login_manager, ckeditor, bootstrap, migrate
from flask_login import current_user # Import current_user
import smtplib

# --- Global Helper Functions & Configuration ---
def generate_gravatar_url(email, size=80, default_image='mp', rating='g'):
    """
    Generates a Gravatar URL for a given email address.

    :param email: The email address (string).
    :param size: Size of the avatar in pixels (integer).
    :param default_image: Default image type (e.g., 'mp', 'identicon', '404').
    :param rating: Rating of the avatar (e.g., 'g', 'pg', 'r', 'x').
    :return: The Gravatar URL (string).
    """
    if email is None: # Handle None email gracefully
        email = ''
    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    # Always use HTTPS for Gravatar URLs
    return f"https://www.gravatar.com/avatar/{email_hash}?s={size}&d={default_image}&r={rating}"

load_dotenv() # It's common to load dotenv at the module level or early in create_app

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
    # Centralized database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI")
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Initialize extensions

    db.init_app(app)
    ckeditor.init_app(app)
    bootstrap.init_app(app)
    migrate.init_app(app, db) # Initialize Flask-Migrate

    # --- Configure Login Manager ---
    # This must be done after initializing the extensions and before registering blueprints that use it.
    login_manager.init_app(app)
    login_manager.login_view = 'blog.login' # Point to the blueprint's login route

    # The user_loader callback needs the User model.
    from blog_project.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))
    
    # --- Register Blueprints ---
    # Import and register blueprints after all extensions are fully configured.
    # This prevents circular dependencies where blueprint code might need an initialized extension.
    from blog_project.main import blog_bp
    app.register_blueprint(blog_bp, url_prefix='/blog_project')

    from vapi_todo import vapi_flask_bp
    app.register_blueprint(vapi_flask_bp) # The url_prefix is already set in routes.py

    from syfw_todo import syfw_todo_bp # This import might need adjustment if it has websockets too
    app.register_blueprint(syfw_todo_bp)

    from blnd_todo.routes import blnd_todo_bp
    app.register_blueprint(blnd_todo_bp)

    from lgch_todo import lgch_todo_bp
    app.register_blueprint(lgch_todo_bp)

    # --- Main Application Routes ---
    @app.route('/', methods=["GET", "POST"])
    def home():
        msg_sent = False
        error_message = None
        if request.method == "POST":
            # This is the contact form submission from the homepage
            name = request.form.get("name")
            email_from = request.form.get("email")
            phone = request.form.get("phone")
            message_body = request.form.get("message")

            if not all([name, email_from, message_body]):
                error_message = "Please fill in all required fields (Name, Email, Message)."
            else:
                mail_server = os.environ.get('MAIL_SERVER')
                mail_port = int(os.environ.get('MAIL_PORT', 587))
                mail_username = os.environ.get('MAIL_USERNAME')
                mail_password = os.environ.get('MAIL_PASSWORD')
                mail_receiver = os.environ.get('MAIL_RECEIVER')

                if not all([mail_server, mail_username, mail_password, mail_receiver]):
                    print("Email configuration is incomplete for main contact form.")
                    error_message = "Message could not be sent due to a server configuration issue."
                else:
                    email_subject = f"New Contact Form Submission from {name} (Main Site)"
                    full_email_message = (
                        f"Subject: {email_subject}\n\n"
                        f"Name: {name}\nEmail: {email_from}\nPhone: {phone if phone else 'Not provided'}\n\nMessage:\n{message_body}\n"
                    )

                    try:
                        with smtplib.SMTP(mail_server, mail_port) as server:
                            server.starttls()
                            server.login(mail_username, mail_password)
                            server.sendmail(mail_username, mail_receiver, full_email_message.encode('utf-8'))
                        msg_sent = True
                    except Exception as e:
                        print(f"Error sending email from main contact form: {e}")
                        error_message = "An unexpected error occurred. Please try again later."

        # Always render index.html, passing the status of the form submission
        # The 'current_user' is available globally via the context_processor, so no need to pass it here.
        return render_template('index.html', msg_sent=msg_sent, error=error_message)

    @app.route('/about')
    def about():
        return render_template('about.html')

    @app.route('/blog-tech-spec')
    def blog_tech_spec():
        """Renders the technical specification page for the blog project."""
        return render_template('blog_tech_spec.html')

    @app.route('/vapi-tech-spec')
    def vapi_tech_spec():
        """Renders the technical specification page for the VAPI todo project."""
        return render_template('vapi_tech_spec.html')

    @app.route('/syfw-tech-spec')
    def syfw_tech_spec():
        """Renders the technical specification page for the SYFW todo project."""
        return render_template('syfw_tech_spec.html')

    @app.route('/blnd-tech-spec')
    def blnd_tech_spec():
        """Renders the technical specification page for the BLND todo project."""
        return render_template('blnd_tech_spec.html')

    @app.route('/lgch-tech-spec')
    def lgch_tech_spec():
        """Renders the technical specification page for the LangGraph + MCP + Langflow todo project."""
        return render_template('lgch_tech_spec.html')

    # --- Context Processors ---
    @app.context_processor
    def utility_processor():
        return dict(gravatar_url=generate_gravatar_url, user=current_user)

    return app

# Create the application instance for WSGI servers like Gunicorn to find.
app = create_app()

if __name__ == '__main__':
    # This is for local development only.
    # app = create_app() # Ensure the app is created before running
    app.run(debug=True)