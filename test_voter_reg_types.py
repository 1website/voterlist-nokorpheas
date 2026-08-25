from starlette.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models import User, Village, PollingStation, Voter
from app.auth import hash_password

client = TestClient(app)

def get_admin_cookies():
    response = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert response.status_code in [302, 303]
    return response.cookies

def test_voter_registration_new_legacy_transferred():
    cookies = get_admin_cookies()
    db = SessionLocal()
    
    village = db.query(Village).first()
    station = db.query(PollingStation).first()
    assert village is not None
    assert station is not None

    test_id_legacy = "881122334"
    test_id_new = "881122335"
    test_id_transferred = "881122336"

    db.query(Voter).filter(Voter.national_id.in_([test_id_legacy, test_id_new, test_id_transferred])).delete()
    db.commit()

    # 1. Create Legacy Voter
    res1 = client.post(
        "/api/voters",
        data={
            "name_kh": "ឡុង ចាស់",
            "name_en": "LONG CHAS",
            "gender": "ប្រុស",
            "dob": "1990-01-01",
            "national_id": test_id_legacy,
            "village_id": village.id,
            "station_id": station.id,
            "reg_type": "legacy",
            "reg_year": 2024,
            "reg_reason": "legacy"
        },
        cookies=cookies
    )
    assert res1.status_code == 200
    v1 = db.query(Voter).filter(Voter.national_id == test_id_legacy).first()
    assert v1 is not None
    assert v1.reg_type == "legacy"
    assert v1.reg_year == 2024
    assert v1.reg_type_badge["type"] == "legacy"
    assert "បញ្ជីចាស់" in v1.reg_type_badge["text"]

    # 2. Create New Voter
    res2 = client.post(
        "/api/voters",
        data={
            "name_kh": "ឡុង ថ្មី",
            "name_en": "LONG THMEI",
            "gender": "ស្រី",
            "dob": "2008-01-01",
            "national_id": test_id_new,
            "village_id": village.id,
            "station_id": station.id,
            "reg_type": "new",
            "reg_year": 2026,
            "reg_reason": "first_time_18"
        },
        cookies=cookies
    )
    assert res2.status_code == 200
    v2 = db.query(Voter).filter(Voter.national_id == test_id_new).first()
    assert v2 is not None
    assert v2.reg_type == "new"
    assert v2.reg_year == 2026
    assert v2.reg_type_badge["type"] == "new"
    assert "ចុះថ្មី 2026" in v2.reg_type_badge["text"]

    # 3. Create Transferred Voter
    res3 = client.post(
        "/api/voters",
        data={
            "name_kh": "ឡុង ផ្ទេរ",
            "name_en": "LONG PHTER",
            "gender": "ប្រុស",
            "dob": "1998-05-10",
            "national_id": test_id_transferred,
            "village_id": village.id,
            "station_id": station.id,
            "reg_type": "transferred",
            "reg_year": 2026,
            "reg_reason": "relocated"
        },
        cookies=cookies
    )
    assert res3.status_code == 200
    v3 = db.query(Voter).filter(Voter.national_id == test_id_transferred).first()
    assert v3 is not None
    assert v3.reg_type == "transferred"
    assert v3.reg_type_badge["type"] == "transferred"
    assert "ផ្ទេរចូល 2026" in v3.reg_type_badge["text"]

    # 4. Edit Voter to change reg_type
    res4 = client.post(
        f"/api/voters/{v1.id}/edit",
        data={
            "name_kh": "ឡុង ចាស់កែប្រែ",
            "name_en": "LONG CHAS EDIT",
            "gender": "ប្រុស",
            "dob": "1990-01-01",
            "national_id": test_id_legacy,
            "village_id": village.id,
            "station_id": station.id,
            "status": "active",
            "reg_type": "transferred",
            "reg_year": 2026,
            "reg_reason": "relocated"
        },
        cookies=cookies
    )
    assert res4.status_code == 200
    db.refresh(v1)
    assert v1.reg_type == "transferred"
    assert v1.reg_year == 2026

    # Clean up
    db.delete(v1)
    db.delete(v2)
    db.delete(v3)
    db.commit()
    db.close()

def test_voter_reg_type_filters():
    cookies = get_admin_cookies()

    res_all = client.get("/voters", cookies=cookies)
    assert res_all.status_code == 200
    assert "ប្រភេទបញ្ជី" in res_all.text

    res_legacy = client.get("/voters?reg_type_filter=legacy", cookies=cookies)
    assert res_legacy.status_code == 200

    res_new = client.get("/voters?reg_type_filter=new", cookies=cookies)
    assert res_new.status_code == 200

    res_year = client.get("/voters?reg_year_filter=2026", cookies=cookies)
    assert res_year.status_code == 200

def test_annual_summary_dashboard_page():
    cookies = get_admin_cookies()
    res = client.get("/reports/annual-summary?year=2026", cookies=cookies)
    assert res.status_code == 200
    assert "របាយការណ៍បូកសរុបអ្នកចុះឈ្មោះថ្មី & ទិន្នន័យចាស់ក្នុងបញ្ជី" in res.text
    assert "បញ្ជីចាស់ (A)" in res.text
    assert "ចុះថ្មី 2026 (B)" in res.text
    assert "ផ្ទេរចូល (C)" in res.text
    assert "លុបចេញ (D)" in res.text
    assert "បញ្ជីផ្លូវការ (A+B+C-D)" in res.text

def test_annual_summary_print_page():
    cookies = get_admin_cookies()
    res = client.get("/reports/print/annual-summary?year=2026", cookies=cookies)
    assert res.status_code == 200
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in res.text
    assert "របាយការណ៍បូកសរុបលទ្ធផលនៃការពិនិត្យបញ្ជីឈ្មោះ" in res.text
    assert "មេឃុំនគរភាស" in res.text

def test_annual_summary_excel_export():
    cookies = get_admin_cookies()
    res = client.get("/reports/export/annual-summary-excel?year=2026", cookies=cookies)
    assert res.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in res.headers.get("content-type", "")

if __name__ == "__main__":
    print("Running Voter Registration Types Tests...")
    test_voter_registration_new_legacy_transferred()
    print("✅ test_voter_registration_new_legacy_transferred passed")
    test_voter_reg_type_filters()
    print("✅ test_voter_reg_type_filters passed")
    test_annual_summary_dashboard_page()
    print("✅ test_annual_summary_dashboard_page passed")
    test_annual_summary_print_page()
    print("✅ test_annual_summary_print_page passed")
    test_annual_summary_excel_export()
    print("✅ test_annual_summary_excel_export passed")
    print("🎉 All Voter Registration Types tests passed successfully!")
