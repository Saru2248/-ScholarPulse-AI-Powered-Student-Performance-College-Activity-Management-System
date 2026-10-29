import os
import json
from datetime import datetime

def get_student_risk_assessment(cur, student_id):
    """
    Evaluates rule-based academic risk indicators with transparent reasons.
    Categories: On Track, Needs Attention, Support Recommended.
    """
    reasons = []
    severity_score = 0  # 0: On Track, 1-2: Needs Attention, 3+: Support Recommended

    # 1. Attendance Check
    cur.execute("""
        SELECT COUNT(*) as total_sessions,
               SUM(CASE WHEN status IN ('Present','Late') THEN 1 ELSE 0 END) as attended
        FROM attendance_records
        WHERE student_id = %s
    """, (student_id,))
    att = cur.fetchone()
    total_sessions = att["total_sessions"] if att and att["total_sessions"] else 0
    attended = att["attended"] if att and att["attended"] else 0
    att_pct = round((attended / total_sessions * 100), 1) if total_sessions > 0 else 100.0

    if att_pct < 65:
        severity_score += 2
        reasons.append(f"Critical attendance shortage: {att_pct}% (Mandatory minimum is 75%).")
    elif att_pct < 75:
        severity_score += 1
        reasons.append(f"Low attendance: {att_pct}% is below the 75% examination eligibility threshold.")

    # 2. Assessment Marks Check (Published only)
    cur.execute("""
        SELECT ar.marks_obtained, a.max_marks, s.name as subject_name
        FROM assessment_results ar
        JOIN assessments a ON a.id = ar.assessment_id
        JOIN subjects s ON s.id = a.subject_id
        WHERE ar.student_id = %s AND a.is_published = 1
        ORDER BY a.exam_date DESC
    """, (student_id,))
    results = cur.fetchall()
    if results:
        low_scores = [r for r in results if (float(r["marks_obtained"]) / float(r["max_marks"])) < 0.50]
        if len(low_scores) >= 2:
            severity_score += 2
            reasons.append(f"Scored below 50% in {len(low_scores)} published assessments ({low_scores[0]['subject_name']}).")
        elif len(low_scores) == 1:
            severity_score += 1
            reasons.append(f"Needs improvement in {low_scores[0]['subject_name']} (< 50% score).")

    # 3. Pending Practicals Check
    cur.execute("""
        SELECT COUNT(*) as pending_prac
        FROM practical_submissions
        WHERE student_id = %s AND status IN ('Needs Resubmission', 'Not Started')
    """, (student_id,))
    p_row = cur.fetchone()
    pending_prac = p_row["pending_prac"] if p_row else 0
    if pending_prac >= 2:
        severity_score += 1
        reasons.append(f"{pending_prac} practical experiments need immediate completion or resubmission.")

    # 4. Pending / Overdue Assignments Check
    cur.execute("""
        SELECT COUNT(*) as pending_count
        FROM assignments a
        JOIN student_profiles sp ON sp.student_id = %s
        JOIN subjects s ON s.id = a.subject_id AND s.semester = sp.semester
        LEFT JOIN assignment_submissions sub ON sub.assignment_id = a.id AND sub.student_id = %s
        WHERE sub.id IS NULL AND a.due_date < NOW()
    """, (student_id, student_id))
    a_row = cur.fetchone()
    overdue_assign = a_row["pending_count"] if a_row else 0
    if overdue_assign >= 1:
        severity_score += 1
        reasons.append(f"{overdue_assign} assignment(s) are overdue and unsubmitted.")

    if severity_score >= 3:
        status = "Support Recommended"
        badge_class = "badge-danger"
    elif severity_score >= 1:
        status = "Needs Attention"
        badge_class = "badge-warning"
    else:
        status = "On Track"
        badge_class = "badge-success"
        reasons.append("Academic progress, attendance, and coursework submissions satisfy college benchmarks.")

    return {
        "status": status,
        "badge_class": badge_class,
        "severity_score": severity_score,
        "reasons": reasons,
        "attendance_pct": att_pct,
        "total_sessions": total_sessions,
        "attended_sessions": attended
    }

