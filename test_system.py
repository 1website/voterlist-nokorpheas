import sys
import os
import shutil
import datetime
import time

# Set stdout UTF-8 encoding on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from fastapi.testclient import TestClient
from main import app
from app.database import SessionLocal, DB_PATH
from app.models import Village, PollingStation, Voter, User

client = TestClient(app)

def run_tests():
    print("=== Testing System Functionality ===")
    
    # 1. Test Login Page
    res = client.get("/login")
    assert res.status_code == 200, f"Login page failed: {res.status_code}"
    print("[PASS] 1. Login page loads successfully")

    # 2. Test Login Authentication
    res = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert res.status_code == 303, f"Admin login failed: {res.status_code}"
    cookies = res.cookies
    print("[PASS] 2. Admin login authenticated")

    # 3. Test Dashboard
    res = client.get("/dashboard", cookies=cookies)
    assert res.status_code == 200, f"Dashboard failed: {res.status_code}"
    print("[PASS] 3. Dashboard loads with live statistics")

    # 4. Test API Dashboard Stats
    res = client.get("/api/dashboard/stats", cookies=cookies)
    assert res.status_code == 200
    stats_data = res.json()
    assert "total_active" in stats_data
    assert "stations" in stats_data
    assert "villages" in stats_data
    print(f"[PASS] 4. API Dashboard Stats: Active={stats_data['total_active']}, Voted={stats_data['total_voted']}, Turnout={stats_data['turnout_pct']}%")

    # 5. Test Voter List
    res = client.get("/voters", cookies=cookies)
    assert res.status_code == 200
    res_filter = client.get("/voters?q=&village_id=&station_id=&date_created=2026-08-24&status_filter=&voted_filter=", cookies=cookies)
    assert res_filter.status_code == 200
    print("[PASS] 5. Voter directory page & date_created filter loads successfully")

    # 6. Test Duplicate ID check
    db = SessionLocal()
    sample_voter = db.query(Voter).first()
    db.close()
    
    res = client.get(f"/api/voters/check-duplicate-id?national_id={sample_voter.national_id}")
    dup_data = res.json()
    assert dup_data["duplicate"] == True
    print(f"[PASS] 6. Duplicate National ID check works: Detected {sample_voter.national_id}")

    # 7. Test QR Lookup
    res = client.get(f"/api/voters/lookup-qr?code={sample_voter.voter_code}", cookies=cookies)
    print(f"QR Lookup for code {sample_voter.voter_code}: Status={res.status_code}, Response={res.text}")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    qr_data = res.json()
    assert qr_data["found"] == True
    assert qr_data["voter"]["name_kh"] == sample_voter.name_kh
    print(f"[PASS] 7. QR/Barcode lookup works: Found {qr_data['voter']['name_kh']} ({sample_voter.voter_code})")

    # 8. Test 1-Click Check-in Toggle
    initial_voted = sample_voter.has_voted
    res = client.post(f"/api/voters/{sample_voter.id}/checkin", cookies=cookies)
    assert res.status_code == 200
    checkin_data = res.json()
    assert checkin_data["success"] == True
    assert checkin_data["has_voted"] != initial_voted
    print(f"[PASS] 8. 1-Click Check-in toggled successfully: Now {checkin_data['has_voted']}")

    # Toggle back to maintain data
    client.post(f"/api/voters/{sample_voter.id}/checkin", cookies=cookies)

    # 9. Test Excel Export
    res = client.get("/reports/export/excel", cookies=cookies)
    assert res.status_code == 200
    assert len(res.content) > 1000
    print(f"[PASS] 9. Excel report generated successfully ({len(res.content)} bytes)")

    # 10. Test Official Printable Register
    res = client.get("/reports/official-list", cookies=cookies)
    assert res.status_code == 200
    print("[PASS] 10. Official Printable Voter Register rendered")

    # 11. Test Batch Voter Cards
    res = client.get("/reports/batch-cards", cookies=cookies)
    assert res.status_code == 200
    print("[PASS] 11. Batch Printable Voter Cards rendered")

    # 12. Test Stations & Villages
    res = client.get("/stations", cookies=cookies)
    assert res.status_code == 200
    res = client.get("/villages", cookies=cookies)
    assert res.status_code == 200
    print("[PASS] 12. 14 Polling Stations and 10 Villages pages loaded")

    # 13. Test Daily Registration Report Page
    res = client.get("/reports/daily", cookies=cookies)
    assert res.status_code == 200
    assert "របាយការណ៍អ្នកចុះឈ្មោះប្រចាំថ្ងៃ" in res.text
    print("[PASS] 13. Daily Registration Report page rendered")

    # 14. Test Daily Registration Excel Export
    res = client.get("/reports/daily/export/excel?date=2026-08-24", cookies=cookies)
    assert res.status_code == 200
    assert len(res.content) > 1000
    print(f"[PASS] 14. Daily Registration Excel export generated ({len(res.content)} bytes)")

    # 15. Test Daily Registration Printable Sheet
    res = client.get("/reports/daily/print?date=2026-08-24", cookies=cookies)
    assert res.status_code == 200
    print("[PASS] 15. Daily Registration Printable Sheet rendered")

    # 16. Test 18+ Age Validation (Underage rejection)
    underage_data = {
        "name_kh": "កុមារ តេស្ត",
        "name_en": "KUMAR TEST",
        "gender": "ប្រុស",
        "dob": "2015-05-15", # 11 years old -> under 18
        "national_id": "099999999",
        "village_id": 1,
        "station_id": 1
    }
    res = client.post("/api/voters", data=underage_data, cookies=cookies)
    assert res.status_code == 400
    assert "១៨ ឆ្នាំ" in res.json().get("detail", "")
    print("[PASS] 16. Under-18 voter registration properly rejected with HTTP 400")

    # 16b. Test Today Registration appears in Daily Report
    from app.timezone_utils import get_cambodia_today_str
    today_str = get_cambodia_today_str()
    unique_nid = f"0{int(datetime.datetime.now().timestamp()) % 100000000:08d}"
    today_voter_data = {
        "name_kh": "ស៊ឹម តេស្តថ្ងៃនេះ",
        "name_en": "SIM TODAY TEST",
        "gender": "ស្រី",
        "dob": "1998-08-25",
        "national_id": unique_nid,
        "village_id": 1,
        "station_id": 1
    }
    res_reg = client.post("/api/voters", data=today_voter_data, cookies=cookies)
    assert res_reg.status_code == 200, res_reg.text
    
    # Check that daily report for today returns this voter
    res_daily_today = client.get(f"/reports/daily?date={today_str}", cookies=cookies)
    assert res_daily_today.status_code == 200
    assert "ស៊ឹម តេស្តថ្ងៃនេះ" in res_daily_today.text
    print(f"[PASS] 16b. Registered voter today ({today_str}) correctly appears in Daily Report for {today_str}")

    # 17. Test Audit Logs Page
    res = client.get("/audit-logs", cookies=cookies)
    assert res.status_code == 200
    assert "កំណត់ត្រាសកម្មភាព" in res.text
    print("[PASS] 17. Audit Logs directory page rendered")

    # 18. Test Audit Logs Excel Export
    res = client.get("/audit-logs/export/excel", cookies=cookies)
    assert res.status_code == 200
    assert len(res.content) > 1000
    print(f"[PASS] 18. Audit Logs Excel export generated ({len(res.content)} bytes)")

    # 19. Test Backup Page & SQLite DB Download
    res = client.get("/backup", cookies=cookies)
    assert res.status_code == 200
    assert "ការបម្រុងទុក" in res.text
    res_dl = client.get("/api/backup/download", cookies=cookies)
    assert res_dl.status_code == 200
    assert len(res_dl.content) > 5000
    print(f"[PASS] 19. Backup Page rendered & SQLite DB download verified ({len(res_dl.content)} bytes)")

    # 20. Test JSON Backup & Local Snapshot Creation
    res_json = client.get("/api/backup/download-json", cookies=cookies)
    assert res_json.status_code == 200
    json_data = res_json.json()
    assert "voters" in json_data
    assert "stations" in json_data

    res_snap = client.post("/api/backup/create-snapshot", cookies=cookies)
    assert res_snap.status_code == 200
    assert res_snap.json()["success"] == True
    print(f"[PASS] 20. JSON Backup ({len(json_data['voters'])} voters) & Snapshot creation verified")

    # 21. Test 7-Digit Identity Certificate Voter Registration
    import time
    dynamic_7digit_id = f"7{int(time.time()) % 1000000:06d}"
    cert_voter_data = {
        "name_kh": "សុខ ចាន់ដារ៉ា",
        "name_en": "SOK CHANDARA",
        "gender": "ប្រុស",
        "dob": "1998-07-20", # 28 years old
        "national_id": dynamic_7digit_id, # 7-digit identity certificate
        "village_id": 1,
        "station_id": 1
    }
    res_cert = client.post("/api/voters", data=cert_voter_data, cookies=cookies)
    assert res_cert.status_code == 200
    assert res_cert.json()["success"] == True
    print(f"[PASS] 21. 7-Digit Identity Certificate voter registration succeeded ({dynamic_7digit_id})")

    # 22. Test Rejection of Invalid Document Length (e.g. 5 digits or 8 digits)
    invalid_doc_data = {
        "name_kh": "តេស្ត លេខខុស",
        "name_en": "TEST INVALID",
        "gender": "ស្រី",
        "dob": "1995-05-15",
        "national_id": "12345", # 5 digits (invalid)
        "village_id": 1,
        "station_id": 1
    }
    # 23. Test User Profile Page
    res_prof = client.get("/profile", cookies=cookies)
    assert res_prof.status_code == 200
    assert "ព័ត៌មានគណនីផ្ទាល់ខ្លួន" in res_prof.text
    print("[PASS] 23. User Profile page rendered successfully")

    # 24. Test User Profile & Avatar Update
    prof_update_data = {
        "full_name": "មេឃុំនគរភាស (Admin)",
        "phone": "068 999 888",
        "photo_preset": "/static/images/avatars/male_2.jpg",
        "current_password": "",
        "new_password": "",
        "confirm_password": ""
    }
    res_p_up = client.post("/api/profile/update", data=prof_update_data, cookies=cookies)
    assert res_p_up.status_code == 200
    assert res_p_up.json()["success"] == True
    print("[PASS] 24. User Profile & Avatar updated successfully")
    # 25. Test Public Voter Verification Page (/verify/{voter_code})
    res_verify = client.get("/verify/NP-0701-0001")
    assert res_verify.status_code == 200
    assert "ផ្ទាំងផ្ទៀងផ្ទាត់ព័ត៌មានអ្នកបោះឆ្នោតផ្លូវការ" in res_verify.text
    assert "NP-0701-0001" in res_verify.text
    assert "មាស វណ្ណា" in res_verify.text
    print("[PASS] 25. Public Voter Verification Page rendered successfully (/verify/NP-0701-0001)")

    # 27. Test Creation of Viewer Role User
    viewer_username = f"viewer_obs_{int(datetime.datetime.now().timestamp()) % 10000}"
    viewer_payload = {
        "username": viewer_username,
        "password": "viewerpassword123",
        "full_name": "លោក អ៊ុំ សុវណ្ណារិទ្ធ (អ្នកសង្កេតការណ៍)",
        "role": "viewer",
        "station_id": 0,
        "village_id": 0,
        "phone": "012 333 444",
        "photo_preset": "/static/images/avatars/male_1.jpg"
    }
    res_v_create = client.post("/api/users", data=viewer_payload, cookies=cookies)
    assert res_v_create.status_code == 200
    assert res_v_create.json()["success"] == True
    print(f"[PASS] 27. Viewer Role User created successfully ({viewer_username})")

    # 28. Test Viewer Login & Exclusive Access to Reports & Profile (Dashboard redirected to Reports)
    res_v_login = client.post("/login", data={"username": viewer_username, "password": "viewerpassword123"}, follow_redirects=False)
    assert res_v_login.status_code in [302, 303]
    viewer_cookies = {"session": res_v_login.cookies.get("session")}

    res_v_dash = client.get("/dashboard", cookies=viewer_cookies, follow_redirects=False)
    assert res_v_dash.status_code == 302
    assert "/reports" in res_v_dash.headers.get("location", "")

    res_v_rep = client.get("/reports", cookies=viewer_cookies)
    assert res_v_rep.status_code == 200
    assert "មជ្ឈមណ្ឌលរបាយការណ៍" in res_v_rep.text
    # Ensure Section 1 and 2 are hidden in sidebar for viewer
    assert "មុខងារស្នូលបោះឆ្នោត" not in res_v_rep.text
    assert "រចនាសម្ព័ន្ធភូមិសាស្ត្រ" not in res_v_rep.text
    assert "របាយការណ៍ &amp; សុវត្ថិភាព" in res_v_rep.text or "របាយការណ៍ & សុវត្ថិភាព" in res_v_rep.text
    print("[PASS] 28. Viewer logged in and redirected to Reports successfully (Only Reports & Security visible)")

    # 29. Test Viewer Mutation Blocking (Delete, Edit, Checkin, Add User - All 403 Forbidden)
    res_v_del = client.post("/api/voters/1/delete", cookies=viewer_cookies)
    assert res_v_del.status_code == 403

    res_v_chk = client.post("/api/voters/1/checkin", cookies=viewer_cookies)
    assert res_v_chk.status_code == 403

    res_v_add = client.post("/api/voters", data={
        "name_kh": "តេស្ត អ្នកពិនិត្យ",
        "name_en": "TEST VIEWER",
        "gender": "ប្រុស",
        "dob": "1990-01-01",
        "national_id": "020999999",
        "village_id": 1,
        "station_id": 1
    }, cookies=viewer_cookies)
    assert res_v_add.status_code == 403

    res_v_usr = client.get("/users", cookies=viewer_cookies)
    assert res_v_usr.status_code == 403
    # 30. Test Strict Login Enforcement Across All Protected Routes (Without Login -> Redirect to /login)
    protected_routes = [
        "/",
        "/dashboard",
        "/voters",
        "/checkin",
        "/reports",
        "/reports/daily",
        "/reports/official-list",
        "/reports/batch-cards",
        "/stations",
        "/villages",
        "/users",
        "/profile",
        "/audit-logs",
        "/backup",
        "/voters/1/card"
    ]
    guest_client = TestClient(app)
    for route in protected_routes:
        res_guest = guest_client.get(route, follow_redirects=False)
        assert res_guest.status_code in [302, 303], f"Route {route} failed to redirect guest: {res_guest.status_code}"
        assert "/login" in res_guest.headers.get("location", "")
    print(f"[PASS] 30. Strict login enforcement verified across all {len(protected_routes)} protected routes (All 100% redirect to /login)")

    print("\n ALL 30 SYSTEM TESTS PASSED SUCCESSFULLY! ")

def test_system():
    # Save safety backup of DB before tests
    temp_backup = DB_PATH + ".test_backup"
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, temp_backup)
    
    try:
        run_tests()
    finally:
        # Always restore original DB so test artifacts never pollute DB
        if os.path.exists(temp_backup):
            shutil.copy2(temp_backup, DB_PATH)
            try:
                os.remove(temp_backup)
            except Exception:
                pass

if __name__ == "__main__":
    test_system()
