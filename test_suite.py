import unittest
from datetime import datetime
from app import app, connect, one, all_rows, run, predict, find_assigned_faculty, generate_query_reference_code
from ai_service import get_student_risk_assessment, get_student_ai_insights, handle_natural_language_query

class TestScholarPulsePlatform(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_unauthenticated_access_redirects(self):
        """Verify unauthenticated requests redirect to login."""
        res = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])

        res2 = self.client.get('/teacher/students', follow_redirects=False)
        self.assertEqual(res2.status_code, 302)
        self.assertIn('/login', res2.headers['Location'])

    def test_student_cannot_access_teacher_endpoints(self):
        """Security: Verify student cannot access administrative or teacher routes."""
        s = one("SELECT id, full_name FROM users WHERE username='student'")
        with self.client.session_transaction() as sess:
            sess['user_id'] = s['id']
            sess['name'] = s['full_name']
            sess['role'] = 'student'

        res = self.client.get('/teacher/students', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard', res.headers['Location'])

        res_att = self.client.get('/teacher/attendance', follow_redirects=False)
        self.assertEqual(res_att.status_code, 302)

        res_ass = self.client.get('/teacher/assessments', follow_redirects=False)
        self.assertEqual(res_ass.status_code, 302)

    def test_teacher_can_access_management_endpoints(self):
        """Verify teacher can access management modules."""
        t = one("SELECT id, full_name FROM users WHERE username='teacher'")
        with self.client.session_transaction() as sess:
            sess['user_id'] = t['id']
            sess['name'] = t['full_name']
            sess['role'] = 'teacher'

        res = self.client.get('/teacher/students')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Student 360', res.data)

        res_att = self.client.get('/teacher/attendance')
        self.assertEqual(res_att.status_code, 200)
        self.assertIn(b'Attendance Operations', res_att.data)

    def test_rule_based_risk_diagnostic(self):
        """Verify deterministic calculation of academic risk statuses."""
        conn = connect()
        cur = conn.cursor(dictionary=True)
        try:
            s2 = one("SELECT id FROM users WHERE username='student'")
            if s2:
                risk_good = get_student_risk_assessment(cur, s2["id"])
                self.assertIn(risk_good["status"], ["On Track", "Needs Attention"])

            s_rahul = one("SELECT id FROM users WHERE username='rahul'")
            if s_rahul:
                risk_rahul = get_student_risk_assessment(cur, s_rahul["id"])
                self.assertIn(risk_rahul["status"], ["Needs Attention", "Support Recommended"])
                self.assertGreater(len(risk_rahul["reasons"]), 0)
        finally:
            cur.close()
            conn.close()

    def test_natural_language_ai_query_fallback(self):
        """Verify AI natural language engine works without external API key."""
        conn = connect()
        cur = conn.cursor(dictionary=True)
        try:
            s_u = one("SELECT id FROM users WHERE username='student'")
            if s_u:
                ans = handle_natural_language_query(cur, s_u["id"], "student", "Which subject needs the most improvement?")
                self.assertIsInstance(ans, str)
                self.assertTrue(len(ans) > 10)

                att_ans = handle_natural_language_query(cur, s_u["id"], "student", "How has my attendance changed this month?")
                self.assertIn("attendance", att_ans.lower())

            t_u = one("SELECT id FROM users WHERE username='teacher'")
            if t_u:
                t_ans = handle_natural_language_query(cur, t_u["id"], "teacher", "Show students below 75% attendance")
                self.assertIn("attendance", t_ans.lower())
        finally:
            cur.close()
            conn.close()

    def test_ml_score_prediction_pipeline(self):
        """Verify the trained scikit-learn model outputs valid predictions."""
        sample_features = {
            "math_marks": 85.0,
            "science_marks": 80.0,
            "english_marks": 75.0,
            "attendance": 88.0,
            "study_hours": 4.0,
            "previous_score": 82.0
        }
        pred = predict(sample_features)
        self.assertIsNotNone(pred)
        self.assertGreaterEqual(pred, 0)
        self.assertLessEqual(pred, 100)

    # -------------------------------------------------------------
    # Query & Two-Way Messaging Tests
    # -------------------------------------------------------------

    def test_student_query_creation_and_auto_assignment(self):
        """Test: Student can create query, which is automatically assigned to subject faculty."""
        s = one("SELECT id, full_name FROM users WHERE username='student'")
        sub = one("SELECT id FROM subjects WHERE code='CS501'")

        with self.client.session_transaction() as sess:
            sess['user_id'] = s['id']
            sess['name'] = s['full_name']
            sess['role'] = 'student'

        res = self.client.post('/student/queries/create', data={
            'subject_id': sub['id'],
            'category': 'Academic',
            'title': 'Test Query for DBMS Assignment',
            'description': 'This is a test question regarding relational schema normalization rules.',
            'attachment_name': 'test_schema.png'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Test Query for DBMS Assignment', res.data)

        # Verify record in database
        q_row = one("SELECT * FROM student_queries WHERE title='Test Query for DBMS Assignment'")
        self.assertIsNotNone(q_row)
        self.assertTrue(q_row['reference_code'].startswith('SP-'))
        # Faculty assigned for CS501 should be Teacher 1
        teacher = one("SELECT id FROM users WHERE username='teacher'")
        self.assertEqual(q_row['assigned_faculty_id'], teacher['id'])
        self.assertEqual(q_row['status'], 'Open')

        # Verify message #1 was created
        msg = one("SELECT * FROM query_messages WHERE query_id=%s ORDER BY id ASC", (q_row['id'],))
        self.assertIsNotNone(msg)
        self.assertEqual(msg['sender_id'], s['id'])
        self.assertIn('relational schema', msg['message_text'])

    def test_unauthorized_query_access_blocked(self):
        """Security: Verify student cannot view or message another student's query (IDOR prevention)."""
        aditi = one("SELECT id, full_name FROM users WHERE username='aditi'")
        # SP-1001 belongs to student 'student', not 'aditi'
        with self.client.session_transaction() as sess:
            sess['user_id'] = aditi['id']
            sess['name'] = aditi['full_name']
            sess['role'] = 'student'

        res = self.client.get('/queries/SP-1001', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/student/queries', res.headers['Location'])

        # Attempt to post a message to SP-1001
        res_post = self.client.post('/queries/SP-1001/messages', data={'message_text': 'Hacking query'}, follow_redirects=False)
        self.assertEqual(res_post.status_code, 302)

    def test_faculty_reply_and_shared_conversation(self):
        """Test: Faculty replies to query, status updates to In Progress, student sees reply."""
        teacher = one("SELECT id, full_name FROM users WHERE username='teacher'")
        student = one("SELECT id, full_name FROM users WHERE username='student'")

        # Post reply as teacher to SP-1001
        with self.client.session_transaction() as sess:
            sess['user_id'] = teacher['id']
            sess['name'] = teacher['full_name']
            sess['role'] = 'teacher'

        reply_text = 'Automated unit test faculty response: Refer to Chapter 4 of the textbook.'
        res = self.client.post('/queries/SP-1001/messages', data={
            'message_text': reply_text,
            'status_update': 'In Progress'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Automated unit test faculty response', res.data)

        # Verify query status in database
        q_row = one("SELECT status FROM student_queries WHERE reference_code='SP-1001'")
        self.assertEqual(q_row['status'], 'In Progress')

        # Log in as the student and verify the student views the exact same message
        with self.client.session_transaction() as sess:
            sess['user_id'] = student['id']
            sess['name'] = student['full_name']
            sess['role'] = 'student'

        res_student = self.client.get('/queries/SP-1001')
        self.assertEqual(res_student.status_code, 200)
        self.assertIn(b'Automated unit test faculty response', res_student.data)

    def test_query_resolve_and_reopen_lifecycle(self):
        """Test: Faculty resolves query with note; student reopens it."""
        teacher = one("SELECT id, full_name FROM users WHERE username='teacher'")
        student = one("SELECT id, full_name FROM users WHERE username='student'")

        # Faculty resolves SP-1001
        with self.client.session_transaction() as sess:
            sess['user_id'] = teacher['id']
            sess['name'] = teacher['full_name']
            sess['role'] = 'teacher'

        res_resolve = self.client.post('/queries/SP-1001/resolve', data={
            'resolution_note': 'Concept explained in class and verified.'
        }, follow_redirects=True)
        self.assertEqual(res_resolve.status_code, 200)

        q_after_resolve = one("SELECT status, resolution_note FROM student_queries WHERE reference_code='SP-1001'")
        self.assertEqual(q_after_resolve['status'], 'Resolved')
        self.assertEqual(q_after_resolve['resolution_note'], 'Concept explained in class and verified.')

        # Student reopens query
        with self.client.session_transaction() as sess:
            sess['user_id'] = student['id']
            sess['name'] = student['full_name']
            sess['role'] = 'student'

        res_reopen = self.client.post('/queries/SP-1001/reopen', follow_redirects=True)
        self.assertEqual(res_reopen.status_code, 200)

        q_after_reopen = one("SELECT status FROM student_queries WHERE reference_code='SP-1001'")
        self.assertEqual(q_after_reopen['status'], 'In Progress')

if __name__ == '__main__':
    unittest.main()