def get_student_ai_insights(cur, student_id):
    """
    Generates actionable, personalized academic insights and study advice for a student.
    Uses authorized database records only.
    """
    risk = get_student_risk_assessment(cur, student_id)

    # Subject-wise marks summary
    cur.execute("""
        SELECT s.name as subject, s.code,
               AVG(ar.marks_obtained / a.max_marks * 100) as avg_pct
        FROM assessment_results ar
        JOIN assessments a ON a.id = ar.assessment_id
        JOIN subjects s ON s.id = a.subject_id
        WHERE ar.student_id = %s AND a.is_published = 1
        GROUP BY s.id, s.name, s.code
        ORDER BY avg_pct DESC
    """, (student_id,))
    sub_scores = cur.fetchall()

    strong_subjects = [s["subject"] for s in sub_scores if s["avg_pct"] and s["avg_pct"] >= 75]
    weak_subjects = [s["subject"] for s in sub_scores if s["avg_pct"] and s["avg_pct"] < 60]

    # Attendance classes needed calculation
    att_pct = risk["attendance_pct"]
    classes_needed = 0
    if att_pct < 75 and risk["total_sessions"] > 0:
        # attended + x / (total + x) >= 0.75 => x >= (0.75*total - attended) / 0.25
        classes_needed = max(0, int((0.75 * risk["total_sessions"] - risk["attended_sessions"]) / 0.25) + 1)

    # Upcoming examinations
    cur.execute("""
        SELECT a.title, a.assessment_type, a.exam_date, a.max_marks, s.name as subject_name
        FROM assessments a
        JOIN subjects s ON s.id = a.subject_id
        WHERE a.exam_date >= CURDATE()
        ORDER BY a.exam_date ASC
        LIMIT 3
    """)
    upcoming_exams = cur.fetchall()

    # Pending practicals
    cur.execute("""
        SELECT p.title, p.experiment_no, s.name as subject_name, ps.status
        FROM practical_submissions ps
        JOIN practicals p ON p.id = ps.practical_id
        JOIN subjects s ON s.id = p.subject_id
        WHERE ps.student_id = %s AND ps.status IN ('Needs Resubmission', 'Not Started', 'In Progress')
        ORDER BY p.experiment_no ASC
    """, (student_id,))
    pending_practicals = cur.fetchall()

    # Priorities & recommendations
    recommendations = []
    if classes_needed > 0:
        recommendations.append({
            "title": "Attendance Recovery Plan",
            "text": f"Attend the next {classes_needed} consecutive sessions without absence to reach the 75% statutory compliance requirement.",
            "category": "attendance"
        })

    if weak_subjects:
        recommendations.append({
            "title": f"Targeted Revision: {', '.join(weak_subjects)}",
            "text": f"Your current score average is below 60% in {', '.join(weak_subjects)}. Focus study time on key numericals and previous year questions.",
            "category": "academics"
        })

    if upcoming_exams:
        next_exam = upcoming_exams[0]
        recommendations.append({
            "title": f"Priority Exam Prep: {next_exam['title']}",
            "text": f"Scheduled for {next_exam['exam_date']} ({next_exam['subject_name']}). Review lecture notes and practice core formulas.",
            "category": "examination"
        })

    if pending_practicals:
        recommendations.append({
            "title": "Lab Submission Clearance",
            "text": f"Resolve {len(pending_practicals)} experiment(s) with 'Needs Resubmission' or 'Not Started' status before final journal sign-off.",
            "category": "practical"
        })

    if not recommendations:
        recommendations.append({
            "title": "Sustain Academic Momentum",
            "text": "Your scores and attendance meet high benchmarks. Maintain steady review habits and consider contributing to technical symposiums or coding hackathons.",
            "category": "general"
        })

    return {
        "risk": risk,
        "strong_subjects": strong_subjects,
        "weak_subjects": weak_subjects,
        "classes_needed": classes_needed,
        "upcoming_exams": upcoming_exams,
        "pending_practicals": pending_practicals,
        "recommendations": recommendations
    }

