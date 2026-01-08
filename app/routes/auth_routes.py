from flask import Blueprint, render_template, request, redirect, url_for, session, flash, current_app, send_from_directory
from app.utils import get_db_connection
import mysql.connector

auth_bp = Blueprint('auth', __name__)

@auth_bp.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Determine the correct query based on role
        if role == "admin":
            query = "SELECT * FROM admin WHERE admin_email = %s"
        elif role == "policymaker":
            query = "SELECT * FROM policymaker WHERE pm_email = %s"
        else:
            query = None

        if not query:
            flash("Incorrect credentials. Please try again.", "danger")
            return redirect(url_for('auth.login'))

        cursor.execute(query, (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            flash("Incorrect credentials. Please try again.", "danger")
            return redirect(url_for('auth.login'))

        stored_pw = user.get("admin_pwrd") if role == "admin" else user.get("pm_pwrd")
        temp_pw = user.get("temp_pwrd")
        first_login = user.get("first_login")

        if password == stored_pw or (first_login and password == temp_pw):
            session["email"] = email
            session["role"] = role
            session["is_main_admin"] = user.get("is_main_admin", False)

            if first_login:
                session["force_password_reset"] = True
                flash("You must reset your password before continuing.", "warning")
                return redirect(url_for("auth.reset_password"))
            else:
                flash("Login successful.", "success")
                return redirect(url_for("auth.dashboard"))
        else:
            flash("Incorrect credentials. Please try again.", "danger")
            return redirect(url_for('auth.login'))
    
    return render_template("auth/login.html")

@auth_bp.route("/dashboard")
def dashboard():
    if "email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    if session.get("role") == "admin":
        return redirect(url_for("admin.upload_file"))
    elif session.get("role") == "policymaker":
        return redirect(url_for("policymaker.overview"))
    else:
        flash("Invalid role.", "danger")
        return redirect(url_for("auth.login"))

@auth_bp.route("/reset_password", methods=["GET", "POST"])
def reset_password():
    if "force_password_reset" not in session:
        flash("Unauthorized access. Please login again.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        new_pw = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()
        email = session.get("email")
        role = session.get("role")

        if not new_pw or not confirm_pw:
            flash("Both fields are required.", "danger")
            return redirect(url_for("auth.reset_password"))

        if new_pw != confirm_pw:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.reset_password"))

        conn = get_db_connection()
        cursor = conn.cursor()

        if role == "admin":
            cursor.execute("""
                UPDATE admin SET admin_pwrd = %s, first_login = FALSE, temp_pwrd = NULL
                WHERE admin_email = %s
            """, (new_pw, email))
        elif role == "policymaker":
            cursor.execute("""
                UPDATE policymaker SET pm_pwrd = %s, first_login = FALSE, temp_pwrd = NULL
                WHERE pm_email = %s
            """, (new_pw, email))

        conn.commit()
        cursor.close()
        conn.close()

        session.pop("force_password_reset", None)
        flash("Password reset successfully. Please continue.", "success")
        return redirect(url_for("auth.dashboard"))

    return render_template("auth/reset_password.html")

@auth_bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "email" not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current_pw = request.form.get("current_password")
        new_pw = request.form.get("new_password")
        confirm_pw = request.form.get("confirm_password")
        role = session.get("role")
        email = session.get("email")

        if new_pw != confirm_pw:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("auth.change_password"))
        
        if new_pw == current_pw:
            flash("New password cannot be the same as the current password.", "warning")
            return redirect(url_for("auth.change_password"))

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if role == "admin":
            cursor.execute("SELECT admin_pwrd, temp_pwrd, first_login FROM admin WHERE admin_email = %s", (email,))
        else:
            cursor.execute("SELECT pm_pwrd, temp_pwrd, first_login FROM policymaker WHERE pm_email = %s", (email,))
        user = cursor.fetchone()

        current_pw_stored = user["admin_pwrd"] if role == "admin" else user["pm_pwrd"]
        temp_pw_stored = user["temp_pwrd"]

        if current_pw not in [current_pw_stored, temp_pw_stored]:
            flash("Current password incorrect.", "danger")
            return redirect(url_for("auth.change_password"))

        # Update password and disable first_login
        if role == "admin":
            cursor.execute("UPDATE admin SET admin_pwrd = %s, first_login = FALSE WHERE admin_email = %s", (new_pw, email))
        else:
            cursor.execute("UPDATE policymaker SET pm_pwrd = %s, first_login = FALSE WHERE pm_email = %s", (new_pw, email))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Password changed successfully!", "success")
        return redirect(request.referrer or url_for("auth.dashboard"))

    return render_template("auth/change_password.html")

@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("auth.login"))
