# ScholarPulse — AI-Powered Student Performance & College Activity Management System

## 1. Executive Summary
ScholarPulse is upgraded into a complete, modern, AI-powered College Management and Student Performance Analytics Platform for a single college (**Apex Institute of Technology & Research**).

The platform centralizes all essential academic activities:
- **Academic Performance Analytics:** Continuous assessment marks, unit tests, internal evaluation, and scikit-learn ML score projection.
- **Attendance Management:** Daily lecture/lab session tracking, minimum 75% statutory compliance alerts, consecutive recovery class calculation, correction requests, and CSV register exports.
- **Practicals & Laboratory Management:** Continuous laboratory assessment index, viva & code execution scoring, journal submission verification, and experiment status tracking.
- **Assignments & Coursework:** Creation, deadlines, student deliverable submissions, late submission tracking, and grading with teacher feedback.
- **Capstones, Projects & Skills Portfolio:** Milestone progress tracking, faculty guide reviews, and student extracurricular achievements portfolio (Hackathons, Certifications, Workshops).
- **Student-Faculty Messaging & Query Resolution:** Complete two-way academic query tracking, automatic division-based faculty routing, chronological message streams, unread badges, and multi-state status lifecycles.
- **Weekly Timetable & Academic Calendar:** Centralized lecture/lab schedules, room allotments, examination schedules, college announcements, and institutional working hours (10:15 AM – 5:15 PM, 7 Hours duration).
- **AI-Powered Academic Insights & Assistant:** Rule-based student risk diagnosis (On Track, Needs Attention, Support Recommended), transparent explanations, and natural-language query assistant for both students and faculty.

### ⏰ Official College Operating Hours & Timetable Schedule
- **College Start Time:** `10:15 AM`
- **College End Time:** `05:15 PM`
- **Total College Duration:** `7.0 Hours` (420 minutes)
- **Period Breakdown:**
  - **Slot 1:** `10:15 AM – 11:15 AM` (Morning Session / 2-Hr Lab Block Part 1)
  - **Slot 2:** `11:15 AM – 12:15 PM` (Morning Session / 2-Hr Lab Block Part 2)
  - **Slot 3:** `12:15 PM – 01:15 PM` (Mid-day Lecture)
  - **Lunch Recess:** `01:15 PM – 02:15 PM` (Common Institutional Break - 60 min)
  - **Slot 4:** `02:15 PM – 03:15 PM` (Afternoon Session / 2-Hr Lab Block Part 1)
  - **Slot 5:** `03:15 PM – 04:15 PM` (Afternoon Session / 2-Hr Lab Block Part 2)
  - **Slot 6:** `04:15 PM – 05:15 PM` (Evening Session / Seminar / Lab Wrap-up)

---

## 2. Authentication & Separate Role-Based Experiences

The platform provides two distinct, secure role-based portals:

### 🎓 Student Portal (`student`)
- **Dashboard:** Real-time stats (attendance %, average marks, ML score estimate, practicals completed %, pending coursework, and academic risk status).
- **Attendance:** Overall %, subject breakdown, recovery classes required, session history, and attendance correction requests.
- **Marks & Exams:** Official **published** marks only (unpublished marks remain strictly hidden), grade categories, and faculty remarks.
- **Practicals & Labs:** Experiment schedule, journal sign-off, viva marks, and execution marks.
- **Assignments:** Pending deadlines, solution text/link submissions, and graded feedback.
- **My Queries / Messages:** Raise academic doubts with auto-routing to subject faculty, two-way chronological conversations, and unread reply badges.
- **Projects & Skills:** Capstone milestone progress bar, guide review notes, and verified extracurricular certifications.
- **Timetable & Calendar:** Weekly schedule grid and upcoming examination dates.
- **AI Insights & Assistant:** Personalized academic health check, study priorities, and an interactive natural-language chat assistant.
- **In-App Notifications:** Real-time unread alert count and update history.
- **Profile:** Official institutional enrollment details, department, semester, and password update.

