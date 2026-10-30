import os
import io
import csv
from datetime import datetime, date
from pathlib import Path
from functools import wraps
import joblib
import mysql.connector
from mysql.connector import Error
from flask import (Flask, render_template, request, redirect, url_for, session,
                   flash, jsonify, Response)
from werkzeug.security import generate_password_hash, check_password_hash
from ai_service import get_student_risk_assessment, get_student_ai_insights, handle_natural_language_query

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "local-demo-change-this-secret")
BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / "models" / "performance_model.joblib"

DB = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "student_performance")
}

FEATURES = ["math_marks", "science_marks", "english_marks", "attendance", "study_hours", "previous_score"]

def connect():
    return mysql.connector.connect(**DB)

def one(sql, params=()):
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()

def all_rows(sql, params=()):
    conn = connect()
    try:
        cur = conn.cursor(dictionary=True, buffered=True)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()
        conn.close()

def run(sql, params=()):
    conn = connect()
    try:
        cur = conn.cursor(buffered=True)
        cur.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        cur.close()
        conn.close()

def log_audit(action, entity_type, entity_id=None, details=""):
    try:
        uid = session.get("user_id")
        if uid:
            ip = request.remote_addr or "127.0.0.1"
            run("""INSERT INTO audit_logs (user_id, action, entity_type, entity_id, details, ip_address)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (uid, action, entity_type, entity_id, str(details)[:500], ip))
    except Exception:
        app.logger.exception("Failed writing to audit log")

def required(role=None):
    def deco(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                flash("Please log in first.", "error")
                return redirect(url_for("login"))
            if role and session.get("role") != role:
                flash("You do not have permission to open that page.", "error")
                return redirect(url_for("dashboard"))
            return view(*args, **kwargs)
        return wrapped
    return deco

def get_perf(student_id):
    return one("SELECT * FROM performance WHERE student_id=%s", (student_id,))

def ensure_perf(student_id):
    if not get_perf(student_id):
        run("INSERT INTO performance (student_id) VALUES (%s)", (student_id,))

def predict(perf):
    if not MODEL_PATH.exists():
        return None
    try:
        model = joblib.load(MODEL_PATH)
        return round(float(model.predict([[float(perf[k]) for k in FEATURES]])[0]), 1)
    except Exception:
        app.logger.exception("ML prediction failed")
        return None

@app.context_processor
def inject_globals():
    unread = 0
    unread_queries = 0
    uid = session.get("user_id")
    role = session.get("role")
    if uid:
        try:
            row = one("SELECT COUNT(*) as cnt FROM notifications WHERE user_id=%s AND is_read=0", (uid,))
            unread = row["cnt"] if row else 0

            if role == "student":
                q_row = one("""
                    SELECT COUNT(DISTINCT qm.id) as cnt
                    FROM query_messages qm
                    JOIN student_queries sq ON sq.id = qm.query_id
                    WHERE sq.student_id = %s AND qm.sender_id != %s AND qm.read_at IS NULL
                """, (uid, uid))
                unread_queries = q_row["cnt"] if q_row else 0
            elif role == "teacher":
                q_row = one("""
                    SELECT COUNT(DISTINCT sq.id) as cnt
                    FROM student_queries sq
                    LEFT JOIN query_messages qm ON qm.query_id = sq.id AND qm.sender_id != %s AND qm.read_at IS NULL
                    WHERE (sq.assigned_faculty_id = %s OR sq.assigned_faculty_id IS NULL)
                      AND (sq.status = 'Open' OR qm.id IS NOT NULL)
                """, (uid, uid))
                unread_queries = q_row["cnt"] if q_row else 0
        except Exception:
            pass
    return dict(unread_notification_count=unread, unread_queries_count=unread_queries)

# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("dashboard" if session.get("user_id") else "login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not username or len(password) < 8:
            flash("Enter all fields. Password must be at least 8 characters.", "error")
            return render_template("login.html", mode="register")
        try:
            uid = run("INSERT INTO users (full_name,username,password_hash,role) VALUES (%s,%s,%s,'student')",
                      (name, username, generate_password_hash(password)))
            ensure_perf(uid)

            # Assign default profile
            dept = one("SELECT id FROM departments WHERE code='CE'")
            dept_id = dept["id"] if dept else 1
            eno = f"ENR-{datetime.now().year}-{uid:04d}"
            run("""INSERT INTO student_profiles (student_id, enrollment_no, department_id, semester, division, academic_year)
                   VALUES (%s, %s, %s, 5, 'A', '2026-2027')""", (uid, eno, dept_id))

            log_audit("STUDENT_REGISTER", "users", uid, f"Self-registered student account: {username}")
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except Error as e:
            if getattr(e, "errno", None) == 1062:
                flash("Username already exists. Choose another.", "error")
            else:
                app.logger.exception("Registration error")
                flash("Registration failed. Check MySQL setup.", "error")
    return render_template("login.html", mode="register")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        try:
            user = one("SELECT * FROM users WHERE username=%s", (username,))
        except Error:
            app.logger.exception("Database connection error")
            flash("Database not available. Run schema.sql and check MySQL settings.", "error")
            return render_template("login.html", mode="login")
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session.update(user_id=user["id"], name=user["full_name"], role=user["role"])
            log_audit("USER_LOGIN", "users", user["id"], f"Successful login for {username}")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html", mode="login")

@app.route("/logout")
def logout():
    uid = session.get("user_id")
    if uid:
        log_audit("USER_LOGOUT", "users", uid, "User logged out")
    session.clear()
    return redirect(url_for("login"))

# -------------------------------------------------------------
# Dashboard (Student & Teacher)
# -------------------------------------------------------------

@app.route("/dashboard")
@required()
def dashboard():
    uid = session["user_id"]
    role = session["role"]

    if role == "teacher":
        students = all_rows("""
            SELECT u.id, u.full_name, u.username, sp.enrollment_no,
                   p.math_marks, p.science_marks, p.english_marks, p.attendance, p.study_hours, p.previous_score
            FROM users u
            JOIN performance p ON p.student_id=u.id
            LEFT JOIN student_profiles sp ON sp.student_id=u.id
            WHERE u.role='student'
            ORDER BY u.full_name
        """)
        for s in students:
            s["average"] = round((float(s["math_marks"]) + float(s["science_marks"]) + float(s["english_marks"])) / 3, 1)
            s["prediction"] = predict(s)

        avg_att = round(sum(float(s["attendance"]) for s in students) / len(students), 1) if students else 0
        avg_marks = round(sum(s["average"] for s in students) / len(students), 1) if students else 0

        # At-risk calculation for teachers
        conn = connect()
        cur = conn.cursor(dictionary=True)
        at_risk_students = []
        for s in students:
            ra = get_student_risk_assessment(cur, s["id"])
            if ra["status"] != "On Track":
                at_risk_students.append({
                    "id": s["id"],
                    "full_name": s["full_name"],
                    "enrollment_no": s["enrollment_no"] or f"ID-{s['id']}",
                    "status": ra["status"],
                    "badge_class": ra["badge_class"],
                    "attendance_pct": ra["attendance_pct"],
                    "reasons": ra["reasons"]
                })

        pending_prac = one("SELECT COUNT(*) as cnt FROM practical_submissions WHERE status IN ('Submitted', 'Needs Resubmission')")
        pending_assg = one("SELECT COUNT(*) as cnt FROM assignment_submissions WHERE status='Submitted'")
        pending_corr = one("SELECT COUNT(*) as cnt FROM attendance_correction_requests WHERE status='Pending'")
        cur.close()
        conn.close()

        return render_template("dashboard.html",
                               role="teacher",
                               students=students,
                               student_count=len(students),
                               avg_attendance=avg_att,
                               avg_marks=avg_marks,
                               at_risk_count=len(at_risk_students),
                               at_risk_students=at_risk_students,
                               pending_practicals_count=pending_prac["cnt"] if pending_prac else 0,
                               pending_assignments_count=pending_assg["cnt"] if pending_assg else 0,
                               pending_corrections_count=pending_corr["cnt"] if pending_corr else 0)

    # Student Dashboard
    conn = connect()
    cur = conn.cursor(dictionary=True)
    ensure_perf(uid)
    perf = get_perf(uid)
    values = {k: float(perf[k]) for k in FEATURES}
    estimate = predict(values)

    # Detailed attendance
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status IN ('Present','Late') THEN 1 ELSE 0 END) as attended
        FROM attendance_records WHERE student_id=%s
    """, (uid,))
    att_row = cur.fetchone()
    total_sess = int(att_row["total"] or 0) if att_row else 0
    attended_sess = int(att_row["attended"] or 0) if att_row else 0
    overall_att = round(attended_sess / total_sess * 100, 1) if total_sess > 0 else float(values["attendance"])

    # Subject-wise marks & attendance for charts
    cur.execute("""
        SELECT s.code, s.name,
               AVG(ar.marks_obtained / a.max_marks * 100) as avg_score
        FROM assessments a
        JOIN assessment_results ar ON ar.assessment_id = a.id
        JOIN subjects s ON s.id = a.subject_id
        WHERE ar.student_id = %s AND a.is_published = 1
        GROUP BY s.id, s.code, s.name
    """, (uid,))
    sub_scores = cur.fetchall()
    subject_names = [s["code"] for s in sub_scores] or ["Math", "Science", "English"]
    subject_marks = [round(float(s["avg_score"]), 1) for s in sub_scores] or [values["math_marks"], values["science_marks"], values["english_marks"]]
    avg_marks = round(sum(subject_marks) / len(subject_marks), 1) if subject_marks else 0

    cur.execute("""
        SELECT s.code,
               COUNT(ar.id) as total,
               SUM(CASE WHEN ar.status IN ('Present','Late') THEN 1 ELSE 0 END) as attended
        FROM attendance_sessions sess
        JOIN attendance_records ar ON ar.session_id = sess.id
        JOIN subjects s ON s.id = sess.subject_id
        WHERE ar.student_id = %s
        GROUP BY s.id, s.code
    """, (uid,))
    att_subs = cur.fetchall()
    att_subject_names = [s["code"] for s in att_subs] or ["CS501", "CS502", "CS504"]
    att_subject_values = [round(float(s["attended"] or 0) / float(s["total"] or 1) * 100, 1) if s["total"] else 100.0 for s in att_subs] or [values["attendance"], values["attendance"], values["attendance"]]

    # Practicals stats
    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status='Evaluated' THEN 1 ELSE 0 END) as evaluated
        FROM practical_submissions WHERE student_id=%s
    """, (uid,))
    prac_row = cur.fetchone()
    total_prac = int(prac_row["total"] or 0) if prac_row else 0
    eval_prac = int(prac_row["evaluated"] or 0) if prac_row else 0
    prac_pct = round(eval_prac / total_prac * 100, 1) if total_prac > 0 else 0

    # Pending assignments
    cur.execute("""
        SELECT COUNT(*) as pending
        FROM assignments a
        JOIN student_profiles sp ON sp.student_id = %s
        JOIN subjects s ON s.id = a.subject_id AND s.semester = sp.semester
        LEFT JOIN assignment_submissions sub ON sub.assignment_id = a.id AND sub.student_id = %s
        WHERE sub.id IS NULL
    """, (uid, uid))
    pending_assg_row = cur.fetchone()
    pending_assg_count = pending_assg_row["pending"] if pending_assg_row else 0

    # Upcoming examinations
    cur.execute("""
        SELECT a.title, s.code as subject, a.assessment_type as event_type, a.exam_date as date
        FROM assessments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.exam_date >= CURDATE()
        ORDER BY a.exam_date ASC LIMIT 3
    """)
    upcoming_events = cur.fetchall()

    insights = get_student_ai_insights(cur, uid)
    cur.close()
    conn.close()

    return render_template("dashboard.html",
                           role="student",
                           overall_attendance=overall_att,
                           average_marks=avg_marks,
                           prediction=estimate,
                           practical_completion_pct=prac_pct,
                           evaluated_practicals_count=eval_prac,
                           total_practicals_count=total_prac,
                           pending_assignments_count=pending_assg_count,
                           upcoming_events=upcoming_events,
                           risk=insights["risk"],
                           ai_recommendations=insights["recommendations"],
                           subject_names=subject_names,
                           subject_marks=subject_marks,
                           att_subject_names=att_subject_names,
                           att_subject_values=att_subject_values)

# -------------------------------------------------------------
# Student Portal Routes
# -------------------------------------------------------------

@app.route("/attendance")
@required("student")
def student_attendance():
    uid = session["user_id"]
    conn = connect()
    cur = conn.cursor(dictionary=True)

    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(CASE WHEN status IN ('Present','Late') THEN 1 ELSE 0 END) as attended
        FROM attendance_records WHERE student_id=%s
    """, (uid,))
    att_row = cur.fetchone()
    total_sess = int(att_row["total"] or 0) if att_row else 0
    attended_sess = int(att_row["attended"] or 0) if att_row else 0
    missed_sess = total_sess - attended_sess
    overall_pct = round(attended_sess / total_sess * 100, 1) if total_sess > 0 else 100.0

    # Consecutive classes needed for 75%
    classes_needed = 0
    if overall_pct < 75.0 and total_sess > 0:
        classes_needed = max(0, int((0.75 * total_sess - attended_sess) / 0.25) + 1)

    # Subject-wise
    cur.execute("""
        SELECT s.code, s.name,
               COUNT(ar.id) as total,
               SUM(CASE WHEN ar.status IN ('Present','Late') THEN 1 ELSE 0 END) as attended
        FROM attendance_sessions sess
        JOIN attendance_records ar ON ar.session_id = sess.id
        JOIN subjects s ON s.id = sess.subject_id
        WHERE ar.student_id = %s
        GROUP BY s.id, s.code, s.name
        ORDER BY s.code
    """, (uid,))
    sub_att_rows = cur.fetchall()
    subject_attendance = []
    for s in sub_att_rows:
        tot = int(s["total"] or 0)
        att = int(s["attended"] or 0)
        pct = round(att / tot * 100, 1) if tot > 0 else 100.0
        needed = max(0, int((0.75 * tot - att) / 0.25) + 1) if pct < 75.0 and tot > 0 else 0
        subject_attendance.append({
            "code": s["code"],
            "name": s["name"],
            "total": tot,
            "attended": att,
            "missed": tot - att,
            "pct": pct,
            "needed": needed
        })

    # Recent session logs
    cur.execute("""
        SELECT sess.id as session_id, sess.session_date, sess.session_type, sess.topic_covered,
               s.code as subject_code, s.name as subject_name, u.full_name as teacher_name,
               ar.status, ar.remarks
        FROM attendance_records ar
        JOIN attendance_sessions sess ON sess.id = ar.session_id
        JOIN subjects s ON s.id = sess.subject_id
        JOIN users u ON u.id = sess.teacher_id
        WHERE ar.student_id = %s
        ORDER BY sess.session_date DESC, sess.id DESC
        LIMIT 25
    """, (uid,))
    session_records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template("attendance.html",
                           overall_att_pct=overall_pct,
                           total_attended=attended_sess,
                           total_sessions=total_sess,
                           total_missed=missed_sess,
                           classes_needed=classes_needed,
                           subject_attendance=subject_attendance,
                           session_records=session_records)

