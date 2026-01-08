from flask import (
    Blueprint, render_template, request, flash,
    redirect, url_for, current_app, session, jsonify
)
import os
import pandas as pd
import chardet
from werkzeug.utils import secure_filename
from threading import Thread

from app.utils import (
    allowed_file, get_db_connection,
    set_progress, get_progress, reset_progress
)
from app.stage_predict import predict_toxic_and_hate_type
import secrets
import string


admin_bp = Blueprint('admin', __name__)


def run_in_context(app, func, *args, **kwargs):
    with app.app_context():
        func(*args, **kwargs)

def generate_temp_password(length=10):
    characters = string.ascii_letters + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))

def register_new_user(role, email):
    password = generate_temp_password()
    conn = get_db_connection()
    cursor = conn.cursor()

    if role == 'admin':
        cursor.execute("INSERT INTO admin (admin_email, temp_pwrd, first_login) VALUES (%s, %s, TRUE)", (email, password))
    elif role == 'policymaker':
        cursor.execute("INSERT INTO policymaker (pm_email, temp_pwrd, first_login) VALUES (%s, %s, TRUE)", (email, password))

    conn.commit()
    cursor.close()
    conn.close()
    return password

def background_task(filepath, month, filename):
    try:
        reset_progress()
        set_progress(5, "Connecting to database...")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            month_fmt = pd.to_datetime(month, format="%B %Y").strftime("%Y-%m")
        except (ValueError, TypeError):
            month_fmt = pd.to_datetime(month, errors="coerce").strftime("%Y-%m")

        cursor.execute(
            "SELECT COUNT(*) AS count FROM tweets WHERE file_name = %s AND month = %s",
            (filename, month_fmt)
        )
        if cursor.fetchone()["count"] > 0:
            set_progress(100, "Duplicate file. Skipped.")
            return

        with open(filepath, 'rb') as f:
            raw_data = f.read(100000)
        encoding = chardet.detect(raw_data)['encoding'] or 'utf-8'
        set_progress(10, f"Reading CSV (encoding={encoding})...")

        try:
            chunks = pd.read_csv(
                filepath,
                chunksize=100_000,
                encoding=encoding,
                on_bad_lines='skip',
                encoding_errors="ignore"
            )
        except Exception:
            chunks = pd.read_csv(
                filepath,
                chunksize=100_000,
                encoding="ISO-8859-1",
                on_bad_lines='skip',
                encoding_errors="ignore"
            )

        total_rows = 0
        chunk_index = 0
        all_chunks = []

        for chunk in chunks:
            if "text" in chunk.columns:
                raw_texts = chunk["text"].astype(str).tolist()
            elif "tweet" in chunk.columns:
                raw_texts = chunk["tweet"].astype(str).tolist()
            else:
                set_progress(100, "Missing 'text' or 'tweet' column.")
                return

            hate_preds, hate_type_dict, cleaned_texts = predict_toxic_and_hate_type(
                raw_texts,
                batch_size=64
            )
            set_progress(20 + chunk_index * 5, f"Classifying chunk {chunk_index + 1}...")

            hate_types_list = []
            for i, flag in enumerate(hate_preds):
                if flag == 1:
                    labels_list = hate_type_dict.get(i, [])
                    if labels_list:
                        hate_types_list.append(",".join(labels_list))
                    else:
                        hate_types_list.append("not_and_other_hate_speech")
                else:
                    hate_types_list.append("")

            chunk["tweet"] = raw_texts
            chunk["clean_tweet"] = cleaned_texts
            chunk["hate"] = ["hate" if p == 1 else "non-hate" for p in hate_preds]
            chunk["hate_types"] = hate_types_list
            chunk["month"] = month_fmt
            chunk["file_name"] = filename

            cols = ["tweet", "clean_tweet", "hate", "hate_types", "month", "file_name"]
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO tweets ({', '.join(cols)}) VALUES ({placeholders})"
            values = chunk[cols].values.tolist()

            for start in range(0, len(values), 2000):
                cursor.executemany(sql, values[start:start + 2000])
                conn.commit()

            all_chunks.append(chunk.copy())
            total_rows += len(chunk)
            chunk_index += 1

        if total_rows == 0:
            set_progress(100, "⚠️ No tweets processed.")
            return

        final_df = pd.concat(all_chunks, ignore_index=True)
        os.makedirs("data", exist_ok=True)
        final_df.to_csv("processed_data/tweets.csv", index=False, encoding="utf-8")

        cursor.close()
        conn.close()
        set_progress(100, "✅ Upload and processing complete.")

    except Exception as e:
        print("❌ Upload error:", e)
        set_progress(100, "❌ Processing error.")

# ────────────────────────────────────────────────────────────────────────────
# Flask Routes
# ────────────────────────────────────────────────────────────────────────────
@admin_bp.route("/upload_progress")
def upload_progress():
    return jsonify(get_progress())
    