### 👨‍🏫 Admin / Faculty Portal (`teacher`)
- **Dashboard:** Live student roster, scikit-learn score projections, class average, attendance average, and students-at-risk intervention alerts.
- **Student 360 Registry:** Full student list, search by name/username/enrollment, department filters, individual 360-degree academic profile view, manual registration, and **validated CSV bulk import**.
- **Faculty Directory:** Department professors, employee codes, cabin numbers, and assigned subjects.
- **Academic Setup:** Department management, subject creation (credits, practical/assignment requirements), and statutory attendance policies.
- **Attendance Operations:** Record daily lecture/practical/lab attendance for class rosters, review and approve/reject student correction requests, and export class attendance registers to CSV.
- **Assessments & Marks Publishing:** Schedule unit tests/mid-semester/internal tests, enter marks per student, and toggle draft/published status.
- **Practicals & Labs Evaluation:** Create experiments and grade student submissions (viva, execution, journal signature).
- **Assignments & Grading:** Post assignments with deadlines and grade student deliverables.
- **Student Queries Resolution:** Dedicated query queue, conversation reply interface, status workflow (`In Progress`, `Waiting for Student`, `Resolved`), resolution summaries, and faculty reassignment.
- **Project Mentorship:** Review team milestones, set completion percentage, and record guide feedback.
- **Announcements:** Broadcast institutional notices with targeted audience selection (All, Students Only, Faculty Only).
- **Reports & Data Export:** Official CSV exports for class attendance registers, marks sheets, and at-risk students.
- **AI Analytics & Class Monitoring:** Class-level risk diagnosis and faculty natural-language analytical assistant.
- **Audit Logs:** Immutable audit trail recording user, action, entity, details, IP address, and timestamp.

---

## 3. Demo Credentials (Ready to Use)

All demo accounts are seeded with realistic sample data labeled as **DEMO**:

| Role | Username | Password | Full Name / Description | Academic Profile |
| :--- | :--- | :--- | :--- | :--- |
| **Student (Featured)** | `student` | `Student@123` | Aarav Patel (DEMO) | Sem 5 CE (Div A), 88.5% Att, **On Track** |
| **Student (Attendance Shortage)** | `aditi` | `Student@123` | Aditi Sharma (DEMO) | Sem 5 CE (Div A), 74.6% Att, **Needs Attention** |
| **Student (High Risk)** | `rahul` | `Student@123` | Rahul Verma (DEMO) | Sem 5 CE (Div A), 62.4% Att, **Support Recommended** |
| **Faculty / Admin (Primary)** | `teacher` | `Teacher@123` | Prof. Project Teacher (DEMO) | CE Faculty, DBMS & Web Tech Lab |
| **Faculty (HOD)** | `dr_sharma` | `Teacher@123` | Dr. Rajesh Sharma (DEMO) | HOD Computer Engineering |
| **Faculty (AI/ML)** | `prof_patel` | `Teacher@123` | Prof. Sneha Patel (DEMO) | CE Faculty, Machine Learning & AI |

*(30+ additional student accounts are available in the system, e.g., `ananya`, `rohit`, `tanvi`, `vikram`, `priyanka` with password `Student@123`).*

---

## 4. Technology Stack
- **Backend:** Python 3.10+ with Flask 3.0+
- **Database:** MySQL Server 8.0 (InnoDB relational schema with foreign keys and unique constraints)
- **Machine Learning:** `scikit-learn` (Random Forest Regressor), `pandas`, `numpy`, `joblib`
- **Frontend:** Jinja2 templates, modern responsive CSS with CSS variables, light/dark mode support, Chart.js 4 for data visualization.

---

## 5. How to Run the Project

### Step 1: Ensure MySQL is Running
Make sure your local MySQL Server is listening on port 3306.

### Step 2: Database Migration & Schema Setup
Run the migration script to create all relational tables:
```bash
python migrate_db.py
```

### Step 3: Seed Realistic Demo Data
Populate the database with fictional college departments, subjects, teachers, 30+ students, 3 months of attendance, practicals, assessments, projects, and timetables:
```bash
python seed_demo_data.py
```

### Step 4: Verify the ML Model
Train the scikit-learn Random Forest model (if not already trained):
```bash
python train_model.py
```

### Step 5: Start the Web Server
Launch the Flask development server:
```bash
python app.py
```
Open your browser at: **`http://127.0.0.1:5000`**

### Step 6: Run Automated Tests
Execute the verification test suite covering role-based security, calculation accuracy, AI fallback, and ML pipelines:
```bash
python test_suite.py
```

---

## 6. AI Integration & Environment Variables

