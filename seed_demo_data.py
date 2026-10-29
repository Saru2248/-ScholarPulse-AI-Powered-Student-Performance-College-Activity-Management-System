import os
import random
from datetime import datetime, timedelta
import mysql.connector
from werkzeug.security import generate_password_hash

DB = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "student_performance")
}

def seed():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)
    print("Beginning comprehensive demo data seeding...")

    # 1. Departments
    departments_data = [
        ("Computer Engineering", "CE", "Department of Computer Engineering and AI"),
        ("Information Technology", "IT", "Department of Information Technology and Cloud Systems")
    ]
    dept_ids = {}
    for name, code, desc in departments_data:
        cur.execute("SELECT id FROM departments WHERE code=%s", (code,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO departments (name, code, description) VALUES (%s, %s, %s)", (name, code, desc))
            dept_ids[code] = cur.lastrowid
        else:
            dept_ids[code] = row["id"]

    # 2. Subjects (6-8 per semester)
    subjects_data = [
        # CE Sem 5
        (dept_ids["CE"], 5, "CS501", "Database Management Systems", 4, True, True),
        (dept_ids["CE"], 5, "CS502", "Advanced Computer Networks", 4, True, True),
        (dept_ids["CE"], 5, "CS503", "Software Engineering & Agile", 3, False, True),
        (dept_ids["CE"], 5, "CS504", "Machine Learning & AI", 4, True, True),
        (dept_ids["CE"], 5, "CS505", "Theory of Computation", 3, False, True),
        (dept_ids["CE"], 5, "CS506", "Web Technology & Cloud Lab", 2, True, True),
        (dept_ids["CE"], 5, "CS507", "Professional Ethics & Management", 2, False, False),
        # IT Sem 5
        (dept_ids["IT"], 5, "IT501", "Operating Systems Architecture", 4, True, True),
        (dept_ids["IT"], 5, "IT502", "Cyber Security & Cryptography", 4, True, True),
        (dept_ids["IT"], 5, "IT503", "Cloud Computing & DevOps", 4, True, True),
        (dept_ids["IT"], 5, "IT504", "Mobile Application Development", 3, True, True),
        (dept_ids["IT"], 5, "IT505", "Data Science & Big Data", 4, True, True),
        (dept_ids["IT"], 5, "IT506", "IoT and Embedded Systems", 3, True, True)
    ]
    subject_map = {}
    for did, sem, code, name, credits, has_prac, has_assg in subjects_data:
        cur.execute("SELECT id FROM subjects WHERE code=%s", (code,))
        row = cur.fetchone()
        if not row:
            cur.execute("""INSERT INTO subjects (department_id, semester, code, name, credits, has_practical, has_assignment)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""", (did, sem, code, name, credits, has_prac, has_assg))
            subject_map[code] = cur.lastrowid
        else:
            subject_map[code] = row["id"]

    # 3. Teachers (6+ fictional teachers)
    pw_teacher = generate_password_hash("Teacher@123")
    teachers_data = [
        ("teacher", "Prof. Project Teacher (DEMO)", "TCHR-001", dept_ids["CE"], "Associate Professor", "M.Tech, Ph.D.", "Block A-201"),
        ("dr_sharma", "Dr. Rajesh Sharma (DEMO)", "TCHR-002", dept_ids["CE"], "Professor & HOD", "Ph.D. (IIT Bombay)", "Block A-101"),
        ("prof_patel", "Prof. Sneha Patel (DEMO)", "TCHR-003", dept_ids["CE"], "Assistant Professor", "M.Tech (AI & ML)", "Block A-204"),
        ("prof_deshmukh", "Prof. Amit Deshmukh (DEMO)", "TCHR-004", dept_ids["CE"], "Assistant Professor", "M.E. (Computer Networks)", "Block A-206"),
        ("prof_joshi", "Prof. Priya Joshi (DEMO)", "TCHR-005", dept_ids["IT"], "Associate Professor", "M.Tech (Cyber Security)", "Block B-302"),
        ("prof_kulkarni", "Prof. Rohan Kulkarni (DEMO)", "TCHR-006", dept_ids["IT"], "Assistant Professor", "M.Tech (Cloud Systems)", "Block B-305")
    ]
    teacher_ids = {}
    for uname, fname, ecode, did, desig, qual, cabin in teachers_data:
        cur.execute("SELECT id FROM users WHERE username=%s", (uname,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (%s, %s, %s, 'teacher')",
                        (fname, uname, pw_teacher))
            uid = cur.lastrowid
        else:
            uid = row["id"]
        teacher_ids[uname] = uid

        cur.execute("SELECT id FROM teacher_profiles WHERE teacher_id=%s", (uid,))
        if not cur.fetchone():
            cur.execute("""INSERT INTO teacher_profiles (teacher_id, employee_code, department_id, designation, qualification, cabin_office, phone)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (uid, ecode, did, desig, qual, cabin, "9876543210"))

    # Map teachers to subjects
    teacher_subject_assignments = [
        ("CS501", teacher_ids["teacher"], "A"),
        ("CS502", teacher_ids["prof_deshmukh"], "A"),
        ("CS503", teacher_ids["dr_sharma"], "A"),
        ("CS504", teacher_ids["prof_patel"], "A"),
        ("CS505", teacher_ids["dr_sharma"], "A"),
        ("CS506", teacher_ids["teacher"], "A"),
        ("CS507", teacher_ids["prof_deshmukh"], "A"),
        ("IT501", teacher_ids["prof_kulkarni"], "A"),
        ("IT502", teacher_ids["prof_joshi"], "A"),
        ("IT503", teacher_ids["prof_kulkarni"], "A"),
        ("IT504", teacher_ids["prof_joshi"], "A"),
        ("IT505", teacher_ids["prof_joshi"], "A"),
        ("IT506", teacher_ids["prof_kulkarni"], "A")
    ]
    for scode, tid, div in teacher_subject_assignments:
        sub_id = subject_map[scode]
        cur.execute("SELECT id FROM subject_teachers WHERE subject_id=%s AND teacher_id=%s AND division=%s", (sub_id, tid, div))
        if not cur.fetchone():
            cur.execute("INSERT INTO subject_teachers (subject_id, teacher_id, division, academic_year) VALUES (%s, %s, %s, '2026-2027')",
                        (sub_id, tid, div))

    # 4. Students (30+ fictional students)
    pw_student = generate_password_hash("Student@123")
    students_data = [
        ("student", "Aarav Patel (DEMO)", "DEMO-2024-CE-001", "CE", 5, "A", 88.5, 84, 86, 88.0, 4.5, 82),
        ("aditi", "Aditi Sharma (DEMO)", "DEMO-2024-CE-002", "CE", 5, "A", 68.0, 62, 70, 69.5, 2.0, 65),
        ("rahul", "Rahul Verma (DEMO)", "DEMO-2024-CE-003", "CE", 5, "A", 48.0, 42, 52, 58.0, 1.2, 50),
        ("ananya", "Ananya Iyer (DEMO)", "DEMO-2024-CE-004", "CE", 5, "A", 94.0, 92, 95, 96.0, 5.5, 92),
        ("rohit", "Rohit Kadam (DEMO)", "DEMO-2024-CE-005", "CE", 5, "A", 76.0, 72, 74, 80.0, 3.0, 75),
        ("tanvi", "Tanvi Mehta (DEMO)", "DEMO-2024-CE-006", "CE", 5, "A", 82.0, 80, 85, 85.0, 3.5, 80),
        ("siddharth", "Siddharth Rao (DEMO)", "DEMO-2024-CE-007", "CE", 5, "A", 71.0, 68, 70, 75.0, 2.5, 68),
        ("pooja", "Pooja Hegde (DEMO)", "DEMO-2024-CE-008", "CE", 5, "A", 89.0, 85, 90, 91.0, 4.0, 86),
        ("karan", "Karan Malhotra (DEMO)", "DEMO-2024-CE-009", "CE", 5, "A", 61.0, 58, 64, 66.0, 1.8, 60),
        ("ishaan", "Ishaan Roy (DEMO)", "DEMO-2024-CE-010", "CE", 5, "A", 84.0, 88, 82, 87.0, 3.8, 83),
        ("diya", "Diya Sen (DEMO)", "DEMO-2024-CE-011", "CE", 5, "A", 79.0, 75, 80, 82.0, 3.0, 78),
        ("varun", "Varun Nair (DEMO)", "DEMO-2024-CE-012", "CE", 5, "A", 64.0, 60, 68, 70.0, 2.0, 65),
        ("neha", "Neha Gupta (DEMO)", "DEMO-2024-CE-013", "CE", 5, "A", 91.0, 89, 93, 94.0, 5.0, 90),
        ("manish", "Manish Pandey (DEMO)", "DEMO-2024-CE-014", "CE", 5, "A", 54.0, 48, 56, 62.0, 1.5, 52),
        ("rhea", "Rhea Kapoor (DEMO)", "DEMO-2024-CE-015", "CE", 5, "A", 86.0, 84, 88, 89.0, 4.2, 85),
        # IT Students
        ("vikram", "Vikram Singh (DEMO)", "DEMO-2024-IT-001", "IT", 5, "A", 85.0, 82, 87, 88.0, 4.0, 84),
        ("priyanka", "Priyanka Das (DEMO)", "DEMO-2024-IT-002", "IT", 5, "A", 73.0, 70, 75, 78.0, 2.8, 72),
        ("arjun", "Arjun Reddy (DEMO)", "DEMO-2024-IT-003", "IT", 5, "A", 59.0, 55, 62, 64.0, 1.6, 58),
        ("sneha_s", "Sneha Sawant (DEMO)", "DEMO-2024-IT-004", "IT", 5, "A", 92.0, 90, 94, 95.0, 5.0, 91),
        ("nikhil", "Nikhil Chavan (DEMO)", "DEMO-2024-IT-005", "IT", 5, "A", 77.0, 74, 78, 81.0, 3.2, 76),
        ("ananya_m", "Ananya Mishra (DEMO)", "DEMO-2024-IT-006", "IT", 5, "A", 81.0, 79, 83, 84.0, 3.5, 80),
        ("sameer", "Sameer Khan (DEMO)", "DEMO-2024-IT-007", "IT", 5, "A", 69.0, 65, 72, 73.0, 2.2, 67),
        ("shruti", "Shruti Joshi (DEMO)", "DEMO-2024-IT-008", "IT", 5, "A", 88.0, 86, 89, 90.0, 4.2, 87),
        ("gaurav", "Gaurav Bhatt (DEMO)", "DEMO-2024-IT-009", "IT", 5, "A", 52.0, 46, 55, 60.0, 1.4, 50),
        ("meera", "Meera Pillai (DEMO)", "DEMO-2024-IT-010", "IT", 5, "A", 83.0, 81, 85, 86.0, 3.6, 82),
        ("akash", "Akash Shinde (DEMO)", "DEMO-2024-IT-011", "IT", 5, "A", 75.0, 72, 76, 79.0, 3.0, 74),
        ("divya", "Divya Jain (DEMO)", "DEMO-2024-IT-012", "IT", 5, "A", 67.0, 63, 69, 71.0, 2.1, 66),
        ("harsh", "Harsh Vardhan (DEMO)", "DEMO-2024-IT-013", "IT", 5, "A", 90.0, 88, 92, 93.0, 4.8, 89),
        ("kavya", "Kavya Menon (DEMO)", "DEMO-2024-IT-014", "IT", 5, "A", 80.0, 77, 82, 83.0, 3.4, 79),
        ("omkar", "Omkar Gaikwad (DEMO)", "DEMO-2024-IT-015", "IT", 5, "A", 58.0, 52, 60, 63.0, 1.5, 55),
        ("tanya", "Tanya Agarwal (DEMO)", "DEMO-2024-IT-016", "IT", 5, "A", 87.0, 85, 88, 89.0, 4.0, 86),
        ("ayush", "Ayush Tiwari (DEMO)", "DEMO-2024-IT-017", "IT", 5, "A", 74.0, 71, 75, 77.0, 2.7, 72)
    ]

    student_records = []
    for uname, fname, eno, dcode, sem, div, mth, sci, eng, att, sth, prev in students_data:
        cur.execute("SELECT id FROM users WHERE username=%s", (uname,))
        row = cur.fetchone()
        if not row:
            cur.execute("INSERT INTO users (full_name, username, password_hash, role) VALUES (%s, %s, %s, 'student')",
                        (fname, uname, pw_student))
            uid = cur.lastrowid
        else:
            uid = row["id"]

        # Ensure performance table row (backward compatibility)
        cur.execute("SELECT id FROM performance WHERE student_id=%s", (uid,))
        if not cur.fetchone():
            cur.execute("""INSERT INTO performance (student_id, math_marks, science_marks, english_marks, attendance, study_hours, previous_score)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (uid, mth, sci, eng, att, sth, prev))
        else:
            cur.execute("""UPDATE performance SET math_marks=%s, science_marks=%s, english_marks=%s, attendance=%s, study_hours=%s, previous_score=%s
                           WHERE student_id=%s""",
                        (mth, sci, eng, att, sth, prev, uid))

        # Profile
        cur.execute("SELECT id FROM student_profiles WHERE student_id=%s", (uid,))
        if not cur.fetchone():
            mentor = teacher_ids["dr_sharma"] if dcode == "CE" else teacher_ids["prof_joshi"]
            cur.execute("""INSERT INTO student_profiles (student_id, enrollment_no, department_id, semester, division, academic_year, mentor_id)
                           VALUES (%s, %s, %s, %s, %s, '2026-2027', %s)""",
                        (uid, eno, dept_ids[dcode], sem, div, mentor))

        student_records.append({"id": uid, "username": uname, "dept": dcode, "sem": sem, "div": div, "att_rate": att / 100.0})

    conn.commit()

    # 5. Attendance Sessions & Records (Past 3 months: Aug 1 to Oct 28, 2026)
    # Check if attendance sessions already exist
    cur.execute("SELECT COUNT(*) as cnt FROM attendance_sessions")
    if cur.fetchone()["cnt"] < 30:
        print("Generating 3 months of attendance sessions & records...")
        ce_subs = [s for s in subjects_data if s[0] == dept_ids["CE"]]
        ce_students = [s for s in student_records if s["dept"] == "CE"]

        start_date = datetime(2026, 8, 3)
        end_date = datetime(2026, 10, 28)
        current = start_date

        random.seed(42)
        while current <= end_date:
            if current.weekday() < 5: # Mon-Fri
                # 2-3 sessions per day
                for scode, tid, div in [("CS501", teacher_ids["teacher"], "A"),
                                        ("CS502", teacher_ids["prof_deshmukh"], "A"),
                                        ("CS504", teacher_ids["prof_patel"], "A")]:
                    sub_id = subject_map[scode]
                    cur.execute("""INSERT INTO attendance_sessions (subject_id, teacher_id, session_date, session_type, division, topic_covered)
                                   VALUES (%s, %s, %s, 'Lecture', %s, %s)""",
                                (sub_id, tid, current.strftime("%Y-%m-%d"), div, f"Unit discussion - {scode} Lecture"))
                    sess_id = cur.lastrowid

                    # Records for CE students
                    rec_rows = []
                    for s in ce_students:
                        # Determine status based on student's attendance profile
                        roll = random.random()
                        if roll < s["att_rate"]:
                            st = "Present"
                        elif roll < s["att_rate"] + 0.05:
                            st = "Late"
                        else:
                            st = "Absent"
                        rec_rows.append((sess_id, s["id"], st, ""))

                    for r in rec_rows:
                        cur.execute("INSERT INTO attendance_records (session_id, student_id, status, remarks) VALUES (%s, %s, %s, %s)", r)
            current += timedelta(days=1)
        conn.commit()

    # 6. Assessments & Results
    cur.execute("SELECT COUNT(*) as cnt FROM assessments")
    if cur.fetchone()["cnt"] < 5:
        print("Creating assessments and grading results...")
        assessments_list = [
            ("CS501", "Unit Test 1 - Relational Algebra & SQL", "Unit Test", 25.0, 10.0, "2026-08-25", True, teacher_ids["teacher"]),
            ("CS501", "Mid-Semester Examination", "Mid Semester", 50.0, 20.0, "2026-09-20", True, teacher_ids["teacher"]),
            ("CS501", "Internal Assessment 2 - Normalization & Indexing", "Internal Assessment", 25.0, 10.0, "2026-10-15", True, teacher_ids["teacher"]),
            ("CS502", "Unit Test 1 - Transport Protocols", "Unit Test", 25.0, 10.0, "2026-08-28", True, teacher_ids["prof_deshmukh"]),
            ("CS502", "Mid-Semester Examination", "Mid Semester", 50.0, 20.0, "2026-09-22", True, teacher_ids["prof_deshmukh"]),
            ("CS504", "Unit Test 1 - Linear Models & Cost Functions", "Unit Test", 25.0, 10.0, "2026-09-02", True, teacher_ids["prof_patel"]),
            ("CS504", "Mid-Semester Examination", "Mid Semester", 50.0, 20.0, "2026-09-25", True, teacher_ids["prof_patel"]),
            ("CS504", "End-Semester Mock Practical", "Practical Exam", 25.0, 10.0, "2026-10-20", True, teacher_ids["prof_patel"]),
            ("CS501", "End Semester Final Examination (Upcoming)", "End Semester", 100.0, 50.0, "2026-11-20", False, teacher_ids["teacher"])
        ]
        ce_students = [s for s in student_records if s["dept"] == "CE"]
        for scode, title, atype, maxm, weight, edate, is_pub, creator in assessments_list:
            cur.execute("""INSERT INTO assessments (subject_id, title, assessment_type, max_marks, weightage, exam_date, is_published, published_at, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (subject_map[scode], title, atype, maxm, weight, edate, is_pub,
                         datetime.now() if is_pub else None, creator))
            ass_id = cur.lastrowid
            if is_pub:
                for s in ce_students:
                    pct = s["att_rate"] * (0.85 + random.uniform(-0.1, 0.15))
                    obtained = round(min(max(pct * maxm, 0.3 * maxm), maxm), 1)
                    cur.execute("""INSERT INTO assessment_results (assessment_id, student_id, marks_obtained, remarks, evaluated_by)
                                   VALUES (%s, %s, %s, %s, %s)""",
                                (ass_id, s["id"], obtained, "Good effort" if obtained >= 0.7 * maxm else "Needs revision", creator))
        conn.commit()

    # 7. Practicals & Submissions
    cur.execute("SELECT COUNT(*) as cnt FROM practicals")
    if cur.fetchone()["cnt"] < 4:
        print("Creating practical experiments & laboratory records...")
        practicals_list = [
            ("CS501", 1, "DDL/DML Queries and Integrity Constraints", "Implement relational tables with primary, foreign keys and constraints.", "2026-08-10", 25.0, teacher_ids["teacher"]),
            ("CS501", 2, "Complex Nested Queries & Aggregate Functions", "Write multi-table joins, subqueries, and grouping queries on retail database.", "2026-08-24", 25.0, teacher_ids["teacher"]),
            ("CS501", 3, "PL/SQL Stored Procedures & Triggers", "Develop autonomous triggers for audit logging and procedures for ledger balance.", "2026-09-08", 25.0, teacher_ids["teacher"]),
            ("CS501", 4, "Indexing & Query Execution Plan Optimization", "Analyze EXPLAIN query plans and evaluate B-Tree index benchmarks.", "2026-09-22", 25.0, teacher_ids["teacher"]),
            ("CS504", 1, "Linear and Logistic Regression from Scratch", "Implement gradient descent optimization on housing price dataset.", "2026-08-18", 25.0, teacher_ids["prof_patel"]),
            ("CS504", 2, "Decision Trees and Random Forest Classifier", "Train ensemble tree classifier and evaluate confusion matrix on loan data.", "2026-09-12", 25.0, teacher_ids["prof_patel"]),
            ("CS504", 3, "K-Means Clustering and PCA Dimensionality Reduction", "Cluster customer segmentation data and visualize principal components.", "2026-10-06", 25.0, teacher_ids["prof_patel"])
        ]
        ce_students = [s for s in student_records if s["dept"] == "CE"]
        for scode, exp_no, title, desc, sdate, maxm, creator in practicals_list:
            cur.execute("""INSERT INTO practicals (subject_id, experiment_no, title, description, scheduled_date, max_marks, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (subject_map[scode], exp_no, title, desc, sdate, maxm, creator))
            prac_id = cur.lastrowid

            for s in ce_students:
                # Distribute statuses: high performers are Evaluated, lower have pending/resubmission
                if s["username"] == "rahul" and exp_no >= 3:
                    st = "Needs Resubmission" if exp_no == 3 else "Not Started"
                    viva, exe, tot = 4.0, 5.0, 9.0
                    fb = "Code logic incomplete. Please resubmit."
                elif s["username"] == "aditi" and exp_no == 4:
                    st = "Submitted"
                    viva, exe, tot = 0.0, 0.0, 0.0
                    fb = "Under review by instructor."
                else:
                    st = "Evaluated"
                    viva = round(random.uniform(7.0, 10.0), 1)
                    exe = round(random.uniform(9.0, 14.5), 1)
                    tot = viva + exe
                    fb = "Verified experiment and journal."

                cur.execute("""INSERT INTO practical_submissions
                               (practical_id, student_id, status, lab_attendance, journal_submitted, viva_marks, execution_marks, total_marks, feedback, evaluated_by, evaluated_at)
                               VALUES (%s, %s, %s, 'Present', %s, %s, %s, %s, %s, %s, %s)""",
                            (prac_id, s["id"], st, True if st in ('Submitted','Evaluated') else False,
                             viva, exe, tot, fb, creator, datetime.now() if st == 'Evaluated' else None))
        conn.commit()

    # 8. Assignments & Submissions
    cur.execute("SELECT COUNT(*) as cnt FROM assignments")
    if cur.fetchone()["cnt"] < 3:
        print("Creating assignments and student coursework...")
        assignments_list = [
            ("CS501", "Assignment 1: Relational Algebra & ER Modeling",
             "Model an e-commerce platform and convert into 3NF relational schemas.",
             "Submit single PDF document with schema diagrams.", "2026-08-30 23:59:00", 20.0, teacher_ids["teacher"]),
            ("CS501", "Assignment 2: Query Optimization & Indexing Strategies",
             "Analyze slow queries and recommend composite indexes for MySQL engine.",
             "Include EXPLAIN output and execution time comparison.", "2026-10-05 23:59:00", 20.0, teacher_ids["teacher"]),
            ("CS504", "Assignment 1: Supervised Learning Implementation",
             "Implement and tune Random Forest Regressor on synthetic student dataset.",
             "Upload Jupyter notebook and brief report.", "2026-10-18 23:59:00", 25.0, teacher_ids["prof_patel"]),
            ("CS502", "Assignment 1: TCP Congestion Control Case Study",
             "Compare TCP Reno vs BBR under high latency wireless conditions.",
             "Analyze packet drop graphs in Wireshark.", "2026-11-05 23:59:00", 20.0, teacher_ids["prof_deshmukh"])
        ]
        ce_students = [s for s in student_records if s["dept"] == "CE"]
        for scode, title, desc, inst, due, maxm, creator in assignments_list:
            cur.execute("""INSERT INTO assignments (subject_id, title, description, instructions, due_date, max_marks, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (subject_map[scode], title, desc, inst, due, maxm, creator))
            assign_id = cur.lastrowid

            for s in ce_students:
                if "11-05" in due:
                    # Upcoming assignment - mostly pending
                    if s["username"] in ("ananya", "student"):
                        cur.execute("""INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, status)
                                       VALUES (%s, %s, %s, 'Submitted')""",
                                    (assign_id, s["id"], "Early draft submitted for review."))
                    continue

                if s["username"] == "rahul" and "10-18" in due:
                    continue # pending for Rahul!

                marks = round(random.uniform(14.0, maxm), 1)
                cur.execute("""INSERT INTO assignment_submissions (assignment_id, student_id, submission_text, status, marks_obtained, feedback, evaluated_by, evaluated_at)
                               VALUES (%s, %s, %s, 'Evaluated', %s, %s, %s, %s)""",
                            (assign_id, s["id"], "Completed assignment submitted on time.", marks,
                             "Well explained and organized.", creator, datetime.now()))
        conn.commit()

    # 9. Projects & Milestones
    cur.execute("SELECT COUNT(*) as cnt FROM projects")
    if cur.fetchone()["cnt"] < 2:
        print("Creating capstone / mini projects...")
        projects_data = [
            ("AI-Powered Campus Navigation & Asset Tracker", "IoT and indoor BLE beacon system for smart campus positioning.", "Major Project", dept_ids["CE"], teacher_ids["dr_sharma"],
             [("student", "Team Lead"), ("aditi", "Frontend Engineer"), ("rohit", "Embedded Systems")]),
            ("Automated Student Academic Risk Predictor", "Machine learning pipeline to identify students needing early interventions.", "Mini Project", dept_ids["CE"], teacher_ids["prof_patel"],
             [("ananya", "Team Lead"), ("tanvi", "Data Analyst"), ("ishaan", "Fullstack Developer")])
        ]
        for title, desc, ptype, did, gid, members in projects_data:
            cur.execute("""INSERT INTO projects (title, description, project_type, department_id, academic_year, guide_id)
                           VALUES (%s, %s, %s, %s, '2026-2027', %s)""", (title, desc, ptype, did, gid))
            pid = cur.lastrowid

            for uname, role in members:
                cur.execute("SELECT id FROM users WHERE username=%s", (uname,))
                u = cur.fetchone()
                if u:
                    cur.execute("INSERT INTO project_members (project_id, student_id, role_in_team) VALUES (%s, %s, %s)", (pid, u["id"], role))

            milestones = [
                (pid, "Problem Definition & Requirement Analysis", "2026-08-20", "2026-08-18", "Approved", 100, "Excellent scope document."),
                (pid, "System Architecture & Database Design", "2026-09-15", "2026-09-14", "Approved", 100, "Schema and DFD diagrams approved."),
                (pid, "Core Prototype Development & Module 1 Integration", "2026-10-15", "2026-10-16", "Approved", 100, "Working prototype verified."),
                (pid, "Final Testing, Security Audit & Thesis Report", "2026-11-15", None, "Pending", 40, "In progress.")
            ]
            for p_id, mname, tdate, cdate, st, pct, remarks in milestones:
                cur.execute("""INSERT INTO project_milestones (project_id, milestone_name, target_date, completed_date, status, progress_pct, guide_remarks)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""", (p_id, mname, tdate, cdate, st, pct, remarks))
        conn.commit()

    # 10. Student Extracurricular Activities & Certifications
    cur.execute("SELECT COUNT(*) as cnt FROM activities")
    if cur.fetchone()["cnt"] < 3:
        print("Adding verified activities and certifications...")
        # Add for student (Aarav Patel)
        s_u = teacher_ids.get("student")
        cur.execute("SELECT id FROM users WHERE username='student'")
        s_row = cur.fetchone()
        if s_row:
            sid = s_row["id"]
            acts = [
                (sid, "National Smart India Hackathon 2026 Finalist", "Hackathon", "Ministry of Education & AICTE", "2026-09-28", "SIH-2026-FIN-491", "Verified"),
                (sid, "AWS Certified Cloud Practitioner", "Technical Certification", "Amazon Web Services", "2026-08-15", "AWS-CCP-992144", "Verified"),
                (sid, "IEEE International Student Symposium on AI", "Seminar", "IEEE Computer Society", "2026-10-05", "IEEE-CONF-108", "Verified")
            ]
            for s_id, t, cat, org, adate, cref, vstatus in acts:
                cur.execute("""INSERT INTO activities (student_id, title, category, organizer, activity_date, certificate_ref, verified_status)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""", (s_id, t, cat, org, adate, cref, vstatus))
        conn.commit()

    # 11. Timetable
    cur.execute("SELECT COUNT(*) as cnt FROM timetable")
    if cur.fetchone()["cnt"] < 5:
        print("Populating weekly timetable...")
        timetable_entries = [
            # Monday: 10:15 AM - 5:15 PM
            (dept_ids["CE"], 5, "A", "Monday", "10:15:00", "11:15:00", subject_map["CS501"], teacher_ids["teacher"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Monday", "11:15:00", "12:15:00", subject_map["CS502"], teacher_ids["prof_deshmukh"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Monday", "12:15:00", "13:15:00", subject_map["CS504"], teacher_ids["prof_patel"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Monday", "14:15:00", "16:15:00", subject_map["CS506"], teacher_ids["teacher"], "Lab Block 202", "Laboratory"),
            (dept_ids["CE"], 5, "A", "Monday", "16:15:00", "17:15:00", subject_map["CS503"], teacher_ids["dr_sharma"], "Room 401", "Lecture"),

            # Tuesday: 10:15 AM - 5:15 PM
            (dept_ids["CE"], 5, "A", "Tuesday", "10:15:00", "11:15:00", subject_map["CS504"], teacher_ids["prof_patel"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Tuesday", "11:15:00", "12:15:00", subject_map["CS503"], teacher_ids["dr_sharma"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Tuesday", "12:15:00", "13:15:00", subject_map["CS505"], teacher_ids["dr_sharma"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Tuesday", "14:15:00", "16:15:00", subject_map["CS501"], teacher_ids["teacher"], "Lab Block 301", "Practical"),
            (dept_ids["CE"], 5, "A", "Tuesday", "16:15:00", "17:15:00", subject_map["CS507"], teacher_ids["prof_deshmukh"], "Room 401", "Lecture"),

            # Wednesday: 10:15 AM - 5:15 PM
            (dept_ids["CE"], 5, "A", "Wednesday", "10:15:00", "11:15:00", subject_map["CS502"], teacher_ids["prof_deshmukh"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Wednesday", "11:15:00", "12:15:00", subject_map["CS501"], teacher_ids["teacher"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Wednesday", "12:15:00", "13:15:00", subject_map["CS507"], teacher_ids["prof_deshmukh"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Wednesday", "14:15:00", "16:15:00", subject_map["CS504"], teacher_ids["prof_patel"], "AI & Data Lab", "Practical"),
            (dept_ids["CE"], 5, "A", "Wednesday", "16:15:00", "17:15:00", subject_map["CS505"], teacher_ids["dr_sharma"], "Room 401", "Tutorial"),

            # Thursday: 10:15 AM - 5:15 PM
            (dept_ids["CE"], 5, "A", "Thursday", "10:15:00", "11:15:00", subject_map["CS505"], teacher_ids["dr_sharma"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Thursday", "11:15:00", "12:15:00", subject_map["CS504"], teacher_ids["prof_patel"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Thursday", "12:15:00", "13:15:00", subject_map["CS502"], teacher_ids["prof_deshmukh"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Thursday", "14:15:00", "15:15:00", subject_map["CS503"], teacher_ids["dr_sharma"], "Room 401", "Tutorial"),
            (dept_ids["CE"], 5, "A", "Thursday", "15:15:00", "17:15:00", subject_map["CS502"], teacher_ids["prof_deshmukh"], "Network Lab 104", "Practical"),

            # Friday: 10:15 AM - 5:15 PM
            (dept_ids["CE"], 5, "A", "Friday", "10:15:00", "12:15:00", subject_map["CS504"], teacher_ids["prof_patel"], "AI & Data Lab", "Laboratory"),
            (dept_ids["CE"], 5, "A", "Friday", "12:15:00", "13:15:00", subject_map["CS501"], teacher_ids["teacher"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Friday", "14:15:00", "15:15:00", subject_map["CS503"], teacher_ids["dr_sharma"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Friday", "15:15:00", "16:15:00", subject_map["CS505"], teacher_ids["dr_sharma"], "Room 401", "Lecture"),
            (dept_ids["CE"], 5, "A", "Friday", "16:15:00", "17:15:00", subject_map["CS504"], teacher_ids["prof_patel"], "Room 401", "Seminar")
        ]
        for did, sem, div, dow, st, et, sub_id, tid, room, stype in timetable_entries:
            cur.execute("""INSERT INTO timetable (department_id, semester, division, day_of_week, start_time, end_time, subject_id, teacher_id, room_number, session_type)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (did, sem, div, dow, st, et, sub_id, tid, room, stype))
        conn.commit()

    # 12. Announcements
    cur.execute("SELECT COUNT(*) as cnt FROM announcements")
    if cur.fetchone()["cnt"] < 3:
        print("Publishing announcements...")
        announcements_list = [
            ("Schedule for Semester 5 End-Semester Examinations (Dec 2026)",
             "The tentative timetable for regular and backlog end-semester exams has been released. Check the portal for hall tickets and room allocation.",
             "Examination", "all", dept_ids["CE"], teacher_ids["dr_sharma"]),
            ("Final Date for Journal Submission & Practical Evaluation",
             "All students must complete laboratory write-ups and obtain teacher signature by November 10, 2026. Resubmissions must be approved.",
             "Academic", "student", dept_ids["CE"], teacher_ids["teacher"]),
            ("Annual College Tech Symposium 'TechVerve 2026'",
             "Registration is now open for project showcase, codeathon, and robotics tracks. Certificates and cash awards for winning teams.",
             "Event", "all", None, teacher_ids["dr_sharma"]),
            ("Urgent: Minimum 75% Attendance Compliance Notice",
             "Students falling below 75% aggregate attendance must meet their respective faculty mentors before the upcoming internal assessment.",
             "Urgent", "student", dept_ids["CE"], teacher_ids["dr_sharma"])
        ]
        for title, content, cat, target, did, creator in announcements_list:
            cur.execute("""INSERT INTO announcements (title, content, category, target_role, department_id, created_by)
                           VALUES (%s, %s, %s, %s, %s, %s)""", (title, content, cat, target, did, creator))
        conn.commit()

    # 13. Notifications for demo students
    cur.execute("SELECT id FROM users WHERE username='student'")
    s_row = cur.fetchone()
    if s_row:
        sid = s_row["id"]
        cur.execute("SELECT COUNT(*) as cnt FROM notifications WHERE user_id=%s", (sid,))
        if cur.fetchone()["cnt"] == 0:
            notes = [
                (sid, "Mid-Semester Marks Published", "Your marks for CS501 and CS504 mid-semester examinations are now published.", "marks", "/marks"),
                (sid, "Practical Evaluation Updated", "Experiment 3: PL/SQL Stored Procedures has been evaluated by Prof. Project Teacher.", "practical", "/practicals"),
                (sid, "Upcoming Assignment Due Date", "CS502 Assignment 1 on TCP Congestion Control is due on Nov 5, 2026.", "assignment", "/assignments"),
                (sid, "Attendance Notice", "Your aggregate attendance is 88.5%. You are on track for examination eligibility.", "attendance", "/attendance")
            ]
            for u_id, title, msg, cat, link in notes:
                cur.execute("INSERT INTO notifications (user_id, title, message, category, link, is_read) VALUES (%s, %s, %s, %s, %s, FALSE)",
                            (u_id, title, msg, cat, link))
            conn.commit()

    # 14. Student Queries & Shared Conversations (Demo Data)
    cur.execute("SELECT COUNT(*) as cnt FROM student_queries")
    if cur.fetchone()["cnt"] < 5:
        print("Seeding realistic student queries & multi-turn conversations...")
        queries_seed = [
            ("SP-1001", "student", "CS501", teacher_ids["teacher"], "Academic",
             "Doubt regarding B-Tree vs B+ Tree Node Splitting in Unit 3",
             "Professor, during the Unit 3 lecture on indexing, you mentioned that B+ trees store data pointers only in leaf nodes while internal nodes store keys. When a leaf node overflows with order 4, does the median key get copied up or moved up?",
             None, "In Progress", None,
             [
                 ("student", "Professor, during the Unit 3 lecture on indexing, you mentioned that B+ trees store data pointers only in leaf nodes while internal nodes store keys. When a leaf node overflows with order 4, does the median key get copied up or moved up?", None, "2026-10-24 10:15:00"),
                 ("teacher", "Hello Aarav. In a B+ Tree, leaf nodes are linked sequentially in a doubly-linked list. When a leaf node overflows, the median key is copied up to the parent index node (so the leaf retains a copy of the key), whereas in a traditional B-Tree the median key is moved up. Let me know if you want to trace an insertion example.", None, "2026-10-24 14:30:00"),
                 ("student", "Thank you Prof! That clears up the distinction completely. Could you also review if slide 24 in lecture 6 has a diagram for order 4 insertion?", None, "2026-10-25 09:00:00")
             ]),

            ("SP-1002", "student", "CS504", teacher_ids["prof_patel"], "Practical/Lab",
             "Convergence issue in Gradient Descent practical implementation",
             "Prof. Sneha, when running Experiment 1 on the housing prices dataset, the cost function value oscillates instead of monotonically decreasing after iteration 50. I used learning rate alpha = 0.05.",
             "cost_vs_iteration.png", "Waiting for Student", None,
             [
                 ("student", "Prof. Sneha, when running Experiment 1 on the housing prices dataset, the cost function value oscillates instead of monotonically decreasing after iteration 50. I used learning rate alpha = 0.05.", "cost_vs_iteration.png", "2026-10-26 11:20:00"),
                 ("prof_patel", "Aarav, an oscillating cost function almost always indicates that your learning rate alpha is too large, causing the gradient steps to overshoot the global minimum. Try scaling your features using standard z-score normalization (mean 0, variance 1) or reduce alpha to 0.001. Please reply with the cost vs iteration plot once you test this.", None, "2026-10-26 16:45:00")
             ]),

            ("SP-1003", "aditi", "CS501", teacher_ids["teacher"], "Attendance",
             "Attendance record mismatch for Lab session on October 12",
             "Respected Sir, on October 12 I attended the 2-hour PL/SQL practical laboratory in Lab Block 301 and submitted my journal on the same day. However, my portal shows 'Absent' for that session.",
             None, "Resolved", "Attendance verified against physical laboratory attendance register and corrected to Present. Portal record updated.",
             [
                 ("aditi", "Respected Sir, on October 12 I attended the 2-hour PL/SQL practical laboratory in Lab Block 301 and submitted my journal on the same day. However, my portal shows 'Absent' for that session.", None, "2026-10-20 09:10:00"),
                 ("teacher", "Hello Aditi, I cross-checked the laboratory logbook for October 12. Your signature was present in the second row. I have updated your status to Present. Your updated attendance percentage is now reflected.", None, "2026-10-20 12:15:00"),
                 ("aditi", "Thank you very much Sir! The portal now shows 75.2% eligible attendance.", None, "2026-10-20 14:00:00")
             ]),

            ("SP-1004", "rahul", "CS502", teacher_ids["prof_deshmukh"], "Assignment",
             "Request for 24h extension on Assignment 1 due to medical leave",
             "Respected Prof. Deshmukh, I was hospitalized for viral fever over the weekend and missed 2 lectures. I have completed 80% of the TCP congestion simulation report. Could I submit by tomorrow evening without late penalty?",
             "medical_certificate_slip.pdf", "Open", None,
             [
                 ("rahul", "Respected Prof. Deshmukh, I was hospitalized for viral fever over the weekend and missed 2 lectures. I have completed 80% of the TCP congestion simulation report. Could I submit by tomorrow evening without late penalty?", "medical_certificate_slip.pdf", "2026-10-28 17:00:00")
             ]),

            ("SP-1005", "ananya", "CS505", teacher_ids["dr_sharma"], "Examination",
             "Syllabus scope for Mid-Semester Exam: Turing Machines vs PDA",
             "Dear Dr. Sharma, could you please confirm whether non-deterministic Turing Machines and the Halting Problem are included in next week's mid-semester examination syllabus or only Unit 1 to Unit 3 (Regular & Context-Free Languages)?",
             None, "Resolved", "Mid-semester exam covers Units 1, 2, and 3 only (DFA/NFA, Regular Expressions, CFLs and Pushdown Automata). Turing Machines are reserved for the End-Semester Examination.",
             [
                 ("ananya", "Dear Dr. Sharma, could you please confirm whether non-deterministic Turing Machines and the Halting Problem are included in next week's mid-semester examination syllabus or only Unit 1 to Unit 3 (Regular & Context-Free Languages)?", None, "2026-10-18 10:00:00"),
                 ("dr_sharma", "Ananya, the mid-semester examination syllabus is strictly limited to Modules 1 through 3. Turing Machines, decidability, and undecidability will be assessed in the final end-semester examination in December.", None, "2026-10-18 13:20:00")
             ]),

            ("SP-1006", "student", "CS503", None, "Technical Issue",
             "Jira backlog project access permission for Scrum team 4",
             "Our capstone project team is trying to link Jira agile sprint boards to the college Git server but receiving 403 Forbidden. Is there an admin token required?",
             None, "Unassigned", None,
             [
                 ("student", "Our capstone project team is trying to link Jira agile sprint boards to the college Git server but receiving 403 Forbidden. Is there an admin token required?", None, "2026-10-29 08:30:00")
             ])
        ]

        for ref, s_uname, scode, fac_id, cat, title, desc, attach, status, r_note, msg_list in queries_seed:
            cur.execute("SELECT id FROM users WHERE username=%s", (s_uname,))
            stu = cur.fetchone()
            if not stu:
                continue
            stu_id = stu["id"]
            sub_id = subject_map[scode]

            cur.execute("""
                INSERT INTO student_queries (reference_code, student_id, subject_id, assigned_faculty_id, category, title, description, attachment_name, status, resolution_note, resolved_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (ref, stu_id, sub_id, fac_id, cat, title, desc, attach, status, r_note, datetime.now() if status == "Resolved" else None))
            qid = cur.lastrowid

            for sender_uname, mtext, mattach, mdate in msg_list:
                sender_id = stu_id if sender_uname == s_uname else teacher_ids.get(sender_uname, fac_id)
                cur.execute("""
                    INSERT INTO query_messages (query_id, sender_id, message_text, attachment_name, created_at, read_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (qid, sender_id, mtext, mattach, mdate, mdate))

            # Seed notification
            if status == "Open" and fac_id:
                cur.execute("""
                    INSERT INTO notifications (user_id, title, message, category, link, is_read)
                    VALUES (%s, %s, %s, 'query', %s, FALSE)
                """, (fac_id, f"New Student Query: {ref}", f"New query '{title}' submitted.", f"/queries/{ref}"))
            elif status == "Waiting for Student":
                cur.execute("""
                    INSERT INTO notifications (user_id, title, message, category, link, is_read)
                    VALUES (%s, %s, %s, 'query', %s, FALSE)
                """, (stu_id, f"Faculty Response: {ref}", f"Professor replied to '{title}'. Action requested.", f"/queries/{ref}"))

        conn.commit()

    print("Demo data seeding completed successfully!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    seed()

