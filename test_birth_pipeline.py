import os
from starlette.testclient import TestClient
from main import app
from app.database import SessionLocal
from app.models import User, Village, PollingStation, Voter, BirthCertificate

client = TestClient(app)

def get_admin_cookies():
    # Login as admin to get session
    response = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert response.status_code in [302, 303]
    return response.cookies

def test_birth_certificates_list_page():
    cookies = get_admin_cookies()
    response = client.get("/birth-certificates", cookies=cookies)
    assert response.status_code == 200
    assert "កត់ត្រាសំបុត្រកំណើត" in response.text
    assert "សំបុត្រកំណើតសរុប" in response.text

def test_birth_certificates_filters():
    cookies = get_admin_cookies()
    # Test filter by turning_18_this_year
    res1 = client.get("/birth-certificates?eligibility=turning_18_this_year", cookies=cookies)
    assert res1.status_code == 200

    # Test filter by unregistered
    res2 = client.get("/birth-certificates?reg_status=unregistered", cookies=cookies)
    assert res2.status_code == 200

def test_youth_pipeline_dashboard():
    cookies = get_admin_cookies()
    response = client.get("/birth-certificates/youth-pipeline", cookies=cookies)
    assert response.status_code == 200
    assert "ផ្ទាំងវិភាគទិន្នន័យយុវជន" in response.text
    assert "villageYouthChart" in response.text

def test_create_and_convert_birth_certificate():
    cookies = get_admin_cookies()
    db = SessionLocal()
    
    village = db.query(Village).first()
    station = db.query(PollingStation).first()
    assert village is not None
    assert station is not None

    test_cert_no = "ស.ក-TEST-9999"
    # Clean up if existed
    db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_no).delete()
    db.commit()

    # 1. Create Birth Certificate
    res_create = client.post(
        "/birth-certificates/create",
        data={
            "certificate_no": test_cert_no,
            "book_no": "០១/២០២៦",
            "name_kh": "សុខ តេស្តយុវជន",
            "name_en": "SOK TESTYOUTH",
            "gender": "ប្រុស",
            "dob": "2008-05-20",
            "pob": "ឃុំនគរភាស",
            "father_name": "សុខ ឪពុក",
            "mother_name": "សុខ ម្តាយ",
            "address": "ក្រុមទី ១ ភូមិរមៀត",
            "village_id": village.id,
            "notes": "តេស្តប្រព័ន្ធ"
        },
        cookies=cookies,
        follow_redirects=True
    )
    assert res_create.status_code == 200

    # Check created in DB
    created = db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_no).first()
    assert created is not None
    assert created.is_turning_18_this_year is True
    assert created.is_registered_voter is False

    # 2. Convert to Voter (1-Click Promote)
    test_nid = "998877665"
    db.query(Voter).filter(Voter.national_id == test_nid).delete()
    db.commit()

    res_convert = client.post(
        f"/birth-certificates/convert-to-voter/{created.id}",
        data={
            "national_id": test_nid,
            "station_id": station.id,
            "address": "ក្រុមទី ១",
            "notes": "Convert test"
        },
        cookies=cookies,
        follow_redirects=True
    )
    assert res_convert.status_code == 200

    # Verify voter was created and linked
    db.refresh(created)
    assert created.is_registered_voter is True
    assert created.voter_id is not None

    voter = db.query(Voter).filter(Voter.id == created.voter_id).first()
    assert voter is not None
    assert voter.national_id == test_nid
    assert voter.name_kh == "សុខ តេស្តយុវជន"

    # Clean up test records
    db.delete(created)
    db.delete(voter)
    db.commit()
    db.close()

def test_export_excel():
    cookies = get_admin_cookies()
    response = client.get("/birth-certificates/export-excel", cookies=cookies)
    assert response.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in response.headers.get("content-type", "")

def test_print_eligible_view():
    cookies = get_admin_cookies()
    response = client.get("/birth-certificates/print-eligible", cookies=cookies)
    assert response.status_code == 200
    assert "បញ្ជីឈ្មោះយុវជនគ្រប់អាយុបោះឆ្នោត" in response.text
    assert "ព្រះរាជាណាចក្រកម្ពុជា" in response.text

def test_birth_certificate_attachments():
    cookies = get_admin_cookies()
    db = SessionLocal()
    village = db.query(Village).first()
    assert village is not None

    test_cert_img = "ស.ក-TEST-IMG-001"
    test_cert_pdf = "ស.ក-TEST-PDF-002"
    db.query(BirthCertificate).filter(BirthCertificate.certificate_no.in_([test_cert_img, test_cert_pdf])).delete()
    db.commit()

    # 1. Test image upload
    img_content = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00"
    res_img = client.post(
        "/birth-certificates/create",
        data={
            "certificate_no": test_cert_img,
            "book_no": "០១/២០២៦",
            "name_kh": "រូបភាព តេស្ត",
            "name_en": "IMAGE TEST",
            "gender": "ប្រុស",
            "dob": "2008-01-01",
            "village_id": village.id
        },
        files={"attachment": ("sample_cert.jpg", img_content, "image/jpeg")},
        cookies=cookies,
        follow_redirects=True
    )
    assert res_img.status_code == 200

    rec_img = db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_img).first()
    assert rec_img is not None
    assert rec_img.attachment_url is not None
    assert rec_img.is_image is True
    assert rec_img.is_pdf is False

    # 2. Test PDF upload
    pdf_content = b"%PDF-1.4 sample pdf content for testing"
    res_pdf = client.post(
        "/birth-certificates/create",
        data={
            "certificate_no": test_cert_pdf,
            "book_no": "០១/២០២៦",
            "name_kh": "ឯកសារ ភីឌីអេហ្វ",
            "name_en": "PDF TEST",
            "gender": "ស្រី",
            "dob": "2008-02-02",
            "village_id": village.id
        },
        files={"attachment": ("sample_cert.pdf", pdf_content, "application/pdf")},
        cookies=cookies,
        follow_redirects=True
    )
    assert res_pdf.status_code == 200

    rec_pdf = db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_pdf).first()
    assert rec_pdf is not None
    assert rec_pdf.attachment_url is not None
    assert rec_pdf.is_pdf is True
    assert rec_pdf.is_image is False

    # Clean up test records and uploaded files
    import os
    for rec in [rec_img, rec_pdf]:
        if rec and rec.attachment_url:
            local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", rec.attachment_url.lstrip("/"))
            if os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except Exception:
                    pass

    db.delete(rec_img)
    db.delete(rec_pdf)
    db.commit()
    db.close()