The system features an autonomous, rule-based AI analytical engine that operates deterministically without requiring an external paid API key:
- **Rule Engine & Fallback:** Analyzes authenticated MySQL records to generate actionable student study priorities, detect attendance recovery needs, and answer natural-language queries.
- **External AI Integration (Optional):** If an external LLM key is configured in the environment (`OPENAI_API_KEY` or `GEMINI_API_KEY`), the platform can enhance responses using the server-side environment variable. Secrets are never exposed to the frontend.

Configurable Environment Variables:
```powershell
$env:DB_HOST="localhost"
$env:DB_USER="root"
$env:DB_PASSWORD=""
$env:DB_NAME="student_performance"
$env:FLASK_SECRET_KEY="your-secret-key"
```

---

## 7. Student-Faculty Messaging & Query Resolution System

### Lifecycle & Status Flow
- **`Open`:** Query submitted by student and auto-assigned to the subject professor.
- **`In Progress`:** Faculty member has opened the query or responded.
- **`Waiting for Student`:** Faculty requested clarification or supporting documents.
- **`Resolved`:** Faculty provided resolution summary note.
- **`Unassigned`:** Subject mapping missing; routed to department admin.

### Key Endpoints
- `GET /student/queries` — Student query queue, filters, and unread badges.
- `GET /student/queries/new` & `POST /student/queries/create` — Raise doubt with automatic faculty mapping.
- `GET /teacher/queries` — Faculty query queue and student doubt resolution roster.
- `GET /queries/<reference_code>` — Shared, unified real-time conversation stream.
- `POST /queries/<reference_code>/messages` — Send follow-up or reply.
- `POST /queries/<reference_code>/status` — Update query status.
- `POST /queries/<reference_code>/resolve` — Mark resolved with summary note.
- `POST /queries/<reference_code>/reopen` — Controlled reopening by student or faculty.
- `POST /queries/<reference_code>/reassign` — Administrative faculty reassignment.

---

## 8. Modified & Newly Created Files

- [`migrate_db.py`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/migrate_db.py) — Database schema migration script creating 20+ relational tables.
- [`seed_demo_data.py`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/seed_demo_data.py) — Seed script generating 30+ students, 6 teachers, 3 months attendance, assessments, practicals, projects, and schedules.
- [`ai_service.py`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/ai_service.py) — Academic risk diagnostic engine, attendance recovery calculator, and natural language assistant.
- [`app.py`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/app.py) — Complete backend routing, role-based access control, CSV exports, audit logging, and preserved legacy compatibility.
- [`test_suite.py`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/test_suite.py) — Unit and integration tests for RBAC, formulas, and AI queries.
- [`static/style.css`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/static/style.css) — Modern UI styles, light/dark theme tokens, responsive sidebar, stat cards, chat UI.
- [`templates/base.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/base.html) — Unified master layout with role-based navigation and notification alerts.
- [`templates/login.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/login.html) — Redesigned institutional login & registration page with demo credentials.
- [`templates/dashboard.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/dashboard.html) — Role-adaptive dashboard for students and faculty.
- [`templates/attendance.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/attendance.html) — Student attendance tracking, recovery plans, and correction requests.
- [`templates/marks.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/marks.html) — Student published marks and examination results.
- [`templates/practicals.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/practicals.html) — Student practical laboratory experiments and viva scores.
- [`templates/assignments.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/assignments.html) — Student coursework tracking and submission portal.
- [`templates/projects.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/projects.html) — Student capstone project milestones and skill portfolio.
- [`templates/timetable.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/timetable.html) — Weekly class and laboratory schedule grid.
- [`templates/calendar.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/calendar.html) — Central academic calendar, deadlines, and notices.
- [`templates/ai_insights.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/ai_insights.html) — AI academic diagnostic and student natural language chat.
- [`templates/notifications.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/notifications.html) — In-app notification center.
- [`templates/student/queries.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/student/queries.html) — Student query list, filters, stats, and conversation links.
- [`templates/student/new_query.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/student/new_query.html) — New query submission form with automatic faculty routing hint.
- [`templates/teacher/queries.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/teacher/queries.html) — Faculty student queries management queue.
- [`templates/queries/conversation.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/queries/conversation.html) — Shared real-time two-way conversation view for student and faculty.
- [`templates/profile.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/profile.html) — User profile and password management.
- [`templates/teacher/*.html`](file:///d:/yash/student-performance-dashboard-2/student-performance-dashboard/templates/teacher) — Management suite for student registry, attendance entry, assessments grading, practical evaluations, coursework grading, projects, announcements, reports, and audit logs.
