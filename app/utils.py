import chardet
import pandas as pd
from io import StringIO
import os
import mysql.connector
from flask import current_app

def get_db_connection():
    return mysql.connector.connect(
        host=current_app.config['MYSQL_HOST'],
        user=current_app.config['MYSQL_USER'],
        password=current_app.config['MYSQL_PASSWORD'],
        database=current_app.config['MYSQL_DB'],
        connection_timeout=300,
        charset="utf8mb4",
        use_unicode=True 
    )

def read_csv_with_encoding(filepath):
    try:
        # Detect file encoding first
        with open(filepath, 'rb') as f:
            result = chardet.detect(f.read(100000))  # Read first 100k bytes to guess
        encoding = result['encoding'] or 'utf-8'

        # Read CSV with detected encoding, replace bad characters if any
        df = pd.read_csv(filepath, encoding=encoding, errors='replace')
        return df

    except Exception as e:
        return str(e)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'csv'}

progress = {
    "percent": 0,
    "status": "idle"
}

def set_progress(value, status="processing"):
    progress["percent"] = value
    progress["status"] = status

def get_progress():
    return progress

def reset_progress():
    progress["percent"] = 0
    progress["status"] = "idle"
