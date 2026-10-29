import os
import mysql.connector

DB = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "student_performance")
}

def migrate():
    conn = mysql.connector.connect(**DB)
    cur = conn.cursor()
    print("Connected to MySQL. Applying migrations...")

    # Update users table if needed
    try:
        cur.execute("ALTER TABLE users MODIFY COLUMN role ENUM('student','teacher','admin') NOT NULL DEFAULT 'student'")
    except Exception as e:
        print("Note on users.role:", e)

    tables = [
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            code VARCHAR(20) NOT NULL UNIQUE,
            description TEXT
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS subjects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department_id INT NOT NULL,
            semester INT NOT NULL,
            code VARCHAR(20) NOT NULL UNIQUE,
            name VARCHAR(100) NOT NULL,
            credits INT NOT NULL DEFAULT 4,
            has_practical BOOLEAN DEFAULT TRUE,
            has_assignment BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS student_profiles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL UNIQUE,
            enrollment_no VARCHAR(30) NOT NULL UNIQUE,
            department_id INT NOT NULL,
            semester INT NOT NULL DEFAULT 5,
            division VARCHAR(10) NOT NULL DEFAULT 'A',
            academic_year VARCHAR(20) NOT NULL DEFAULT '2026-2027',
            profile_photo_url VARCHAR(255) DEFAULT NULL,
            dob DATE DEFAULT NULL,
            phone VARCHAR(20) DEFAULT NULL,
            mentor_id INT DEFAULT NULL,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
            FOREIGN KEY (mentor_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS teacher_profiles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            teacher_id INT NOT NULL UNIQUE,
            employee_code VARCHAR(30) NOT NULL UNIQUE,
            department_id INT NOT NULL,
            designation VARCHAR(50) NOT NULL DEFAULT 'Assistant Professor',
            qualification VARCHAR(100) DEFAULT 'M.Tech, Ph.D.',
            cabin_office VARCHAR(50) DEFAULT 'Lab Block 302',
            phone VARCHAR(20) DEFAULT NULL,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS subject_teachers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT NOT NULL,
            teacher_id INT NOT NULL,
            division VARCHAR(10) NOT NULL DEFAULT 'A',
            academic_year VARCHAR(20) NOT NULL DEFAULT '2026-2027',
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance_sessions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT NOT NULL,
            teacher_id INT NOT NULL,
            session_date DATE NOT NULL,
            session_type ENUM('Lecture','Practical','Laboratory','Tutorial','Seminar') NOT NULL DEFAULT 'Lecture',
            division VARCHAR(10) NOT NULL DEFAULT 'A',
            topic_covered VARCHAR(255) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance_records (
            id INT AUTO_INCREMENT PRIMARY KEY,
            session_id INT NOT NULL,
            student_id INT NOT NULL,
            status ENUM('Present','Absent','Late','Approved Leave') NOT NULL DEFAULT 'Present',
            remarks VARCHAR(255) DEFAULT '',
            UNIQUE KEY unique_session_student (session_id, student_id),
            FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS attendance_correction_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            session_id INT NOT NULL,
            reason TEXT NOT NULL,
            status ENUM('Pending','Approved','Rejected') NOT NULL DEFAULT 'Pending',
            reviewed_by INT DEFAULT NULL,
            reviewed_at TIMESTAMP NULL DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
            FOREIGN KEY (reviewed_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS assessments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT NOT NULL,
            title VARCHAR(150) NOT NULL,
            assessment_type ENUM('Internal Assessment','Unit Test','Mid Semester','End Semester','Practical Exam','Viva','Remedial') NOT NULL DEFAULT 'Internal Assessment',
            max_marks DECIMAL(5,2) NOT NULL DEFAULT 25.0,
            weightage DECIMAL(5,2) NOT NULL DEFAULT 10.0,
            exam_date DATE NOT NULL,
            is_published BOOLEAN NOT NULL DEFAULT FALSE,
            published_at TIMESTAMP NULL DEFAULT NULL,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS assessment_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            assessment_id INT NOT NULL,
            student_id INT NOT NULL,
            marks_obtained DECIMAL(5,2) NOT NULL,
            remarks VARCHAR(255) DEFAULT '',
            evaluated_by INT DEFAULT NULL,
            evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY unique_assessment_student (assessment_id, student_id),
            FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (evaluated_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS practicals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT NOT NULL,
            experiment_no INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            scheduled_date DATE DEFAULT NULL,
            max_marks DECIMAL(5,2) NOT NULL DEFAULT 25.0,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS practical_submissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            practical_id INT NOT NULL,
            student_id INT NOT NULL,
            status ENUM('Not Started','Scheduled','In Progress','Submitted','Evaluated','Needs Resubmission') NOT NULL DEFAULT 'Not Started',
            lab_attendance ENUM('Present','Absent') NOT NULL DEFAULT 'Present',
            journal_submitted BOOLEAN NOT NULL DEFAULT FALSE,
            viva_marks DECIMAL(5,2) DEFAULT 0,
            execution_marks DECIMAL(5,2) DEFAULT 0,
            total_marks DECIMAL(5,2) DEFAULT 0,
            feedback TEXT,
            evaluated_by INT DEFAULT NULL,
            evaluated_at TIMESTAMP NULL DEFAULT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_practical_student (practical_id, student_id),
            FOREIGN KEY (practical_id) REFERENCES practicals(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (evaluated_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS assignments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            description TEXT,
            instructions TEXT,
            due_date DATETIME NOT NULL,
            max_marks DECIMAL(5,2) NOT NULL DEFAULT 20.0,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS assignment_submissions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            assignment_id INT NOT NULL,
            student_id INT NOT NULL,
            submission_text TEXT,
            attachment_name VARCHAR(255) DEFAULT NULL,
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_late BOOLEAN NOT NULL DEFAULT FALSE,
            status ENUM('Submitted','Evaluated','Needs Resubmission') NOT NULL DEFAULT 'Submitted',
            marks_obtained DECIMAL(5,2) DEFAULT NULL,
            feedback TEXT,
            evaluated_by INT DEFAULT NULL,
            evaluated_at TIMESTAMP NULL DEFAULT NULL,
            UNIQUE KEY unique_assign_student (assignment_id, student_id),
            FOREIGN KEY (assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (evaluated_by) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            project_type ENUM('Mini Project','Major Project') NOT NULL DEFAULT 'Mini Project',
            department_id INT NOT NULL,
            academic_year VARCHAR(20) NOT NULL DEFAULT '2026-2027',
            guide_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            FOREIGN KEY (guide_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS project_members (
            id INT AUTO_INCREMENT PRIMARY KEY,
            project_id INT NOT NULL,
            student_id INT NOT NULL,
            role_in_team VARCHAR(50) NOT NULL DEFAULT 'Team Member',
            UNIQUE KEY unique_project_member (project_id, student_id),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS project_milestones (
            id INT AUTO_INCREMENT PRIMARY KEY,
            project_id INT NOT NULL,
            milestone_name VARCHAR(150) NOT NULL,
            target_date DATE NOT NULL,
            completed_date DATE DEFAULT NULL,
            status ENUM('Pending','In Review','Approved') NOT NULL DEFAULT 'Pending',
            progress_pct INT NOT NULL DEFAULT 0,
            guide_remarks TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS activities (
            id INT AUTO_INCREMENT PRIMARY KEY,
            student_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            category ENUM('Hackathon','Workshop','Seminar','Technical Certification','Sports','Cultural','Extracurricular') NOT NULL DEFAULT 'Workshop',
            organizer VARCHAR(150) NOT NULL,
            activity_date DATE NOT NULL,
            certificate_ref VARCHAR(255) DEFAULT '',
            verified_status ENUM('Pending','Verified','Rejected') NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS timetable (
            id INT AUTO_INCREMENT PRIMARY KEY,
            department_id INT NOT NULL,
            semester INT NOT NULL DEFAULT 5,
            division VARCHAR(10) NOT NULL DEFAULT 'A',
            day_of_week ENUM('Monday','Tuesday','Wednesday','Thursday','Friday','Saturday') NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            subject_id INT NOT NULL,
            teacher_id INT NOT NULL,
            room_number VARCHAR(50) NOT NULL DEFAULT 'Room 401',
            session_type ENUM('Lecture','Practical','Laboratory','Tutorial') NOT NULL DEFAULT 'Lecture',
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS announcements (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            content TEXT NOT NULL,
            category ENUM('Academic','Examination','Event','Urgent','General') NOT NULL DEFAULT 'Academic',
            target_role ENUM('all','student','teacher') NOT NULL DEFAULT 'all',
            department_id INT DEFAULT NULL,
            created_by INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            title VARCHAR(200) NOT NULL,
            message TEXT NOT NULL,
            category VARCHAR(50) NOT NULL DEFAULT 'general',
            link VARCHAR(255) DEFAULT '',
            is_read BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            action VARCHAR(100) NOT NULL,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INT DEFAULT NULL,
            details TEXT,
            ip_address VARCHAR(45) DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS student_queries (
            id INT AUTO_INCREMENT PRIMARY KEY,
            reference_code VARCHAR(20) NOT NULL UNIQUE,
            student_id INT NOT NULL,
            subject_id INT NOT NULL,
            assigned_faculty_id INT DEFAULT NULL,
            category ENUM('Academic', 'Attendance', 'Marks', 'Practical/Lab', 'Assignment', 'Timetable', 'Examination', 'Technical Issue', 'Other') NOT NULL DEFAULT 'Academic',
            title VARCHAR(200) NOT NULL,
            description TEXT NOT NULL,
            attachment_name VARCHAR(255) DEFAULT NULL,
            status ENUM('Open', 'In Progress', 'Waiting for Student', 'Resolved', 'Unassigned') NOT NULL DEFAULT 'Open',
            resolution_note TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP NULL DEFAULT NULL,
            INDEX idx_queries_student (student_id),
            INDEX idx_queries_faculty (assigned_faculty_id),
            INDEX idx_queries_status (status),
            INDEX idx_queries_ref (reference_code),
            FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_faculty_id) REFERENCES users(id) ON DELETE SET NULL
        ) ENGINE=InnoDB;
        """,
        """
        CREATE TABLE IF NOT EXISTS query_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            query_id INT NOT NULL,
            sender_id INT NOT NULL,
            message_text TEXT NOT NULL,
            attachment_name VARCHAR(255) DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            read_at TIMESTAMP NULL DEFAULT NULL,
            INDEX idx_messages_query (query_id),
            INDEX idx_messages_sender (sender_id),
            FOREIGN KEY (query_id) REFERENCES student_queries(id) ON DELETE CASCADE,
            FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
        ) ENGINE=InnoDB;
        """
    ]

    for stmt in tables:
        cur.execute(stmt)
        conn.commit()

    print("All migration tables created or verified successfully!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    migrate()

