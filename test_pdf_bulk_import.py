import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')

from app.database import SessionLocal, engine
from app.models import Voter, PollingStation, Village
from app.pdf_importer import preview_pdf_import, execute_pdf_import

def run_tests():
    pdf_path = r"C:\Users\ASUS Vivobook\OneDrive\Voter-List 2025\170050061.pdf"
    if not os.path.exists(pdf_path):
        print(f"Error: Test file not found at {pdf_path}")
        return False

    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    db = SessionLocal()
    try:
        print("=== TEST 1: PDF PREVIEW & EXTRACTION ===")
        preview = preview_pdf_import(pdf_bytes, "170050061.pdf", db)
        assert preview["success"] is True, "Preview should be successful"
        assert preview["total_pages"] == 36, f"Expected 36 pages, got {preview['total_pages']}"
        assert preview["total_voters"] == 355, f"Expected 355 voters, got {preview['total_voters']}"
        assert preview["matched_station"] is not None, "Station should be matched"
        assert preview["matched_station"]["code"] == "0061", "Station code should be 0061"
        assert preview["matched_village"] is not None, "Village should be matched"
        assert "ល្បើក" in preview["matched_village"]["name"], "Village should be ភូមិល្បើក"
        print(f"✓ Preview verified: {preview['total_voters']} voters across {preview['total_pages']} pages.")
        print(f"✓ Matched Station: {preview['matched_station']['name']} (ID: {preview['matched_station']['id']})")
        print(f"✓ Matched Village: {preview['matched_village']['name']} (ID: {preview['matched_village']['id']})")

        # Check sample records
        sample = preview["preview_records"][0]
        assert sample["voter_code"] == "08-531-702"
        assert "កន" in sample["name_kh"]
        assert sample["gender"] == "ស្រី"
        assert sample["dob"] == "1983-08-08"
        assert sample["photo_url"] is not None
        print(f"✓ Record #1 verified: {sample['voter_code']} - {sample['name_kh']} ({sample['gender']}, {sample['dob']}) with portrait photo.")

        print("\n=== TEST 2: DATABASE EXECUTION IMPORT ===")
        station_id = preview["matched_station"]["id"]
        village_id = preview["matched_village"]["id"]

        import_res = execute_pdf_import(
            file_bytes=pdf_bytes,
            filename="170050061.pdf",
            station_id=station_id,
            village_id=village_id,
            update_existing=True,
            user_id=1,
            db=db
        )

        assert import_res["success"] is True
        assert import_res["total_records"] == 355
        print(f"✓ DB Execution Result: Total={import_res['total_records']}, Inserted={import_res['inserted']}, Updated={import_res['updated']}")

        # Verify query directly from database
        db_voters = db.query(Voter).filter(
            Voter.station_id == station_id,
            Voter.reg_type == "legacy",
            Voter.reg_year == 2025
        ).all()
        print(f"✓ Queried from DB: Found {len(db_voters)} voters in Station {station_id} with reg_year=2025.")
        assert len(db_voters) == 355, f"Expected 355 records in DB, found {len(db_voters)}"

        v1 = db.query(Voter).filter(Voter.voter_code == "08-531-702").first()
        assert v1 is not None, "Voter 08-531-702 should exist in DB"
        assert "កន" in v1.name_kh
        assert v1.photo_url is not None
        print(f"✓ DB Record Detail: {v1.voter_code} | {v1.name_kh} | {v1.gender} | {v1.dob} | Photo: {v1.photo_url[:40]}...")

        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
        return True

    finally:
        db.close()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