@app.route("/attendance/request-correction", methods=["POST"])
@required("student")
def request_attendance_correction():
    uid = session["user_id"]
    session_id = request.form.get("session_id")
    reason = request.form.get("reason", "").strip()

    if not session_id or not reason:
        flash("Please provide the session reference and justification.", "error")
        return redirect(url_for("student_attendance"))

    try:
        # Check if already requested
        existing = one("SELECT id FROM attendance_correction_requests WHERE student_id=%s AND session_id=%s AND status='Pending'",
                       (uid, session_id))
        if existing:
            flash("A correction request for this session is already under faculty review.", "error")
        else:
            run("""INSERT INTO attendance_correction_requests (student_id, session_id, reason, status)
                   VALUES (%s, %s, %s, 'Pending')""", (uid, session_id, reason))
            log_audit("ATTENDANCE_CORRECTION_REQUESTED", "attendance_records", session_id, f"Reason: {reason}")
            flash("Attendance correction request submitted to your faculty mentor.", "success")
    except Exception:
        app.logger.exception("Attendance correction request failed")
        flash("Could not submit correction request.", "error")

    return redirect(url_for("student_attendance"))

@app.route("/attendance/export-csv")
@required("student")
def export_student_attendance_csv():
    uid = session["user_id"]
    records = all_rows("""
        SELECT sess.session_date, s.code, s.name as subject, sess.session_type, ar.status, sess.topic_covered
        FROM attendance_records ar
        JOIN attendance_sessions sess ON sess.id = ar.session_id
        JOIN subjects s ON s.id = sess.subject_id
        WHERE ar.student_id = %s
        ORDER BY sess.session_date DESC
    """, (uid,))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Apex Institute of Technology & Research - Student Attendance Log"])
    writer.writerow([f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow([f"Student Name: {session.get('name')}", f"User ID: {uid}"])
    writer.writerow([])
    writer.writerow(["Date", "Subject Code", "Subject Name", "Session Type", "Status", "Topic Covered"])
    for r in records:
        writer.writerow([r["session_date"], r["code"], r["subject"], r["session_type"], r["status"], r["topic_covered"]])

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=attendance_{uid}.csv"})

@app.route("/marks")
@required("student")
def student_marks():
    uid = session["user_id"]
    # Only PUBLISHED assessments visible to students
    results = all_rows("""
        SELECT a.title, a.assessment_type, a.max_marks, a.weightage, a.exam_date,
               a.published_at, ar.marks_obtained, ar.remarks,
               s.code as subject_code, s.name as subject_name
        FROM assessment_results ar
        JOIN assessments a ON a.id = ar.assessment_id
        JOIN subjects s ON s.id = a.subject_id
        WHERE ar.student_id = %s AND a.is_published = 1
        ORDER BY a.exam_date DESC
    """, (uid,))

    for r in results:
        r["pct"] = round(float(r["marks_obtained"]) / float(r["max_marks"]) * 100, 1)

    overall_avg = round(sum(r["pct"] for r in results) / len(results), 1) if results else 0
    highest = max([r["pct"] for r in results]) if results else 0
    lowest = min([r["pct"] for r in results]) if results else 0
    highest_sub = next((r["subject_name"] for r in results if r["pct"] == highest), None)
    lowest_sub = next((r["subject_name"] for r in results if r["pct"] == lowest), None)

    # Subject averages for chart
    sub_map = {}
    for r in results:
        sub_map.setdefault(r["subject_code"], []).append(r["pct"])
    chart_subjects = list(sub_map.keys())
    chart_scores = [round(sum(vals)/len(vals), 1) for vals in sub_map.values()]

    return render_template("marks.html",
                           published_results=results,
                           overall_avg_pct=overall_avg,
                           highest_score=highest,
                           lowest_score=lowest,
                           highest_subject=highest_sub,
                           lowest_subject=lowest_sub,
                           chart_subjects=chart_subjects,
                           chart_scores=chart_scores)

@app.route("/practicals")
@required("student")
def student_practicals():
    uid = session["user_id"]
    practicals = all_rows("""
        SELECT p.id, p.experiment_no, p.title, p.description, p.scheduled_date, p.max_marks,
               s.code as subject_code, s.name as subject_name,
               ps.status, ps.lab_attendance, ps.journal_submitted, ps.viva_marks,
               ps.execution_marks, ps.total_marks, ps.feedback
        FROM practicals p
        JOIN subjects s ON s.id = p.subject_id
        JOIN student_profiles sp ON sp.student_id = %s AND sp.semester = s.semester
        LEFT JOIN practical_submissions ps ON ps.practical_id = p.id AND ps.student_id = %s
        ORDER BY s.code, p.experiment_no ASC
    """, (uid, uid))

    total = len(practicals)
    eval_count = sum(1 for p in practicals if p["status"] == "Evaluated")
    resub_count = sum(1 for p in practicals if p["status"] == "Needs Resubmission")
    pct = round(eval_count / total * 100, 1) if total > 0 else 0

    evaluated = [p for p in practicals if p["status"] == "Evaluated"]
    avg_viva = round(sum(float(p["viva_marks"] or 0) for p in evaluated) / len(evaluated), 1) if evaluated else 0
    avg_exe = round(sum(float(p["execution_marks"] or 0) for p in evaluated) / len(evaluated), 1) if evaluated else 0

    return render_template("practicals.html",
                           practicals_list=practicals,
                           total_practicals=total,
                           evaluated_count=eval_count,
                           completion_pct=pct,
                           resubmission_count=resub_count,
                           avg_viva=avg_viva,
                           avg_execution=avg_exe)

@app.route("/assignments")
@required("student")
def student_assignments():
    uid = session["user_id"]
    # All assignments for student's semester
    all_assign = all_rows("""
        SELECT a.id, a.title, a.description, a.instructions, a.due_date, a.max_marks,
               s.code as subject_code, s.name as subject_name,
               sub.id as submission_id, sub.submitted_at, sub.is_late, sub.status,
               sub.marks_obtained, sub.feedback, sub.submission_text, sub.attachment_name
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        JOIN student_profiles sp ON sp.student_id = %s AND sp.semester = s.semester
        LEFT JOIN assignment_submissions sub ON sub.assignment_id = a.id AND sub.student_id = %s
        ORDER BY a.due_date ASC
    """, (uid, uid))

    pending = []
    evaluated = []
    now = datetime.now()
    for a in all_assign:
        if a["submission_id"]:
            evaluated.append(a)
        else:
            a["is_overdue"] = a["due_date"] < now if a["due_date"] else False
            pending.append(a)

    scores = [float(a["marks_obtained"]) / float(a["max_marks"]) * 100 for a in evaluated if a["marks_obtained"] is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    return render_template("assignments.html",
                           pending_assignments=pending,
                           evaluated_assignments=evaluated,
                           avg_assignment_score=avg_score)

@app.route("/assignments/submit", methods=["POST"])
@required("student")
def submit_assignment():
    uid = session["user_id"]
    assign_id = request.form.get("assignment_id")
    text = request.form.get("submission_text", "").strip()
    attach = request.form.get("attachment_name", "").strip()

    if not assign_id or not text:
        flash("Submission deliverable text or links are required.", "error")
        return redirect(url_for("student_assignments"))

    assign = one("SELECT * FROM assignments WHERE id=%s", (assign_id,))
    if not assign:
        flash("Assignment not found.", "error")
        return redirect(url_for("student_assignments"))

    is_late = datetime.now() > assign["due_date"] if assign["due_date"] else False

    try:
        existing = one("SELECT id FROM assignment_submissions WHERE assignment_id=%s AND student_id=%s", (assign_id, uid))
        if existing:
            run("""UPDATE assignment_submissions
                   SET submission_text=%s, attachment_name=%s, submitted_at=NOW(), is_late=%s, status='Submitted'
                   WHERE id=%s""", (text, attach, is_late, existing["id"]))
        else:
            run("""INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, attachment_name, is_late, status)
                   VALUES (%s, %s, %s, %s, %s, 'Submitted')""",
                (assign_id, uid, text, attach, is_late))
        log_audit("ASSIGNMENT_SUBMITTED", "assignments", assign_id, f"Late: {is_late}")
        flash("Coursework submitted successfully for faculty grading.", "success")
    except Exception:
        app.logger.exception("Failed submitting coursework")
        flash("Could not submit assignment.", "error")

    return redirect(url_for("student_assignments"))

@app.route("/projects")
@required("student")
def student_projects():
    uid = session["user_id"]
    # Student's project
    proj = one("""
        SELECT p.id, p.title, p.description, p.project_type, p.academic_year,
               u.full_name as guide_name
        FROM projects p
        JOIN project_members pm ON pm.project_id = p.id
        JOIN users u ON u.id = p.guide_id
        WHERE pm.student_id = %s
    """, (uid,))

    team_members = []
    milestones = []
    avg_progress = 0
    if proj:
        team_members = all_rows("""
            SELECT u.full_name, pm.role_in_team
            FROM project_members pm
            JOIN users u ON u.id = pm.student_id
            WHERE pm.project_id = %s
        """, (proj["id"],))

        milestones = all_rows("""
            SELECT id, milestone_name, target_date, completed_date, status, progress_pct, guide_remarks
            FROM project_milestones
            WHERE project_id = %s
            ORDER BY target_date ASC
        """, (proj["id"],))

        if milestones:
            avg_progress = int(sum(m["progress_pct"] for m in milestones) / len(milestones))

    # Portfolio activities
    activities = all_rows("""
        SELECT id, title, category, organizer, activity_date, certificate_ref, verified_status
        FROM activities
        WHERE student_id = %s
        ORDER BY activity_date DESC
    """, (uid,))

    return render_template("projects.html",
                           project=proj,
                           team_members=team_members,
                           milestones=milestones,
                           avg_progress=avg_progress,
                           activities=activities)

@app.route("/activities/add", methods=["POST"])
@required("student")
def add_activity():
    uid = session["user_id"]
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "Workshop")
    organizer = request.form.get("organizer", "").strip()
    act_date = request.form.get("activity_date")
    cert = request.form.get("certificate_ref", "").strip()

    if not title or not organizer or not act_date:
        flash("Please fill all required activity fields.", "error")
        return redirect(url_for("student_projects"))

    try:
        run("""INSERT INTO activities (student_id, title, category, organizer, activity_date, certificate_ref, verified_status)
               VALUES (%s, %s, %s, %s, %s, %s, 'Pending')""",
            (uid, title, category, organizer, act_date, cert))
        log_audit("ACTIVITY_RECORDED", "activities", None, f"{title} ({category})")
        flash("Activity added to your verified student portfolio for faculty review.", "success")
    except Exception:
        app.logger.exception("Failed adding activity")
        flash("Could not add activity.", "error")

    return redirect(url_for("student_projects"))

@app.route("/timetable")
@required()
def view_timetable():
    uid = session["user_id"]
    role = session["role"]

    timetable_rows = all_rows("""
        SELECT t.id, t.day_of_week, t.start_time, t.end_time, t.room_number, t.session_type,
               s.code as subject_code, s.name as subject_name, u.full_name as teacher_name
        FROM timetable t
        JOIN subjects s ON s.id = t.subject_id
        JOIN users u ON u.id = t.teacher_id
        WHERE t.semester = 5 AND t.division = 'A'
        ORDER BY t.start_time ASC
    """)

    timetable_by_day = {}
    def _to_12h(t_val):
        try:
            s = str(t_val)[:5]
            parts = s.split(":")
            h, m = int(parts[0]), int(parts[1])
            suffix = "AM" if h < 12 else "PM"
            h12 = h % 12
            if h12 == 0:
                h12 = 12
            return f"{h12:02d}:{m:02d} {suffix}"
        except Exception:
            return str(t_val)[:5]

    for r in timetable_rows:
        # format times
        st = str(r["start_time"])[:5]
        et = str(r["end_time"])[:5]
        r["start_time"] = st
        r["end_time"] = et
        r["start_time_fmt"] = _to_12h(st)
        r["end_time_fmt"] = _to_12h(et)
        timetable_by_day.setdefault(r["day_of_week"], []).append(r)

    return render_template("timetable.html", timetable_by_day=timetable_by_day)

@app.route("/calendar")
@required()
def view_calendar():
    exams = all_rows("""
        SELECT a.title, a.assessment_type, a.max_marks, a.exam_date,
               s.code as subject_code, s.name as subject_name
        FROM assessments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.exam_date >= CURDATE()
        ORDER BY a.exam_date ASC
    """)

    assignments = all_rows("""
        SELECT a.title, a.due_date, a.max_marks, s.code as subject_code, s.name as subject_name
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.due_date >= NOW()
        ORDER BY a.due_date ASC
    """)

    announcements = all_rows("""
        SELECT ann.title, ann.content, ann.category, ann.created_at, u.full_name as author_name
        FROM announcements ann
        LEFT JOIN users u ON u.id = ann.created_by
        ORDER BY ann.created_at DESC LIMIT 6
    """)

    return render_template("calendar.html", exams=exams, assignments=assignments, announcements=announcements)

@app.route("/ai-insights")
@required("student")
def student_ai_insights():
    uid = session["user_id"]
    conn = connect()
    cur = conn.cursor(dictionary=True)
    insights = get_student_ai_insights(cur, uid)
    cur.close()
    conn.close()
    return render_template("ai_insights.html", insights=insights)

@app.route("/api/ai/query", methods=["POST"])
@required()
def api_ai_query():
    data = request.get_json(silent=True) or {}
    query_text = data.get("query", "").strip()
    if not query_text:
        return jsonify({"error": "Empty query"}), 400

    uid = session["user_id"]
    role = session["role"]

    conn = connect()
    cur = conn.cursor(dictionary=True)
    try:
        reply = handle_natural_language_query(cur, uid, role, query_text)
    finally:
        cur.close()
        conn.close()

    return jsonify({"response": reply})

@app.route("/notifications")
@required()
def view_notifications():
    uid = session["user_id"]
    notifications = all_rows("""
        SELECT id, title, message, category, link, is_read, created_at
        FROM notifications
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (uid,))
    return render_template("notifications.html", notifications=notifications)

@app.route("/notifications/mark-all-read", methods=["POST"])
@required()
def mark_all_notifications_read():
    uid = session["user_id"]
    run("UPDATE notifications SET is_read=1 WHERE user_id=%s", (uid,))
    flash("All notifications marked as read.", "success")
    return redirect(url_for("view_notifications"))

@app.route("/profile")
@required()
def user_profile():
    uid = session["user_id"]
    user = one("SELECT * FROM users WHERE id=%s", (uid,))
    profile = {}
    if user["role"] == "student":
        profile = one("""
            SELECT sp.*, d.name as department_name, u.full_name as mentor_name
            FROM student_profiles sp
            JOIN departments d ON d.id = sp.department_id
            LEFT JOIN users u ON u.id = sp.mentor_id
            WHERE sp.student_id = %s
        """, (uid,)) or {}
    else:
        profile = one("""
            SELECT tp.*, d.name as department_name
            FROM teacher_profiles tp
            JOIN departments d ON d.id = tp.department_id
            WHERE tp.teacher_id = %s
        """, (uid,)) or {}

    return render_template("profile.html", user=user, profile=profile)

@app.route("/change-password", methods=["POST"])
@required()
def change_password():
    uid = session["user_id"]
    cur_pw = request.form.get("current_password", "")
    new_pw = request.form.get("new_password", "")
    conf_pw = request.form.get("confirm_password", "")

    if len(new_pw) < 8:
        flash("New password must be at least 8 characters long.", "error")
        return redirect(url_for("user_profile"))
    if new_pw != conf_pw:
        flash("New password and confirm password do not match.", "error")
        return redirect(url_for("user_profile"))

    user = one("SELECT password_hash FROM users WHERE id=%s", (uid,))
    if not check_password_hash(user["password_hash"], cur_pw):
        flash("Incorrect current password.", "error")
        return redirect(url_for("user_profile"))

    run("UPDATE users SET password_hash=%s WHERE id=%s", (generate_password_hash(new_pw), uid))
    log_audit("PASSWORD_CHANGED", "users", uid, "Password updated successfully")
    flash("Password updated successfully.", "success")
    return redirect(url_for("user_profile"))

# -------------------------------------------------------------
# Student-Faculty Query & Messaging System
# -------------------------------------------------------------

def generate_query_reference_code():
    max_row = one("SELECT MAX(id) as max_id FROM student_queries")
    next_id = (max_row["max_id"] or 0) + 1001
    code = f"SP-{next_id}"
    while one("SELECT id FROM student_queries WHERE reference_code=%s", (code,)):
        next_id += 1
        code = f"SP-{next_id}"
    return code

def find_assigned_faculty(student_id, subject_id):
    sp = one("SELECT * FROM student_profiles WHERE student_id=%s", (student_id,))
    div = sp["division"] if sp and sp.get("division") else "A"
    ay = sp["academic_year"] if sp and sp.get("academic_year") else "2026-2027"

    st = one("""
        SELECT teacher_id FROM subject_teachers
        WHERE subject_id = %s AND division = %s AND academic_year = %s
        LIMIT 1
    """, (subject_id, div, ay))

    if not st:
        st = one("SELECT teacher_id FROM subject_teachers WHERE subject_id = %s LIMIT 1", (subject_id,))

    return st["teacher_id"] if st else None

@app.route("/student/queries")
@required("student")
def student_queries():
    uid = session["user_id"]
    q = request.args.get("q", "").strip()
    sub_id = request.args.get("subject", "").strip()
    status = request.args.get("status", "").strip()

    sql = """
        SELECT sq.id, sq.reference_code, sq.category, sq.title, sq.description,
               sq.status, sq.created_at, sq.updated_at,
               s.code as subject_code, s.name as subject_name,
               u.full_name as assigned_faculty_name,
               (SELECT COUNT(*) FROM query_messages qm WHERE qm.query_id = sq.id AND qm.sender_id != %s AND qm.read_at IS NULL) as unread_count
        FROM student_queries sq
        JOIN subjects s ON s.id = sq.subject_id
        LEFT JOIN users u ON u.id = sq.assigned_faculty_id
        WHERE sq.student_id = %s
    """
    params = [uid, uid]

    if q:
        sql += " AND (sq.title LIKE %s OR sq.description LIKE %s OR sq.reference_code LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if sub_id:
        sql += " AND sq.subject_id = %s"
        params.append(sub_id)
    if status:
        sql += " AND sq.status = %s"
        params.append(status)

    sql += " ORDER BY sq.updated_at DESC, sq.id DESC"
    queries = all_rows(sql, tuple(params))

    # Calculate stats
    all_q = all_rows("SELECT status FROM student_queries WHERE student_id = %s", (uid,))
    total = len(all_q)
    active = sum(1 for item in all_q if item["status"] in ("Open", "In Progress"))
    waiting = sum(1 for item in all_q if item["status"] == "Waiting for Student")
    resolved = sum(1 for item in all_q if item["status"] == "Resolved")

    subjects = all_rows("""
        SELECT s.id, s.code, s.name
        FROM subjects s
        JOIN student_profiles sp ON sp.student_id = %s AND sp.semester = s.semester
        ORDER BY s.code
    """, (uid,))

    return render_template("student/queries.html",
                           queries=queries,
                           subjects=subjects,
                           total_queries=total,
                           active_count=active,
                           waiting_count=waiting,
                           resolved_count=resolved,
                           search_query=q,
                           subject_filter=sub_id,
                           status_filter=status)

@app.route("/student/queries/new")
@required("student")
def student_new_query():
    uid = session["user_id"]
    sp = one("SELECT * FROM student_profiles WHERE student_id=%s", (uid,)) or {}
    div = sp.get("division", "A")
    ay = sp.get("academic_year", "2026-2027")

    subjects = all_rows("""
        SELECT s.id, s.code, s.name, u.full_name as teacher_name
        FROM subjects s
        JOIN student_profiles sp ON sp.student_id = %s AND sp.semester = s.semester
        LEFT JOIN subject_teachers st ON st.subject_id = s.id AND st.division = %s AND st.academic_year = %s
        LEFT JOIN users u ON u.id = st.teacher_id
        ORDER BY s.code
    """, (uid, div, ay))

    return render_template("student/new_query.html",
                           subjects=subjects,
                           student_profile=sp)

@app.route("/student/queries/create", methods=["POST"])
@required("student")
def student_create_query():
    uid = session["user_id"]
    subject_id = request.form.get("subject_id")
    category = request.form.get("category", "Academic")
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    attachment = request.form.get("attachment_name", "").strip()

    if not subject_id or len(title) < 5 or len(description) < 10:
        flash("Please provide all required fields (title at least 5 chars, description at least 10 chars).", "error")
        return redirect(url_for("student_new_query"))

    sub = one("SELECT * FROM subjects WHERE id=%s", (subject_id,))
    if not sub:
        flash("Invalid subject selected.", "error")
        return redirect(url_for("student_new_query"))

    ref_code = generate_query_reference_code()
    faculty_id = find_assigned_faculty(uid, subject_id)
    status = "Open" if faculty_id else "Unassigned"

    conn = connect()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            INSERT INTO student_queries (reference_code, student_id, subject_id, assigned_faculty_id, category, title, description, attachment_name, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (ref_code, uid, subject_id, faculty_id, category, title, description, attachment or None, status))
        query_id = cur.lastrowid

        # Insert initial description as message #1
        cur.execute("""
            INSERT INTO query_messages (query_id, sender_id, message_text, attachment_name, read_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (query_id, uid, description, attachment or None))

        student_name = session.get("name", "Student")

        # Create notification
        if faculty_id:
            cur.execute("""
                INSERT INTO notifications (user_id, title, message, category, link)
                VALUES (%s, %s, %s, 'query', %s)
            """, (faculty_id, f"New Student Query: {ref_code}",
                  f"{student_name} submitted a query on {sub['code']}: '{title}'",
                  f"/queries/{ref_code}"))
        else:
            cur.execute("SELECT id FROM users WHERE role='teacher' LIMIT 2")
            admins = cur.fetchall()
            for a in admins:
                cur.execute("""
                    INSERT INTO notifications (user_id, title, message, category, link)
                    VALUES (%s, %s, %s, 'query', %s)
                """, (a["id"], f"Unassigned Query: {ref_code}",
                      f"{student_name} submitted a query on {sub['code']} requiring faculty assignment.",
                      f"/queries/{ref_code}"))

        conn.commit()
        log_audit("QUERY_CREATED", "student_queries", query_id, f"Ref: {ref_code}, Assigned: {faculty_id}")

        faculty_row = one("SELECT full_name FROM users WHERE id=%s", (faculty_id,)) if faculty_id else None
        assigned_name = faculty_row["full_name"] if faculty_row else "College Faculty Board (Unassigned)"

        flash(f"Query {ref_code} submitted successfully and assigned to {assigned_name}.", "success")
        return redirect(url_for("view_query_conversation", reference_code=ref_code))
    except Exception:
        conn.rollback()
        app.logger.exception("Failed to create query")
        flash("Could not submit query due to database error.", "error")
        return redirect(url_for("student_new_query"))
    finally:
        cur.close()
        conn.close()

@app.route("/teacher/queries")
@required("teacher")
def teacher_queries():
    tid = session["user_id"]
    q = request.args.get("q", "").strip()
    sub_id = request.args.get("subject", "").strip()
    status = request.args.get("status", "").strip()

    sql = """
        SELECT sq.id, sq.reference_code, sq.category, sq.title, sq.description,
               sq.status, sq.created_at, sq.updated_at,
               s.code as subject_code, s.name as subject_name,
               stu.full_name as student_name, stu.username as student_username,
               sp.enrollment_no,
               fac.full_name as assigned_faculty_name,
               (SELECT COUNT(*) FROM query_messages qm WHERE qm.query_id = sq.id AND qm.sender_id != %s AND qm.read_at IS NULL) as unread_count
        FROM student_queries sq
        JOIN subjects s ON s.id = sq.subject_id
        JOIN users stu ON stu.id = sq.student_id
        LEFT JOIN student_profiles sp ON sp.student_id = stu.id
        LEFT JOIN users fac ON fac.id = sq.assigned_faculty_id
        WHERE (sq.assigned_faculty_id = %s OR sq.assigned_faculty_id IS NULL)
    """
    params = [tid, tid]

    if q:
        sql += " AND (sq.title LIKE %s OR sq.description LIKE %s OR sq.reference_code LIKE %s OR stu.full_name LIKE %s OR sp.enrollment_no LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    if sub_id:
        sql += " AND sq.subject_id = %s"
        params.append(sub_id)
    if status:
        sql += " AND sq.status = %s"
        params.append(status)

    sql += " ORDER BY sq.updated_at DESC, sq.id DESC"
    queries = all_rows(sql, tuple(params))

    # Stats
    all_assigned = all_rows("SELECT status FROM student_queries WHERE assigned_faculty_id = %s", (tid,))
    assigned_count = len(all_assigned)
    open_count = sum(1 for item in all_assigned if item["status"] in ("Open", "In Progress"))
    waiting_count = sum(1 for item in all_assigned if item["status"] == "Waiting for Student")
    resolved_count = sum(1 for item in all_assigned if item["status"] == "Resolved")
    unassigned_count = one("SELECT COUNT(*) as cnt FROM student_queries WHERE assigned_faculty_id IS NULL")["cnt"]

    subjects = all_rows("SELECT id, code, name FROM subjects ORDER BY code")

    return render_template("teacher/queries.html",
                           queries=queries,
                           subjects=subjects,
                           assigned_count=assigned_count,
                           open_count=open_count,
                           waiting_count=waiting_count,
                           resolved_count=resolved_count,
                           unassigned_count=unassigned_count,
                           search_query=q,
                           subject_filter=sub_id,
                           status_filter=status)

@app.route("/queries/<reference_code>")
@required()
def view_query_conversation(reference_code):
    uid = session["user_id"]
    role = session["role"]

    query = one("""
        SELECT sq.*, s.code as subject_code, s.name as subject_name,
               stu.full_name as student_name, stu.username as student_username,
               sp.enrollment_no,
               fac.full_name as assigned_faculty_name
        FROM student_queries sq
        JOIN subjects s ON s.id = sq.subject_id
        JOIN users stu ON stu.id = sq.student_id
        LEFT JOIN student_profiles sp ON sp.student_id = stu.id
        LEFT JOIN users fac ON fac.id = sq.assigned_faculty_id
        WHERE sq.reference_code = %s
    """, (reference_code,))

    if not query:
        flash("Query not found.", "error")
        return redirect(url_for("teacher_queries" if role == "teacher" else "student_queries"))

    # Permission check: student must be the creator, teacher must be assigned or query is unassigned
    if role == "student" and query["student_id"] != uid:
        flash("You are not authorized to view this query conversation.", "error")
        return redirect(url_for("student_queries"))
    if role == "teacher" and query["assigned_faculty_id"] and query["assigned_faculty_id"] != uid:
        flash("You are not authorized to access this query.", "error")
        return redirect(url_for("teacher_queries"))

    # Mark unread messages sent by others as read
    run("""
        UPDATE query_messages
        SET read_at = NOW()
        WHERE query_id = %s AND sender_id != %s AND read_at IS NULL
    """, (query["id"], uid))

    # Retrieve all messages in chronological order
    messages = all_rows("""
        SELECT qm.*, u.full_name as sender_name, u.role as sender_role
        FROM query_messages qm
        JOIN users u ON u.id = qm.sender_id
        WHERE qm.query_id = %s
        ORDER BY qm.id ASC
    """, (query["id"],))

    faculty_list = all_rows("""
        SELECT u.id, u.full_name, d.code as department_code
        FROM users u
        LEFT JOIN teacher_profiles tp ON tp.teacher_id = u.id
        LEFT JOIN departments d ON d.id = tp.department_id
        WHERE u.role = 'teacher'
        ORDER BY u.full_name ASC
    """)

    return render_template("queries/conversation.html",
                           query=query,
                           messages=messages,
                           faculty_list=faculty_list)

@app.route("/queries/<reference_code>/messages", methods=["POST"])
@required()
def post_query_message(reference_code):
    uid = session["user_id"]
    role = session["role"]
    message_text = request.form.get("message_text", "").strip()
    attachment = request.form.get("attachment_name", "").strip()
    status_update = request.form.get("status_update")

    if len(message_text) < 2:
        flash("Please enter a valid message.", "error")
        return redirect(url_for("view_query_conversation", reference_code=reference_code))

    query = one("SELECT * FROM student_queries WHERE reference_code=%s", (reference_code,))
    if not query:
        flash("Query not found.", "error")
        return redirect(url_for("dashboard"))

    # Security check
    if role == "student" and query["student_id"] != uid:
        flash("Unauthorized action.", "error")
        return redirect(url_for("student_queries"))
    if role == "teacher" and query["assigned_faculty_id"] and query["assigned_faculty_id"] != uid:
        flash("Unauthorized action.", "error")
        return redirect(url_for("teacher_queries"))

    conn = connect()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("""
            INSERT INTO query_messages (query_id, sender_id, message_text, attachment_name, read_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (query["id"], uid, message_text, attachment or None))

        cur.execute("UPDATE student_queries SET updated_at = NOW() WHERE id = %s", (query["id"],))

        user_name = session.get("name", "User")

        if role == "teacher":
            new_status = query["status"]
            if status_update in ("In Progress", "Waiting for Student", "Resolved"):
                new_status = status_update
            elif query["status"] == "Open":
                new_status = "In Progress"

            if new_status == "Resolved":
                cur.execute("UPDATE student_queries SET status = 'Resolved', resolved_at = NOW() WHERE id = %s", (query["id"],))
            else:
                cur.execute("UPDATE student_queries SET status = %s WHERE id = %s", (new_status, query["id"],))

            cur.execute("""
                INSERT INTO notifications (user_id, title, message, category, link)
                VALUES (%s, %s, %s, 'query', %s)
            """, (query["student_id"], f"Faculty Response on {reference_code}",
                  f"{user_name} sent a reply on your query '{query['title']}'.",
                  f"/queries/{reference_code}"))

        elif role == "student":
            if query["status"] in ("Waiting for Student", "Resolved"):
                cur.execute("UPDATE student_queries SET status = 'In Progress' WHERE id = %s", (query["id"],))

            if query["assigned_faculty_id"]:
                cur.execute("""
                    INSERT INTO notifications (user_id, title, message, category, link)
                    VALUES (%s, %s, %s, 'query', %s)
                """, (query["assigned_faculty_id"], f"Student Follow-up on {reference_code}",
                      f"{user_name} replied to query '{query['title']}'.",
                      f"/queries/{reference_code}"))

        conn.commit()
        log_audit("QUERY_MESSAGE_POSTED", "query_messages", query["id"], f"Sender: {uid} ({role})")
        flash("Message sent successfully.", "success")
    except Exception:
        conn.rollback()
        app.logger.exception("Error posting message")
        flash("Failed to post message.", "error")
    finally:
        cur.close()
        conn.close()

    return redirect(url_for("view_query_conversation", reference_code=reference_code))

@app.route("/queries/<reference_code>/status", methods=["POST"])
@required("teacher")
def update_query_status(reference_code):
    uid = session["user_id"]
    new_status = request.form.get("status")

    if new_status not in ("In Progress", "Waiting for Student"):
        flash("Invalid status transition.", "error")
        return redirect(url_for("view_query_conversation", reference_code=reference_code))

    query = one("SELECT * FROM student_queries WHERE reference_code=%s", (reference_code,))
    if not query:
        flash("Query not found.", "error")
        return redirect(url_for("teacher_queries"))

    if query["assigned_faculty_id"] and query["assigned_faculty_id"] != uid:
        flash("Unauthorized.", "error")
        return redirect(url_for("teacher_queries"))

    run("UPDATE student_queries SET status=%s, updated_at=NOW() WHERE id=%s", (new_status, query["id"]))
    run("""INSERT INTO notifications (user_id, title, message, category, link)
           VALUES (%s, %s, %s, 'query', %s)""",
        (query["student_id"], f"Query Status Updated: {reference_code}",
         f"Your query '{query['title']}' is now marked as {new_status}.",
         f"/queries/{reference_code}"))

    log_audit("QUERY_STATUS_CHANGED", "student_queries", query["id"], f"New status: {new_status}")
    flash(f"Query status updated to {new_status}.", "success")
    return redirect(url_for("view_query_conversation", reference_code=reference_code))

@app.route("/queries/<reference_code>/resolve", methods=["POST"])
@required("teacher")
def resolve_query(reference_code):
    uid = session["user_id"]
    note = request.form.get("resolution_note", "").strip()

    if not note:
        flash("Please provide a resolution summary note for the student.", "error")
        return redirect(url_for("view_query_conversation", reference_code=reference_code))

    query = one("SELECT * FROM student_queries WHERE reference_code=%s", (reference_code,))
    if not query:
        flash("Query not found.", "error")
        return redirect(url_for("teacher_queries"))

    if query["assigned_faculty_id"] and query["assigned_faculty_id"] != uid:
        flash("Unauthorized.", "error")
        return redirect(url_for("teacher_queries"))

    run("""
        UPDATE student_queries
        SET status = 'Resolved', resolution_note = %s, resolved_at = NOW(), updated_at = NOW()
        WHERE id = %s
    """, (note, query["id"]))

    run("""INSERT INTO notifications (user_id, title, message, category, link)
           VALUES (%s, %s, %s, 'query', %s)""",
        (query["student_id"], f"Query Resolved: {reference_code}",
         f"Your query '{query['title']}' has been resolved by faculty: {note[:100]}...",
         f"/queries/{reference_code}"))

    log_audit("QUERY_RESOLVED", "student_queries", query["id"], f"Resolution note: {note}")
    flash(f"Query {reference_code} successfully marked as Resolved.", "success")
    return redirect(url_for("view_query_conversation", reference_code=reference_code))

@app.route("/queries/<reference_code>/reopen", methods=["POST"])
@required()
def reopen_query(reference_code):
    uid = session["user_id"]
    role = session["role"]

    query = one("SELECT * FROM student_queries WHERE reference_code=%s", (reference_code,))
    if not query:
        flash("Query not found.", "error")
        return redirect(url_for("dashboard"))

    if role == "student" and query["student_id"] != uid:
        flash("Unauthorized.", "error")
        return redirect(url_for("student_queries"))
    if role == "teacher" and query["assigned_faculty_id"] and query["assigned_faculty_id"] != uid:
        flash("Unauthorized.", "error")
        return redirect(url_for("teacher_queries"))

    run("""
        UPDATE student_queries
        SET status = 'In Progress', resolved_at = NULL, updated_at = NOW()
        WHERE id = %s
    """, (query["id"],))

    reopener = session.get("name", "User")
    run("""
        INSERT INTO query_messages (query_id, sender_id, message_text, read_at)
        VALUES (%s, %s, %s, NOW())
    """, (query["id"], uid, f"🔔 [System Note] Query reopened by {reopener} for further clarification."))

    if role == "student" and query["assigned_faculty_id"]:
        run("""INSERT INTO notifications (user_id, title, message, category, link)
               VALUES (%s, %s, %s, 'query', %s)""",
            (query["assigned_faculty_id"], f"Query Reopened: {reference_code}",
             f"{reopener} reopened query '{query['title']}' for further help.",
             f"/queries/{reference_code}"))
    elif role == "teacher":
        run("""INSERT INTO notifications (user_id, title, message, category, link)
               VALUES (%s, %s, %s, 'query', %s)""",
            (query["student_id"], f"Query Reopened: {reference_code}",
             f"Faculty {reopener} reopened your query for continued review.",
             f"/queries/{reference_code}"))

    log_audit("QUERY_REOPENED", "student_queries", query["id"], f"Reopened by {uid}")
    flash(f"Query {reference_code} has been reopened.", "success")
    return redirect(url_for("view_query_conversation", reference_code=reference_code))

@app.route("/queries/<reference_code>/reassign", methods=["POST"])
@required("teacher")
def reassign_query(reference_code):
    faculty_id = int(request.form.get("faculty_id"))
    query = one("SELECT * FROM student_queries WHERE reference_code=%s", (reference_code,))
    if not query:
        flash("Query not found.", "error")
        return redirect(url_for("teacher_queries"))

    fac = one("SELECT full_name FROM users WHERE id=%s AND role='teacher'", (faculty_id,))
    if not fac:
        flash("Invalid faculty selected.", "error")
        return redirect(url_for("view_query_conversation", reference_code=reference_code))

    run("""
        UPDATE student_queries
        SET assigned_faculty_id = %s, status = 'Open', updated_at = NOW()
        WHERE id = %s
    """, (faculty_id, query["id"]))

    run("""INSERT INTO notifications (user_id, title, message, category, link)
           VALUES (%s, %s, %s, 'query', %s)""",
        (faculty_id, f"Query Reassigned: {reference_code}",
         f"Query '{query['title']}' has been reassigned to you for resolution.",
         f"/queries/{reference_code}"))

    log_audit("QUERY_REASSIGNED", "student_queries", query["id"], f"Reassigned to {faculty_id}")
    flash(f"Query {reference_code} reassigned to {fac['full_name']}.", "success")
    return redirect(url_for("view_query_conversation", reference_code=reference_code))

# -------------------------------------------------------------
# Admin / Teacher Portal Routes
# -------------------------------------------------------------

@app.route("/teacher/students")
@required("teacher")
def teacher_students():
    q = request.args.get("q", "").strip()
    dept = request.args.get("dept", "").strip()

    sql = """
        SELECT u.id, u.full_name, u.username, sp.enrollment_no, sp.semester, sp.division,
               d.code as dept_code,
               p.math_marks, p.science_marks, p.english_marks, p.attendance
        FROM users u
        JOIN performance p ON p.student_id=u.id
        LEFT JOIN student_profiles sp ON sp.student_id=u.id
        LEFT JOIN departments d ON d.id=sp.department_id
        WHERE u.role='student'
    """
    params = []
    if q:
        sql += " AND (u.full_name LIKE %s OR u.username LIKE %s OR sp.enrollment_no LIKE %s)"
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    if dept:
        sql += " AND d.code = %s"
        params.append(dept)

    sql += " ORDER BY u.full_name ASC"
    students = all_rows(sql, tuple(params))
    return render_template("teacher/students.html", students=students, search_query=q, dept_filter=dept)

@app.route("/teacher/student/<int:student_id>")
@required("teacher")
def teacher_student_profile(student_id):
    student = one("SELECT id, full_name, username FROM users WHERE id=%s AND role='student'", (student_id,))
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("teacher_students"))

    profile = one("""
        SELECT sp.*, d.name as dept_name
        FROM student_profiles sp
        LEFT JOIN departments d ON d.id = sp.department_id
        WHERE sp.student_id=%s
    """, (student_id,)) or {}

    perf = get_perf(student_id)
    pred = predict(perf) if perf else None

    conn = connect()
    cur = conn.cursor(dictionary=True)
    risk = get_student_risk_assessment(cur, student_id)
    cur.close()
    conn.close()

    assessments = all_rows("""
        SELECT a.title, a.assessment_type, a.max_marks, ar.marks_obtained
        FROM assessment_results ar
        JOIN assessments a ON a.id = ar.assessment_id
        WHERE ar.student_id=%s AND a.is_published=1
        ORDER BY a.exam_date DESC
    """, (student_id,))

    practicals = all_rows("""
        SELECT p.experiment_no, p.title, ps.status, ps.total_marks
        FROM practical_submissions ps
        JOIN practicals p ON p.id = ps.practical_id
        WHERE ps.student_id=%s
        ORDER BY p.experiment_no ASC
    """, (student_id,))

    return render_template("teacher/student_profile.html",
                           student=student, profile=profile, perf=perf, prediction=pred,
                           risk=risk, assessments=assessments, practicals=practicals)

@app.route("/teacher/students/add", methods=["POST"])
@required("teacher")
def teacher_add_student():
    name = request.form.get("full_name", "").strip()
    uname = request.form.get("username", "").strip().lower()
    pw = request.form.get("password", "Student@123")
    eno = request.form.get("enrollment_no", "").strip()
    dcode = request.form.get("department_code", "CE")
    sem = int(request.form.get("semester", 5))

    if not name or not uname or not eno:
        flash("Please enter all required student details.", "error")
        return redirect(url_for("teacher_students"))

    try:
        uid = run("INSERT INTO users (full_name, username, password_hash, role) VALUES (%s, %s, %s, 'student')",
                  (name, uname, generate_password_hash(pw)))
        ensure_perf(uid)
        dept = one("SELECT id FROM departments WHERE code=%s", (dcode,))
        dept_id = dept["id"] if dept else 1
        run("""INSERT INTO student_profiles (student_id, enrollment_no, department_id, semester, division, academic_year, mentor_id)
               VALUES (%s, %s, %s, %s, 'A', '2026-2027', %s)""",
            (uid, eno, dept_id, sem, session["user_id"]))
        log_audit("STUDENT_CREATED", "users", uid, f"Created student {uname} ({eno})")
        flash(f"Student account for {name} registered successfully.", "success")
    except Error as e:
        if getattr(e, "errno", None) == 1062:
            flash("Username or Enrollment number already exists.", "error")
        else:
            app.logger.exception("Failed adding student")
            flash("Failed to add student record.", "error")

    return redirect(url_for("teacher_students"))

@app.route("/teacher/students/import-csv", methods=["POST"])
@required("teacher")
def teacher_import_students_csv():
    file = request.files.get("csv_file")
    if not file or not file.filename.endswith(".csv"):
        flash("Please upload a valid CSV file.", "error")
        return redirect(url_for("teacher_students"))

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
        reader = csv.DictReader(stream)
        imported_count = 0
        pw_hash = generate_password_hash("Student@123")

        dept_cache = {d["code"]: d["id"] for d in all_rows("SELECT id, code FROM departments")}

        for row in reader:
            name = row.get("full_name", "").strip()
            uname = row.get("username", "").strip().lower()
            eno = row.get("enrollment_no", "").strip()
            dcode = row.get("department_code", "CE").strip()
            sem = int(row.get("semester", 5))
            div = row.get("division", "A").strip()

            if name and uname and eno:
                existing = one("SELECT id FROM users WHERE username=%s", (uname,))
                if not existing:
                    uid = run("INSERT INTO users (full_name, username, password_hash, role) VALUES (%s, %s, %s, 'student')",
                              (name, uname, pw_hash))
                    ensure_perf(uid)
                    did = dept_cache.get(dcode, 1)
                    run("""INSERT INTO student_profiles (student_id, enrollment_no, department_id, semester, division, academic_year, mentor_id)
                           VALUES (%s, %s, %s, %s, %s, '2026-2027', %s)""",
                        (uid, eno, did, sem, div, session["user_id"]))
                    imported_count += 1

        log_audit("CSV_STUDENT_IMPORT", "users", None, f"Imported {imported_count} student records")
        flash(f"Successfully imported {imported_count} student accounts from CSV.", "success")
    except Exception:
        app.logger.exception("CSV import error")
        flash("Failed reading or importing CSV. Ensure valid headers and encoding.", "error")

    return redirect(url_for("teacher_students"))

@app.route("/teacher/faculty")
@required("teacher")
def teacher_faculty_list():
    teachers = all_rows("""
        SELECT u.id, u.full_name, u.username, tp.employee_code, tp.designation,
               tp.qualification, tp.cabin_office, d.name as department_name,
               GROUP_CONCAT(DISTINCT s.code SEPARATOR ', ') as assigned_subjects
        FROM users u
        LEFT JOIN teacher_profiles tp ON tp.teacher_id = u.id
        LEFT JOIN departments d ON d.id = tp.department_id
        LEFT JOIN subject_teachers st ON st.teacher_id = u.id
        LEFT JOIN subjects s ON s.id = st.subject_id
        WHERE u.role = 'teacher'
        GROUP BY u.id, u.full_name, u.username, tp.employee_code, tp.designation,
                 tp.qualification, tp.cabin_office, d.name
        ORDER BY u.full_name ASC
    """)
    return render_template("teacher/faculty_list.html", teachers=teachers)

@app.route("/teacher/academic-setup")
@required("teacher")
def teacher_academic_setup():
    depts = all_rows("SELECT * FROM departments ORDER BY code")
    subs = all_rows("""
        SELECT s.*, d.name as department_name
        FROM subjects s
        JOIN departments d ON d.id = s.department_id
        ORDER BY s.semester, s.code
    """)
    return render_template("teacher/academic_setup.html", departments=depts, subjects=subs)

@app.route("/teacher/academic-setup/add-subject", methods=["POST"])
@required("teacher")
def teacher_add_subject():
    code = request.form.get("code", "").strip().upper()
    name = request.form.get("name", "").strip()
    did = int(request.form.get("department_id", 1))
    sem = int(request.form.get("semester", 5))
    credits = int(request.form.get("credits", 4))
    has_prac = bool(request.form.get("has_practical"))
    has_assg = bool(request.form.get("has_assignment"))

    try:
        sub_id = run("""INSERT INTO subjects (department_id, semester, code, name, credits, has_practical, has_assignment)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                     (did, sem, code, name, credits, has_prac, has_assg))
        log_audit("SUBJECT_CREATED", "subjects", sub_id, f"{code}: {name}")
        flash(f"Subject {code} ({name}) created successfully.", "success")
    except Exception:
        app.logger.exception("Failed creating subject")
        flash("Could not create subject. Code may already exist.", "error")

    return redirect(url_for("teacher_academic_setup"))

@app.route("/teacher/attendance")
@required("teacher")
def teacher_attendance():
    subs = all_rows("SELECT id, code, name FROM subjects WHERE semester=5 ORDER BY code")
    students = all_rows("""
        SELECT u.id, u.full_name, u.username, sp.enrollment_no
        FROM users u
        JOIN student_profiles sp ON sp.student_id = u.id
        WHERE u.role='student' AND sp.semester=5 AND sp.division='A'
        ORDER BY u.full_name ASC
    """)
    corrections = all_rows("""
        SELECT cr.id, cr.reason, cr.created_at, u.full_name as student_name, sp.enrollment_no,
               sess.session_date, s.code as subject_code
        FROM attendance_correction_requests cr
        JOIN users u ON u.id = cr.student_id
        JOIN student_profiles sp ON sp.student_id = u.id
        JOIN attendance_sessions sess ON sess.id = cr.session_id
        JOIN subjects s ON s.id = sess.subject_id
        WHERE cr.status = 'Pending'
        ORDER BY cr.created_at DESC
    """)
    today = date.today().strftime("%Y-%m-%d")
    return render_template("teacher/attendance.html",
                           subjects=subs, students=students, correction_requests=corrections, today_date=today)

@app.route("/teacher/attendance/record", methods=["POST"])
@required("teacher")
def teacher_record_attendance():
    sub_id = int(request.form.get("subject_id"))
    sdate = request.form.get("session_date")
    stype = request.form.get("session_type", "Lecture")
    topic = request.form.get("topic_covered", "").strip()
    tid = session["user_id"]

    try:
        sess_id = run("""INSERT INTO attendance_sessions (subject_id, teacher_id, session_date, session_type, division, topic_covered)
                         VALUES (%s, %s, %s, %s, 'A', %s)""",
                      (sub_id, tid, sdate, stype, topic))

        students = all_rows("SELECT id FROM users WHERE role='student'")
        for s in students:
            status = request.form.get(f"status_{s['id']}", "Present")
            run("INSERT INTO attendance_records (session_id, student_id, status) VALUES (%s, %s, %s)",
                (sess_id, s["id"], status))

        log_audit("ATTENDANCE_SESSION_RECORDED", "attendance_sessions", sess_id, f"Date: {sdate}, Type: {stype}")
        flash(f"Class attendance for {sdate} recorded successfully for {len(students)} students.", "success")
    except Exception:
        app.logger.exception("Failed recording attendance")
        flash("Could not record attendance session.", "error")

    return redirect(url_for("teacher_attendance"))

@app.route("/teacher/attendance/review-correction/<int:request_id>", methods=["POST"])
@required("teacher")
def teacher_review_correction(request_id):
    action = request.form.get("action", "Approved")
    cr = one("SELECT * FROM attendance_correction_requests WHERE id=%s", (request_id,))
    if not cr:
        flash("Request not found.", "error")
        return redirect(url_for("teacher_attendance"))

    tid = session["user_id"]
    try:
        run("""UPDATE attendance_correction_requests
               SET status=%s, reviewed_by=%s, reviewed_at=NOW()
               WHERE id=%s""", (action, tid, request_id))

        if action == "Approved":
            # Update record to Present
            run("UPDATE attendance_records SET status='Present', remarks='Faculty approved correction' WHERE session_id=%s AND student_id=%s",
                (cr["session_id"], cr["student_id"]))

        log_audit("ATTENDANCE_CORRECTION_REVIEWED", "attendance_correction_requests", request_id, f"Action: {action}")
        flash(f"Correction request {action.lower()} successfully.", "success")
    except Exception:
        app.logger.exception("Error reviewing correction")
        flash("Error processing correction request.", "error")

    return redirect(url_for("teacher_attendance"))

@app.route("/teacher/attendance/export-csv")
@required("teacher")
def teacher_export_attendance_csv():
    records = all_rows("""
        SELECT u.full_name, sp.enrollment_no, s.code as subject_code, sess.session_date,
               sess.session_type, ar.status
        FROM attendance_records ar
        JOIN attendance_sessions sess ON sess.id = ar.session_id
        JOIN subjects s ON s.id = sess.subject_id
        JOIN users u ON u.id = ar.student_id
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        ORDER BY sess.session_date DESC, u.full_name ASC
    """)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Apex Institute of Technology & Research - Class Attendance Register"])
    writer.writerow([f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow(["Academic Year: 2026-2027", "Semester: 5", "Division: A"])
    writer.writerow([])
    writer.writerow(["Student Name", "Enrollment No", "Subject Code", "Session Date", "Session Type", "Status"])
    for r in records:
        writer.writerow([r["full_name"], r["enrollment_no"] or "DEMO", r["subject_code"], r["session_date"], r["session_type"], r["status"]])

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=class_attendance_register.csv"})

@app.route("/teacher/assessments")
@required("teacher")
def teacher_assessments():
    assessments = all_rows("""
        SELECT a.*, s.code as subject_code, s.name as subject_name
        FROM assessments a
        JOIN subjects s ON s.id = a.subject_id
        ORDER BY a.exam_date DESC
    """)
    subs = all_rows("SELECT id, code, name FROM subjects WHERE semester=5 ORDER BY code")
    return render_template("teacher/assessments.html", assessments=assessments, subjects=subs)

@app.route("/teacher/assessments/create", methods=["POST"])
@required("teacher")
def teacher_create_assessment():
    sub_id = int(request.form.get("subject_id"))
    title = request.form.get("title", "").strip()
    atype = request.form.get("assessment_type", "Internal Assessment")
    max_m = float(request.form.get("max_marks", 25.0))
    weight = float(request.form.get("weightage", 10.0))
    edate = request.form.get("exam_date")

    try:
        aid = run("""INSERT INTO assessments (subject_id, title, assessment_type, max_marks, weightage, exam_date, is_published, created_by)
                     VALUES (%s, %s, %s, %s, %s, %s, 0, %s)""",
                  (sub_id, title, atype, max_m, weight, edate, session["user_id"]))
        log_audit("ASSESSMENT_CREATED", "assessments", aid, f"{title} ({atype})")
        flash(f"Assessment '{title}' created in draft mode. Enter marks and publish when ready.", "success")
    except Exception:
        app.logger.exception("Failed creating assessment")
        flash("Could not create assessment.", "error")

    return redirect(url_for("teacher_assessments"))

@app.route("/teacher/assessments/toggle-publish/<int:assessment_id>", methods=["POST"])
@required("teacher")
def teacher_toggle_publish_assessment(assessment_id):
    ass = one("SELECT * FROM assessments WHERE id=%s", (assessment_id,))
    if not ass:
        flash("Assessment not found.", "error")
        return redirect(url_for("teacher_assessments"))

    new_status = 0 if ass["is_published"] else 1
    run("UPDATE assessments SET is_published=%s, published_at=NOW() WHERE id=%s", (new_status, assessment_id))
    log_audit("ASSESSMENT_VISIBILITY_CHANGED", "assessments", assessment_id, f"Published: {new_status}")
    flash(f"Assessment visibility changed: {'Published to students' if new_status else 'Hidden (Draft mode)'}.", "success")
    return redirect(url_for("teacher_assessments"))

@app.route("/teacher/assessments/<int:assessment_id>/grade")
@required("teacher")
def teacher_grade_assessment(assessment_id):
    ass = one("""
        SELECT a.*, s.code as subject_code, s.name as subject_name
        FROM assessments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.id = %s
    """, (assessment_id,))
    if not ass:
        flash("Assessment not found.", "error")
        return redirect(url_for("teacher_assessments"))

    roster = all_rows("""
        SELECT u.id, u.full_name, u.username, sp.enrollment_no,
               ar.marks_obtained, ar.remarks
        FROM users u
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        LEFT JOIN assessment_results ar ON ar.student_id = u.id AND ar.assessment_id = %s
        WHERE u.role = 'student'
        ORDER BY u.full_name ASC
    """, (assessment_id,))

    return render_template("teacher/grade_assessment.html", assessment=ass, students_roster=roster)

@app.route("/teacher/assessments/<int:assessment_id>/save-grades", methods=["POST"])
@required("teacher")
def teacher_save_assessment_grades(assessment_id):
    ass = one("SELECT * FROM assessments WHERE id=%s", (assessment_id,))
    if not ass:
        flash("Assessment not found.", "error")
        return redirect(url_for("teacher_assessments"))

    students = all_rows("SELECT id FROM users WHERE role='student'")
    tid = session["user_id"]
    saved_count = 0

    for s in students:
        sid = s["id"]
        val_str = request.form.get(f"marks_{sid}", "").strip()
        remarks = request.form.get(f"remarks_{sid}", "").strip()
        if val_str != "":
            try:
                marks = min(max(float(val_str), 0.0), float(ass["max_marks"]))
                existing = one("SELECT id FROM assessment_results WHERE assessment_id=%s AND student_id=%s", (assessment_id, sid))
                if existing:
                    run("UPDATE assessment_results SET marks_obtained=%s, remarks=%s, evaluated_by=%s WHERE id=%s",
                        (marks, remarks, tid, existing["id"]))
                else:
                    run("""INSERT INTO assessment_results (assessment_id, student_id, marks_obtained, remarks, evaluated_by)
                           VALUES (%s, %s, %s, %s, %s)""",
                        (assessment_id, sid, marks, remarks, tid))
                saved_count += 1
            except ValueError:
                pass

    log_audit("ASSESSMENT_GRADES_SAVED", "assessments", assessment_id, f"Graded {saved_count} students")
    flash(f"Marks successfully saved for {saved_count} students.", "success")
    return redirect(url_for("teacher_grade_assessment", assessment_id=assessment_id))

@app.route("/teacher/practicals")
@required("teacher")
def teacher_practicals():
    practicals = all_rows("""
        SELECT p.*, s.code as subject_code, s.name as subject_name,
               SUM(CASE WHEN ps.status IN ('Submitted', 'Needs Resubmission') THEN 1 ELSE 0 END) as pending_count
        FROM practicals p
        JOIN subjects s ON s.id = p.subject_id
        LEFT JOIN practical_submissions ps ON ps.practical_id = p.id
        GROUP BY p.id, s.code, s.name
        ORDER BY s.code, p.experiment_no ASC
    """)
    subs = all_rows("SELECT id, code, name, has_practical FROM subjects WHERE semester=5 ORDER BY code")
    return render_template("teacher/practicals.html", practicals=practicals, subjects=subs)

@app.route("/teacher/practicals/create", methods=["POST"])
@required("teacher")
def teacher_create_practical():
    sub_id = int(request.form.get("subject_id"))
    exp_no = int(request.form.get("experiment_no", 1))
    title = request.form.get("title", "").strip()
    desc = request.form.get("description", "").strip()
    sdate = request.form.get("scheduled_date") or None
    max_m = float(request.form.get("max_marks", 25.0))

    try:
        pid = run("""INSERT INTO practicals (subject_id, experiment_no, title, description, scheduled_date, max_marks, created_by)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                  (sub_id, exp_no, title, desc, sdate, max_m, session["user_id"]))

        # Populate initial practical submissions rows
        students = all_rows("SELECT id FROM users WHERE role='student'")
        for s in students:
            run("INSERT INTO practical_submissions (practical_id, student_id, status) VALUES (%s, %s, 'Not Started')",
                (pid, s["id"]))

        log_audit("PRACTICAL_CREATED", "practicals", pid, f"Exp #{exp_no}: {title}")
        flash(f"Experiment #{exp_no} created and assigned to all students.", "success")
    except Exception:
        app.logger.exception("Failed creating practical")
        flash("Could not create practical experiment.", "error")

    return redirect(url_for("teacher_practicals"))

@app.route("/teacher/practicals/<int:practical_id>/evaluate")
@required("teacher")
def teacher_evaluate_practical(practical_id):
    p = one("""
        SELECT p.*, s.code as subject_code, s.name as subject_name
        FROM practicals p
        JOIN subjects s ON s.id = p.subject_id
        WHERE p.id = %s
    """, (practical_id,))
    if not p:
        flash("Experiment not found.", "error")
        return redirect(url_for("teacher_practicals"))

    subs = all_rows("""
        SELECT u.id, u.full_name, u.username, sp.enrollment_no,
               ps.status, ps.lab_attendance, ps.journal_submitted,
               ps.viva_marks, ps.execution_marks, ps.total_marks, ps.feedback
        FROM users u
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        LEFT JOIN practical_submissions ps ON ps.student_id = u.id AND ps.practical_id = %s
        WHERE u.role = 'student'
        ORDER BY u.full_name ASC
    """, (practical_id,))

    return render_template("teacher/evaluate_practical.html", practical=p, student_submissions=subs)

@app.route("/teacher/practicals/<int:practical_id>/save-evaluations", methods=["POST"])
@required("teacher")
def teacher_save_practical_evaluations(practical_id):
    students = all_rows("SELECT id FROM users WHERE role='student'")
    tid = session["user_id"]

    for s in students:
        sid = s["id"]
        status = request.form.get(f"status_{sid}", "Evaluated")
        journal = bool(request.form.get(f"journal_{sid}"))
        viva = float(request.form.get(f"viva_{sid}", 0.0) or 0.0)
        exe = float(request.form.get(f"execution_{sid}", 0.0) or 0.0)
        fb = request.form.get(f"feedback_{sid}", "").strip()
        tot = viva + exe

        existing = one("SELECT id FROM practical_submissions WHERE practical_id=%s AND student_id=%s", (practical_id, sid))
        if existing:
            run("""UPDATE practical_submissions
                   SET status=%s, journal_submitted=%s, viva_marks=%s, execution_marks=%s, total_marks=%s,
                       feedback=%s, evaluated_by=%s, evaluated_at=NOW()
                   WHERE id=%s""",
                (status, journal, viva, exe, tot, fb, tid, existing["id"]))
        else:
            run("""INSERT INTO practical_submissions (practical_id, student_id, status, journal_submitted, viva_marks, execution_marks, total_marks, feedback, evaluated_by, evaluated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (practical_id, sid, status, journal, viva, exe, tot, fb, tid))

    log_audit("PRACTICAL_EVALUATIONS_SAVED", "practicals", practical_id, f"Saved evaluations for {len(students)} students")
    flash("Practical laboratory evaluations successfully updated.", "success")
    return redirect(url_for("teacher_evaluate_practical", practical_id=practical_id))

@app.route("/teacher/assignments")
@required("teacher")
def teacher_assignments():
    assignments = all_rows("""
        SELECT a.*, s.code as subject_code, s.name as subject_name,
               COUNT(sub.id) as submission_count
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        LEFT JOIN assignment_submissions sub ON sub.assignment_id = a.id
        GROUP BY a.id, s.code, s.name
        ORDER BY a.due_date DESC
    """)
    subs = all_rows("SELECT id, code, name FROM subjects WHERE semester=5 ORDER BY code")
    return render_template("teacher/assignments.html", assignments=assignments, subjects=subs)

@app.route("/teacher/assignments/create", methods=["POST"])
@required("teacher")
def teacher_create_assignment():
    sub_id = int(request.form.get("subject_id"))
    title = request.form.get("title", "").strip()
    desc = request.form.get("description", "").strip()
    inst = request.form.get("instructions", "").strip()
    due = request.form.get("due_date")
    max_m = float(request.form.get("max_marks", 20.0))

    try:
        aid = run("""INSERT INTO assignments (subject_id, title, description, instructions, due_date, max_marks, created_by)
                     VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                  (sub_id, title, desc, inst, due, max_m, session["user_id"]))
        log_audit("ASSIGNMENT_CREATED", "assignments", aid, title)
        flash(f"Assignment '{title}' posted successfully.", "success")
    except Exception:
        app.logger.exception("Failed creating assignment")
        flash("Could not create assignment.", "error")

    return redirect(url_for("teacher_assignments"))

@app.route("/teacher/assignments/<int:assignment_id>/grade")
@required("teacher")
def teacher_grade_assignment(assignment_id):
    ass = one("""
        SELECT a.*, s.code as subject_code, s.name as subject_name
        FROM assignments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.id = %s
    """, (assignment_id,))
    if not ass:
        flash("Assignment not found.", "error")
        return redirect(url_for("teacher_assignments"))

    roster = all_rows("""
        SELECT u.id as student_id, u.full_name, u.username, sp.enrollment_no,
               sub.id as submission_id, sub.submission_text, sub.attachment_name,
               sub.submitted_at, sub.is_late, sub.status, sub.marks_obtained, sub.feedback
        FROM users u
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        LEFT JOIN assignment_submissions sub ON sub.student_id = u.id AND sub.assignment_id = %s
        WHERE u.role = 'student'
        ORDER BY u.full_name ASC
    """, (assignment_id,))

    return render_template("teacher/grade_assignment.html", assignment=ass, submissions_roster=roster)

@app.route("/teacher/assignments/<int:assignment_id>/save-grades", methods=["POST"])
@required("teacher")
def teacher_save_assignment_grades(assignment_id):
    ass = one("SELECT * FROM assignments WHERE id=%s", (assignment_id,))
    if not ass:
        flash("Assignment not found.", "error")
        return redirect(url_for("teacher_assignments"))

    students = all_rows("SELECT id FROM users WHERE role='student'")
    tid = session["user_id"]

    for s in students:
        sid = s["id"]
        status = request.form.get(f"status_{sid}", "Evaluated")
        m_str = request.form.get(f"marks_{sid}", "").strip()
        fb = request.form.get(f"feedback_{sid}", "").strip()
        marks = float(m_str) if m_str != "" else None

        existing = one("SELECT id FROM assignment_submissions WHERE assignment_id=%s AND student_id=%s", (assignment_id, sid))
        if existing:
            run("""UPDATE assignment_submissions
                   SET status=%s, marks_obtained=%s, feedback=%s, evaluated_by=%s, evaluated_at=NOW()
                   WHERE id=%s""", (status, marks, fb, tid, existing["id"]))
        elif marks is not None or fb:
            run("""INSERT INTO assignment_submissions (assignment_id, student_id, status, marks_obtained, feedback, evaluated_by, evaluated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, NOW())""",
                (assignment_id, sid, status, marks, fb, tid))

    log_audit("ASSIGNMENT_GRADES_SAVED", "assignments", assignment_id, "Saved grades")
    flash("Coursework evaluations successfully saved.", "success")
    return redirect(url_for("teacher_grade_assignment", assignment_id=assignment_id))

@app.route("/teacher/projects")
@required("teacher")
def teacher_projects():
    projs = all_rows("""
        SELECT p.*, u.full_name as guide_name,
               GROUP_CONCAT(DISTINCT stu.full_name SEPARATOR ', ') as members_str
        FROM projects p
        JOIN users u ON u.id = p.guide_id
        LEFT JOIN project_members pm ON pm.project_id = p.id
        LEFT JOIN users stu ON stu.id = pm.student_id
        GROUP BY p.id, u.full_name
    """)
    for p in projs:
        p["milestones"] = all_rows("SELECT * FROM project_milestones WHERE project_id=%s ORDER BY target_date ASC", (p["id"],))

    return render_template("teacher/projects.html", projects=projs)

@app.route("/teacher/projects/milestone/<int:milestone_id>", methods=["POST"])
@required("teacher")
def teacher_update_milestone(milestone_id):
    pct = int(request.form.get("progress_pct", 0))
    status = request.form.get("status", "Pending")
    remarks = request.form.get("guide_remarks", "").strip()

    cdate = date.today().strftime("%Y-%m-%d") if status == "Approved" else None
    run("""UPDATE project_milestones
           SET progress_pct=%s, status=%s, guide_remarks=%s, completed_date=%s
           WHERE id=%s""", (pct, status, remarks, cdate, milestone_id))

    log_audit("PROJECT_MILESTONE_UPDATED", "project_milestones", milestone_id, f"{status} ({pct}%)")
    flash("Project milestone review updated.", "success")
    return redirect(url_for("teacher_projects"))

@app.route("/teacher/announcements")
@required("teacher")
def teacher_announcements():
    ann = all_rows("""
        SELECT a.*, u.full_name as author_name
        FROM announcements a
        LEFT JOIN users u ON u.id = a.created_by
        ORDER BY a.created_at DESC
    """)
    return render_template("teacher/announcements.html", announcements=ann)

@app.route("/teacher/announcements/create", methods=["POST"])
@required("teacher")
def teacher_create_announcement():
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    cat = request.form.get("category", "Academic")
    target = request.form.get("target_role", "all")

    if not title or not content:
        flash("Title and content are required.", "error")
        return redirect(url_for("teacher_announcements"))

    try:
        aid = run("""INSERT INTO announcements (title, content, category, target_role, created_by)
                     VALUES (%s, %s, %s, %s, %s)""",
                  (title, content, cat, target, session["user_id"]))
        log_audit("ANNOUNCEMENT_POSTED", "announcements", aid, title)
        flash("Institutional announcement broadcasted successfully.", "success")
    except Exception:
        app.logger.exception("Failed creating announcement")
        flash("Could not post announcement.", "error")

    return redirect(url_for("teacher_announcements"))

@app.route("/teacher/reports")
@required("teacher")
def teacher_reports():
    conn = connect()
    cur = conn.cursor(dictionary=True)
    students = all_rows("""
        SELECT u.id, u.full_name, sp.enrollment_no, d.code as department_code,
               p.math_marks, p.science_marks, p.english_marks
        FROM users u
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        LEFT JOIN departments d ON d.id = sp.department_id
        JOIN performance p ON p.student_id = u.id
        WHERE u.role = 'student'
        ORDER BY u.full_name ASC
    """)
    at_risk_list = []
    for s in students:
        ra = get_student_risk_assessment(cur, s["id"])
        core_avg = round((s["math_marks"] + s["science_marks"] + s["english_marks"]) / 3, 1)
        if ra["status"] != "On Track":
            at_risk_list.append({
                "full_name": s["full_name"],
                "enrollment_no": s["enrollment_no"],
                "department_code": s["department_code"],
                "attendance_pct": ra["attendance_pct"],
                "core_marks_avg": core_avg,
                "status": ra["status"],
                "badge_class": ra["badge_class"],
                "reason": ra["reasons"][0] if ra["reasons"] else "Review required"
            })
    cur.close()
    conn.close()

    return render_template("teacher/reports.html", at_risk_list=at_risk_list)

@app.route("/teacher/reports/attendance-csv")
@required("teacher")
def teacher_export_marks_csv():
    records = all_rows("""
        SELECT u.full_name, sp.enrollment_no, s.code, a.title, a.assessment_type,
               ar.marks_obtained, a.max_marks
        FROM assessment_results ar
        JOIN assessments a ON a.id = ar.assessment_id
        JOIN subjects s ON s.id = a.subject_id
        JOIN users u ON u.id = ar.student_id
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        WHERE a.is_published = 1
        ORDER BY s.code, u.full_name ASC
    """)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Apex Institute of Technology & Research - Official Marks Register"])
    writer.writerow([f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow(["Academic Year: 2026-2027", "Semester: 5"])
    writer.writerow([])
    writer.writerow(["Student Name", "Enrollment No", "Subject Code", "Assessment Title", "Type", "Marks Obtained", "Max Marks"])
    for r in records:
        writer.writerow([r["full_name"], r["enrollment_no"] or "DEMO", r["code"], r["title"], r["assessment_type"], r["marks_obtained"], r["max_marks"]])

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=official_marks_register.csv"})

@app.route("/teacher/reports/at-risk-csv")
@required("teacher")
def teacher_export_at_risk_csv():
    conn = connect()
    cur = conn.cursor(dictionary=True)
    students = all_rows("""
        SELECT u.id, u.full_name, sp.enrollment_no, d.code as department_code,
               p.math_marks, p.science_marks, p.english_marks
        FROM users u
        LEFT JOIN student_profiles sp ON sp.student_id = u.id
        LEFT JOIN departments d ON d.id = sp.department_id
        JOIN performance p ON p.student_id = u.id
        WHERE u.role = 'student'
        ORDER BY u.full_name ASC
    """)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Apex Institute of Technology & Research - Academic Support Intervention Roster"])
    writer.writerow([f"Generated Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"])
    writer.writerow(["Academic Year: 2026-2027", "Intervention Threshold: Attendance < 75% or Marks < 50%"])
    writer.writerow([])
    writer.writerow(["Student Name", "Enrollment No", "Department", "Attendance %", "Core Marks Avg", "Status", "Primary Concerns"])

    for s in students:
        ra = get_student_risk_assessment(cur, s["id"])
        core_avg = round((s["math_marks"] + s["science_marks"] + s["english_marks"]) / 3, 1)
        if ra["status"] != "On Track":
            writer.writerow([s["full_name"], s["enrollment_no"] or "DEMO", s["department_code"],
                             ra["attendance_pct"], core_avg, ra["status"], "; ".join(ra["reasons"])])

    cur.close()
    conn.close()

    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=at_risk_students_roster.csv"})

@app.route("/teacher/ai-analytics")
@required("teacher")
def teacher_ai_analytics():
    conn = connect()
    cur = conn.cursor(dictionary=True)

    students = all_rows("SELECT id FROM users WHERE role='student'")
    total = len(students)
    shortage = 0
    support = 0
    ontrack = 0

    for s in students:
        ra = get_student_risk_assessment(cur, s["id"])
        if ra["status"] == "Support Recommended":
            support += 1
        elif ra["status"] == "Needs Attention":
            shortage += 1
        else:
            ontrack += 1

    cur.close()
    conn.close()

    return render_template("teacher/ai_analytics.html",
                           total_students=total,
                           shortage_count=shortage,
                           support_needed_count=support,
                           on_track_count=ontrack)

@app.route("/teacher/audit-logs")
@required("teacher")
def teacher_audit_logs():
    logs = all_rows("""
        SELECT al.*, u.full_name as user_name, u.username
        FROM audit_logs al
        JOIN users u ON u.id = al.user_id
        ORDER BY al.created_at DESC
        LIMIT 100
    """)
    return render_template("teacher/audit_logs.html", audit_logs=logs)

# -------------------------------------------------------------
# Backward-Compatible Route (Preserved from existing codebase)
# -------------------------------------------------------------

@app.route("/teacher/update/<int:student_id>", methods=["POST"])
@required("teacher")
def update_student(student_id):
    if not one("SELECT id FROM users WHERE id=%s AND role='student'", (student_id,)):
        flash("Student not found.", "error")
        return redirect(url_for("dashboard"))
    try:
        vals = {}
        for key in FEATURES:
            value = float(request.form.get(key, ""))
            if key == "study_hours":
                if not 0 <= value <= 24: raise ValueError("Study hours must be from 0 to 24.")
            elif not 0 <= value <= 100:
                raise ValueError(f"{key.replace('_',' ').title()} must be from 0 to 100.")
            vals[key] = value
        run("""UPDATE performance SET math_marks=%s,science_marks=%s,english_marks=%s,
            attendance=%s,study_hours=%s,previous_score=%s WHERE student_id=%s""",
            tuple(vals[k] for k in FEATURES) + (student_id,))
        log_audit("STUDENT_PERFORMANCE_UPDATED", "performance", student_id, f"Updated core scores: {vals}")
        flash("Student performance updated.", "success")
    except (ValueError, TypeError):
        flash("Enter valid numbers. Marks, attendance and previous score: 0–100; study hours: 0–24.", "error")
    except Error:
        app.logger.exception("Update failed")
        flash("Could not update the record.", "error")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)