def handle_natural_language_query(cur, user_id, role, query_text):
    """
    Answers natural language queries using authenticated, permission-checked database retrievals.
    Supports queries from both students and teachers.
    Guaranteed deterministic fallback without requiring external API keys.
    """
    q = query_text.lower().strip()

    if role == "student":
        insights = get_student_ai_insights(cur, user_id)
        risk = insights["risk"]

        if any(w in q for w in ["improvement", "weak", "low", "focus"]):
            if insights["weak_subjects"]:
                return f"Based on your published assessment results, your primary focus should be on **{', '.join(insights['weak_subjects'])}**, where average performance is currently below 60%. Prioritize revision and clarify doubts with your professor."
            else:
                return "Great news! You do not currently have any subjects with critically low marks. Your lowest scoring subject is still above 60%. Continue maintaining consistent study hours."

        elif any(w in q for w in ["attendance", "shortage", "absent", "miss"]):
            att_pct = risk["attendance_pct"]
            status_txt = f"Your aggregate attendance is **{att_pct}%** ({risk['attended_sessions']} of {risk['total_sessions']} sessions attended)."
            if insights["classes_needed"] > 0:
                status_txt += f" To reach the mandatory 75% threshold, you need to attend at least **{insights['classes_needed']} additional consecutive classes**."
            else:
                status_txt += " You are currently in the safe zone above the 75% attendance threshold."
            return status_txt

        elif any(w in q for w in ["pending", "practical", "assignment", "due", "submission"]):
            prac_count = len(insights["pending_practicals"])
            cur.execute("""
                SELECT a.title, a.due_date, s.code
                FROM assignments a
                JOIN student_profiles sp ON sp.student_id = %s
                JOIN subjects s ON s.id = a.subject_id AND s.semester = sp.semester
                LEFT JOIN assignment_submissions sub ON sub.assignment_id = a.id AND sub.student_id = %s
                WHERE sub.id IS NULL
                ORDER BY a.due_date ASC
            """, (user_id, user_id))
            pending_ass = cur.fetchall()

            msg = []
            if prac_count > 0:
                msg.append(f"**{prac_count} practical experiment(s)** requiring action (e.g., {insights['pending_practicals'][0]['title']}).")
            else:
                msg.append("No pending practicals. All experiments submitted!")

            if pending_ass:
                ass_titles = ", ".join([f"{a['code']}: {a['title']}" for a in pending_ass[:2]])
                msg.append(f"**{len(pending_ass)} pending assignment(s)**: {ass_titles}.")
            else:
                msg.append("No pending assignments.")

            return "Here is your coursework status:\n- " + "\n- ".join(msg)

        elif any(w in q for w in ["exam", "test", "prioritize", "schedule"]):
            if insights["upcoming_exams"]:
                exams_str = "; ".join([f"{e['title']} ({e['subject_name']}) on {e['exam_date']}" for e in insights["upcoming_exams"]])
                return f"Your upcoming examinations include: **{exams_str}**. Review the core concepts and past unit test solutions."
            else:
                return "There are no new examinations scheduled in the immediate timetable. Use this time to organize journal files and consolidate semester notes."

        elif any(w in q for w in ["progress", "summary", "overview"]):
            return (f"**Academic Summary for this semester:**\n"
                    f"- Status: **{risk['status']}**\n"
                    f"- Overall Attendance: **{risk['attendance_pct']}%**\n"
                    f"- Strong Subjects: {', '.join(insights['strong_subjects']) if insights['strong_subjects'] else 'In progress'}\n"
                    f"- Priority Subjects: {', '.join(insights['weak_subjects']) if insights['weak_subjects'] else 'None'}\n"
                    f"- Pending Practicals: {len(insights['pending_practicals'])}\n"
                    f"Check the AI Insights tab for personalized study tips.")

        else:
            # Default helpful query guide
            return (f"I can analyze your personal academic records! Here are some sample questions you can ask me:\n"
                    f"• *Which subject needs the most improvement?*\n"
                    f"• *How has my attendance changed and what is my percentage?*\n"
                    f"• *Which assignments and practicals are pending?*\n"
                    f"• *What should I prioritize before my next examination?*\n"
                    f"• *Summarize my academic progress this semester.*")

    elif role in ("teacher", "admin"):
        if any(w in q for w in ["attendance", "shortage", "threshold", "below 75"]):
            cur.execute("""
                SELECT u.full_name, sp.enrollment_no,
                       COUNT(ar.id) as total,
                       SUM(CASE WHEN ar.status IN ('Present','Late') THEN 1 ELSE 0 END) as attended
                FROM users u
                JOIN student_profiles sp ON sp.student_id = u.id
                JOIN attendance_records ar ON ar.student_id = u.id
                GROUP BY u.id, u.full_name, sp.enrollment_no
                HAVING (attended / total * 100) < 75
                ORDER BY (attended / total) ASC
            """)
            shortage_students = cur.fetchall()
            if shortage_students:
                s_list = [f"• **{s['full_name']}** ({s['enrollment_no']}): {round(s['attended']/s['total']*100, 1)}% attendance" for s in shortage_students[:8]]
                return f"Found **{len(shortage_students)} students** below the mandatory 75% attendance threshold:\n" + "\n".join(s_list)
            return "All students in your registered classes currently meet or exceed the 75% attendance threshold!"

        elif any(w in q for w in ["lowest", "average marks", "subject marks"]):
            cur.execute("""
                SELECT s.name, s.code, AVG(ar.marks_obtained / a.max_marks * 100) as avg_pct
                FROM assessments a
                JOIN subjects s ON s.id = a.subject_id
                JOIN assessment_results ar ON ar.assessment_id = a.id
                GROUP BY s.id, s.name, s.code
                ORDER BY avg_pct ASC
            """)
            subs = cur.fetchall()
            if subs:
                lowest = subs[0]
                return f"The subject with the lowest class average is **{lowest['name']} ({lowest['code']})** with an average score of **{round(lowest['avg_pct'], 1)}%**. Consider conducting a remedial session or review lecture."
            return "No assessment results have been published yet to compute averages."

        elif any(w in q for w in ["practical", "evaluation", "pending practical"]):
            cur.execute("""
                SELECT COUNT(*) as pending_eval
                FROM practical_submissions
                WHERE status IN ('Submitted', 'Needs Resubmission')
            """)
            p = cur.fetchone()
            count = p["pending_eval"] if p else 0
            return f"There are currently **{count} practical journal submissions** awaiting evaluation or re-check across laboratory batches."

        elif any(w in q for w in ["risk", "declining", "intervention", "support"]):
            cur.execute("""
                SELECT u.id, u.full_name, sp.enrollment_no
                FROM users u
                JOIN student_profiles sp ON sp.student_id = u.id
                WHERE u.role = 'student'
            """)
            students = cur.fetchall()
            at_risk = []
            for s in students:
                ra = get_student_risk_assessment(cur, s["id"])
                if ra["status"] in ("Support Recommended", "Needs Attention"):
                    at_risk.append((s["full_name"], s["enrollment_no"], ra["status"], ra["reasons"][0] if ra["reasons"] else ""))

            if at_risk:
                lines = [f"• **{name}** ({eno}) - *{st}*: {r}" for name, eno, st, r in at_risk[:6]]
                return f"Identified **{len(at_risk)} students** who may benefit from academic mentoring:\n" + "\n".join(lines)
            return "No students currently flagged for academic intervention."

        else:
            return ("As faculty/admin, you can ask administrative analytical questions like:\n"
                    "• *Show students whose attendance is below the configured threshold*\n"
                    "• *Which subject has the lowest average marks?*\n"
                    "• *List practical evaluations still pending*\n"
                    "• *Summarize students requiring academic intervention*")

