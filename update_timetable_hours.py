import os
import mysql.connector

DB = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "student_performance")
}

def update_timetable():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor(dictionary=True)
    print("Updating college timetable to 10:15 AM - 5:15 PM (7 hours duration)...")

    # Clear current timetable
    cur.execute("DELETE FROM timetable")

    # Fetch departments, subjects, teachers
    cur.execute("SELECT id, code FROM departments WHERE code='CE'")
    ce_dept = cur.fetchone()["id"]

    cur.execute("SELECT id, code FROM subjects")
    sub_map = {row["code"]: row["id"] for row in cur.fetchall()}

    cur.execute("SELECT id, username FROM users WHERE role='teacher'")
    t_map = {row["username"]: row["id"] for row in cur.fetchall()}

    # College working hours: 10:15 AM (10:15:00) to 5:15 PM (17:15:00), 7 hours
    timetable_schedule = [
        # Monday: 10:15 AM - 5:15 PM
        (ce_dept, 5, "A", "Monday", "10:15:00", "11:15:00", sub_map["CS501"], t_map["teacher"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Monday", "11:15:00", "12:15:00", sub_map["CS502"], t_map["prof_deshmukh"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Monday", "12:15:00", "13:15:00", sub_map["CS504"], t_map["prof_patel"], "Room 401", "Lecture"),
        # 13:15 - 14:15 Lunch Break
        (ce_dept, 5, "A", "Monday", "14:15:00", "16:15:00", sub_map["CS506"], t_map["teacher"], "Lab Block 202", "Laboratory"),
        (ce_dept, 5, "A", "Monday", "16:15:00", "17:15:00", sub_map["CS503"], t_map["dr_sharma"], "Room 401", "Lecture"),

        # Tuesday: 10:15 AM - 5:15 PM
        (ce_dept, 5, "A", "Tuesday", "10:15:00", "11:15:00", sub_map["CS504"], t_map["prof_patel"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Tuesday", "11:15:00", "12:15:00", sub_map["CS503"], t_map["dr_sharma"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Tuesday", "12:15:00", "13:15:00", sub_map["CS505"], t_map["dr_sharma"], "Room 401", "Lecture"),
        # 13:15 - 14:15 Lunch Break
        (ce_dept, 5, "A", "Tuesday", "14:15:00", "16:15:00", sub_map["CS501"], t_map["teacher"], "Lab Block 301", "Practical"),
        (ce_dept, 5, "A", "Tuesday", "16:15:00", "17:15:00", sub_map["CS507"], t_map["prof_deshmukh"], "Room 401", "Lecture"),

        # Wednesday: 10:15 AM - 5:15 PM
        (ce_dept, 5, "A", "Wednesday", "10:15:00", "11:15:00", sub_map["CS502"], t_map["prof_deshmukh"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Wednesday", "11:15:00", "12:15:00", sub_map["CS501"], t_map["teacher"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Wednesday", "12:15:00", "13:15:00", sub_map["CS507"], t_map["prof_deshmukh"], "Room 401", "Lecture"),
        # 13:15 - 14:15 Lunch Break
        (ce_dept, 5, "A", "Wednesday", "14:15:00", "16:15:00", sub_map["CS504"], t_map["prof_patel"], "AI & Data Lab", "Practical"),
        (ce_dept, 5, "A", "Wednesday", "16:15:00", "17:15:00", sub_map["CS505"], t_map["dr_sharma"], "Room 401", "Tutorial"),

        # Thursday: 10:15 AM - 5:15 PM
        (ce_dept, 5, "A", "Thursday", "10:15:00", "11:15:00", sub_map["CS505"], t_map["dr_sharma"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Thursday", "11:15:00", "12:15:00", sub_map["CS504"], t_map["prof_patel"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Thursday", "12:15:00", "13:15:00", sub_map["CS502"], t_map["prof_deshmukh"], "Room 401", "Lecture"),
        # 13:15 - 14:15 Lunch Break
        (ce_dept, 5, "A", "Thursday", "14:15:00", "15:15:00", sub_map["CS503"], t_map["dr_sharma"], "Room 401", "Tutorial"),
        (ce_dept, 5, "A", "Thursday", "15:15:00", "17:15:00", sub_map["CS502"], t_map["prof_deshmukh"], "Network Lab 104", "Practical"),

        # Friday: 10:15 AM - 5:15 PM
        (ce_dept, 5, "A", "Friday", "10:15:00", "12:15:00", sub_map["CS504"], t_map["prof_patel"], "AI & Data Lab", "Laboratory"),
        (ce_dept, 5, "A", "Friday", "12:15:00", "13:15:00", sub_map["CS501"], t_map["teacher"], "Room 401", "Lecture"),
        # 13:15 - 14:15 Lunch Break
        (ce_dept, 5, "A", "Friday", "14:15:00", "15:15:00", sub_map["CS503"], t_map["dr_sharma"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Friday", "15:15:00", "16:15:00", sub_map["CS505"], t_map["dr_sharma"], "Room 401", "Lecture"),
        (ce_dept, 5, "A", "Friday", "16:15:00", "17:15:00", sub_map["CS504"], t_map["prof_patel"], "Room 401", "Seminar")
    ]

    for did, sem, div, dow, st, et, sub_id, tid, room, stype in timetable_schedule:
        cur.execute("""
            INSERT INTO timetable (department_id, semester, division, day_of_week, start_time, end_time, subject_id, teacher_id, room_number, session_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (did, sem, div, dow, st, et, sub_id, tid, room, stype))

    conn.commit()
    print(f"Successfully inserted {len(timetable_schedule)} timetable entries from 10:15 AM to 5:15 PM.")
    cur.close()
    conn.close()

if __name__ == "__main__":
    update_timetable()

