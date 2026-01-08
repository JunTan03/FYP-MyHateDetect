import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

from flask import Flask, render_template
from app.routes import register_blueprints
import os

app = Flask(__name__, template_folder='app/templates', static_folder='app/static')

# Secret key
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_default_dev_key')

# MySQL Config
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'myhatedetect'

# Upload folder
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Register Blueprints
register_blueprints(app)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error/500.html'), 500

# Run server
if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)