@admin_bp.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        month = request.form.get("month")
        file = request.files.get("file")

        if not file or file.filename == "" or not allowed_file(file.filename):
            flash("Invalid file", "danger")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        app = current_app._get_current_object()
        Thread(target=run_in_context, args=(app, background_task, filepath, month, filename)).start()

        return render_template("admin/upload_progress.html")

    # === Inject list of available months for Flatpickr ===
    # Pass uploaded months for client-side warning
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT DISTINCT month FROM tweets")
    existing_months = [row["month"] for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    return render_template("admin/upload.html", existing_months=existing_months)


@admin_bp.route("/register_csv", methods=["GET", "POST"])
def register_csv():
    if session.get("role") != "admin":
        flash("Unauthorized", "danger")
        return redirect(url_for("auth.dashboard"))

    is_main_admin = session.get("is_main_admin", False)
    created_users = []
    skipped_users = []

    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or not file.filename.endswith(".csv"):
            flash("Please upload a valid CSV file with 'email' and 'role' columns.", "danger")
            return redirect(request.url)

        df = pd.read_csv(file)
        if 'email' not in df.columns or 'role' not in df.columns:
            flash("CSV must have 'email' and 'role' columns.", "danger")
            return redirect(request.url)

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        for _, row in df.iterrows():
            email = str(row['email']).strip().lower()
            role_code = str(row['role']).strip()

            # Enforce role upload restriction
            if not is_main_admin and role_code != '2':
                skipped_users.append({"email": email, "reason": "Only main admin can upload role 1 (admin)"})
                continue

            if role_code == '1':
                role = 'admin'
                email_col = 'admin_email'
            elif role_code == '2':
                role = 'policymaker'
                email_col = 'pm_email'
            else:
                skipped_users.append({"email": email, "reason": "Invalid role code"})
                continue

            cursor.execute("""
                SELECT email FROM (
                    SELECT LOWER(admin_email) AS email FROM admin
                    UNION
                    SELECT LOWER(pm_email) AS email FROM policymaker
                ) AS all_users
                WHERE email = %s
            """, (email,))
            if cursor.fetchone():
                skipped_users.append({"email": email, "reason": "Already exists in system"})
                continue

            temp_pw = generate_temp_password()
            cursor.execute(
                f"INSERT INTO {role} ({email_col}, temp_pwrd, first_login) VALUES (%s, %s, TRUE)",
                (email, temp_pw)
            )
            created_users.append({"email": email, "role": role, "password": temp_pw})

        conn.commit()
        cursor.close()
        conn.close()

        if created_users:
            flash(f"✅ {len(created_users)} user(s) created successfully.", "success")
        if skipped_users:
            flash(f"⚠️ {len(skipped_users)} user(s) skipped due to duplication or restriction.", "warning")

    return render_template("admin/register_csv.html", created_users=created_users, skipped_users=skipped_users)

@admin_bp.route("/user_list")
def user_list():
    if session.get("role") != "admin":
        flash("Unauthorized access.", "danger")
        return redirect(url_for("auth.dashboard"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT 'admin' AS role, admin_email AS email, temp_pwrd, is_main_admin FROM admin")
    admins = cursor.fetchall()
    cursor.execute("SELECT 'policymaker' AS role, pm_email AS email, temp_pwrd FROM policymaker")
    pms = cursor.fetchall()

    cursor.close()
    conn.close()

    main_admin = [a for a in admins if a.get("is_main_admin")]
    other_admins = [a for a in admins if not a.get("is_main_admin")]
    all_users = main_admin + other_admins + pms

    return render_template("admin/user_list.html", users=all_users)

@admin_bp.route("/update_user", methods=["POST"])
def update_user():
    if session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"})

    is_main_admin = session.get("is_main_admin", False)

    original_email = request.form.get("original_email")
    original_role = request.form.get("original_role")
    new_email = request.form.get("new_email").strip().lower()
    new_role = request.form.get("role")
    admin_password = request.form.get("admin_password")

    if not all([original_email, original_role, new_email, new_role, admin_password]):
        return jsonify({"error": "Missing fields"})

    # Restriction: Only main admin can edit admins
    if not is_main_admin and (original_role == "admin" or new_role == "admin"):
        return jsonify({"error": "You are not allowed to modify admin users."})

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT admin_pwrd FROM admin WHERE admin_email = %s", (session["email"],))
    admin = cursor.fetchone()
    if not admin or admin["admin_pwrd"] != admin_password:
        return jsonify({"error": "Invalid admin password"}), 401

    # Check for duplicate email
    if new_email != original_email:
        cursor.execute("SELECT admin_email FROM admin WHERE admin_email = %s", (new_email,))
        if cursor.fetchone():
            return jsonify({"error": f"Email '{new_email}' already exists in admin list."})
        cursor.execute("SELECT pm_email FROM policymaker WHERE pm_email = %s", (new_email,))
        if cursor.fetchone():
            return jsonify({"error": f"Email '{new_email}' already exists in policymaker list."})

    # Delete old user
    if original_role == "admin":
        cursor.execute("DELETE FROM admin WHERE admin_email = %s", (original_email,))
    else:
        cursor.execute("DELETE FROM policymaker WHERE pm_email = %s", (original_email,))

    # Insert new user
    if new_role == "admin":
        cursor.execute("INSERT INTO admin (admin_email, temp_pwrd, first_login) VALUES (%s, NULL, FALSE)", (new_email,))
    else:
        cursor.execute("INSERT INTO policymaker (pm_email, temp_pwrd, first_login) VALUES (%s, NULL, FALSE)", (new_email,))

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"success": True})

@admin_bp.route("/delete_user", methods=["POST"])
def delete_user():
    if session.get("role") != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    is_main_admin = session.get("is_main_admin", False)

    data = request.get_json()
    emails = data.get("emails", [])
    roles = data.get("roles", [])
    password = data.get("password")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT admin_pwrd FROM admin WHERE admin_email = %s", (session["email"],))
    result = cursor.fetchone()

    if not result or result["admin_pwrd"] != password:
        return jsonify({"error": "Invalid admin password"}), 401

    deleted, skipped = [], []
    for email, role in zip(emails, roles):
        # Restriction: normal admins cannot delete admin accounts
        if not is_main_admin and role == "admin":
            skipped.append(email)
            continue

        if role == "admin":
            cursor.execute("DELETE FROM admin WHERE admin_email = %s", (email,))
        elif role == "policymaker":
            cursor.execute("DELETE FROM policymaker WHERE pm_email = %s", (email,))
        deleted.append(email)

    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"deleted": deleted, "skipped": skipped})

