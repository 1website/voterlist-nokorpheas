import datetime
from fastapi.testclient import TestClient
import main
from app.database import SessionLocal
from app.models import Voter, Village, PollingStation, User
from app.timezone_utils import get_cambodia_now

def test_id_expiry_system():
    client = TestClient(main.app)
    db = SessionLocal()

    village = db.query(Village).first()
    station = db.query(PollingStation).first()
    today = get_cambodia_now().date()
    today_str = today.strftime("%Y-%m-%d")

    # Create test voters with different ID expiry dates
    v1 = Voter(
        voter_code='TEST-EXP-01',
        list_no=9001,
        name_kh='អ្នក ផុតសុពលភាព',
        gender='ប្រុស',
        dob='1990-01-01',
        national_id='020999001',
        id_expiry_date='2024-01-01',  # Expired
        village_id=village.id,
        station_id=station.id,
        status='active'
    )
    v2 = Voter(
        voter_code='TEST-EXP-02',
        list_no=9002,
        name_kh='អ្នក ជិតផុតសុពលភាព',
        gender='ស្រី',
        dob='1992-02-02',
        national_id='020999002',
        id_expiry_date=(today + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),  # Expiring soon
        village_id=village.id,
        station_id=station.id,
        status='active'
    )
    v3 = Voter(
        voter_code='TEST-EXP-03',
        list_no=9003,
        name_kh='អ្នក មានសុពលភាព',
        gender='ប្រុស',
        dob='1994-03-03',
        national_id='020999003',
        id_expiry_date=(today + datetime.timedelta(days=365)).strftime("%Y-%m-%d"),  # Valid
        village_id=village.id,
        station_id=station.id,
        status='active'
    )

    db.add_all([v1, v2, v3])
    db.commit()
    db.refresh(v1)
    db.refresh(v2)
    db.refresh(v3)

    try:
        # Check model properties
        assert v1.id_card_expiry_status['key'] == 'expired'
        assert v1.id_card_expiry_status['is_expired'] is True

        assert v2.id_card_expiry_status['key'] == 'expiring_soon'
        assert v2.id_card_expiry_status['is_warning'] is True

        assert v3.id_card_expiry_status['key'] == 'valid'
        assert v3.id_card_expiry_status['is_expired'] is False

        # Authenticate
        login_res = client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=False)
        assert login_res.status_code in [302, 303]
        cookies = login_res.cookies

        # Test ID Expiry Report Page
        res_rep = client.get('/reports/id-expiry', cookies=cookies)
        assert res_rep.status_code == 200
        assert "របាយការណ៍អត្តសញ្ញាណប័ណ្ណផុតសុពលភាព" in res_rep.text

        # Test Filters on Report Page
        res_filter_exp = client.get('/reports/id-expiry?status=expired', cookies=cookies)
        assert res_filter_exp.status_code == 200
        assert "TEST-EXP-01" in res_filter_exp.text

        res_filter_soon = client.get('/reports/id-expiry?status=expiring_soon', cookies=cookies)
        assert res_filter_soon.status_code == 200
        assert "TEST-EXP-02" in res_filter_soon.text

        # Test Excel Export
        res_excel = client.get('/reports/id-expiry/export/excel?status=attention', cookies=cookies)
        assert res_excel.status_code == 200
        assert len(res_excel.content) > 2000

        # Test Print View
        res_print = client.get('/reports/id-expiry/print?status=expired', cookies=cookies)
        assert res_print.status_code == 200
        assert "TEST-EXP-01" in res_print.text

        # Test Voter List Page with id_status filter
        res_voter_list = client.get('/voters?id_status=expired', cookies=cookies)
        assert res_voter_list.status_code == 200

        print("✅ All ID Expiry unit and integration tests passed successfully!")
    finally:
        db.delete(v1)
        db.delete(v2)
        db.delete(v3)
        db.commit()
        db.close()

if __name__ == '__main__':
    test_id_expiry_system()