def test_birth_certificate_duplicate_check():
    cookies = get_admin_cookies()
    db = SessionLocal()
    village = db.query(Village).first()
    assert village is not None

    test_cert_dup = "ស.ក-DUP-TEST-001"
    test_book_dup = "សៀវភៅលេខ ៨៨/២០២៦"

    # Clean up before test
    db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_dup).delete()
    db.commit()

    # 1. Check duplicate API for non-existing record
    res_api_clean = client.get(
        f"/api/birth-certificates/check-duplicate?certificate_no={test_cert_dup}&book_no={test_book_dup}",
        cookies=cookies
    )
    assert res_api_clean.status_code == 200
    clean_data = res_api_clean.json()
    assert clean_data["duplicate"] is False

    # 2. Insert original record
    res_create = client.post(
        "/birth-certificates/create",
        data={
            "certificate_no": test_cert_dup,
            "book_no": test_book_dup,
            "name_kh": "ជា សុជាតិ",
            "name_en": "CHEA SOCHEAT",
            "gender": "ប្រុស",
            "dob": "2008-01-15",
            "village_id": village.id
        },
        cookies=cookies,
        follow_redirects=False
    )
    assert res_create.status_code == 302
    assert "msg=" in res_create.headers["location"]

    original = db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_dup).first()
    assert original is not None

    # 3. Check duplicate API for existing record -> should return duplicate: True and details
    res_api_dup = client.get(
        f"/api/birth-certificates/check-duplicate?certificate_no={test_cert_dup}&book_no={test_book_dup}",
        cookies=cookies
    )
    assert res_api_dup.status_code == 200
    dup_data = res_api_dup.json()
    assert dup_data["duplicate"] is True
    assert "ជា សុជាតិ" in dup_data["message"]
    assert dup_data["existing"]["name_kh"] == "ជា សុជាតិ"
    assert dup_data["existing"]["certificate_no"] == test_cert_dup

    # 4. Check duplicate API with exclude_id = original.id (edit mode) -> should return duplicate: False
    res_api_exclude = client.get(
        f"/api/birth-certificates/check-duplicate?certificate_no={test_cert_dup}&book_no={test_book_dup}&exclude_id={original.id}",
        cookies=cookies
    )
    assert res_api_exclude.status_code == 200
    assert res_api_exclude.json()["duplicate"] is False

    # 5. Try creating duplicate record -> should redirect with error message
    res_create_dup = client.post(
        "/birth-certificates/create",
        data={
            "certificate_no": test_cert_dup,
            "book_no": test_book_dup,
            "name_kh": "អ្នកថ្មី ចង់បញ្ចូលស្ទួន",
            "name_en": "NEW PERSON DUP",
            "gender": "ស្រី",
            "dob": "2008-06-20",
            "village_id": village.id
        },
        cookies=cookies,
        follow_redirects=False
    )
    assert res_create_dup.status_code == 302
    assert "error=" in res_create_dup.headers["location"]
    import urllib.parse
    decoded_loc = urllib.parse.unquote(res_create_dup.headers["location"])
    assert "ជា សុជាតិ" in decoded_loc
    assert "ទិន្នន័យស្ទួន" in decoded_loc

    # Verify no second record was created
    dup_count = db.query(BirthCertificate).filter(BirthCertificate.certificate_no == test_cert_dup).count()
    assert dup_count == 1

    # Clean up
    db.delete(original)
    db.commit()
    db.close()

if __name__ == "__main__":
    from app.database import DB_PATH
    import shutil
    temp_backup = DB_PATH + ".test_backup_birth"
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, temp_backup)
    try:
        print("Running tests manually...")
        test_birth_certificates_list_page()
        print("✅ test_birth_certificates_list_page passed")
        test_birth_certificates_filters()
        print("✅ test_birth_certificates_filters passed")
        test_youth_pipeline_dashboard()
        print("✅ test_youth_pipeline_dashboard passed")
        test_create_and_convert_birth_certificate()
        print("✅ test_create_and_convert_birth_certificate passed")
        test_birth_certificate_attachments()
        print("✅ test_birth_certificate_attachments (Image & PDF) passed")
        test_export_excel()
        print("✅ test_export_excel passed")
        test_print_eligible_view()
        print("✅ test_print_eligible_view passed")
        test_birth_certificate_duplicate_check()
        print("✅ test_birth_certificate_duplicate_check passed")
        print("🎉 All 8 tests passed successfully!")
    finally:
        if os.path.exists(temp_backup):
            shutil.copy2(temp_backup, DB_PATH)
            try:
                os.remove(temp_backup)
            except Exception:
                pass
