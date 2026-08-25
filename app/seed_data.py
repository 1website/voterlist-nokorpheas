import datetime
import random
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import os
from sqlalchemy.orm import Session
from app.models import Village, PollingStation, Voter, User, BirthCertificate
from app.auth import hash_password

def seed_birth_certificates(db: Session):
    if db.query(BirthCertificate).count() > 0:
        return

    villages = db.query(Village).order_by(Village.code).all()
    if not villages:
        return

    print("Seeding birth certificate records & youth voter pipeline data...")

    kh_first_names_male = ["ស៊ឹម", "កែវ", "ចាន់", "ហេង", "ឡុង", "ប៊ុន", "សុខ", "អ៊ុំ", "អ៊ុក", "ទូច", "សួន", "មាស", "គង់", "ពេជ្រ", "ឈុន"]
    kh_last_names_male = ["វណ្ណា", "រតនា", "វិចិត្រ", "ធឿន", "សុខា", "ពិសិដ្ឋ", "សំណាង", "តារា", "សម្បត្តិ", "វិបុល", "បញ្ញា", "ចាន់ថន", "វុទ្ធី", "សិលា"]

    kh_first_names_female = ["មាស", "គឹម", "អ៊ុក", "ស៊ឹម", "កែវ", "ចាន់", "ហេង", "ឡុង", "ប៊ុន", "សុខ", "ទូច", "សួន", "ឈុន", "ពេជ្រ"]
    kh_last_names_female = ["សុផល", "សុជាតិ", "សុភា", "កល្យាណ", "ចិន្តា", "ស្រីពៅ", "ធីតា", "បុប្ផា", "ចរិយា", "មុន្នី", "ទេវី", "រស្មី", "លក្ខិណា", "វណ្ណី"]

    latin_map = {
        "ស៊ឹម": "SIM", "កែវ": "KEO", "ចាន់": "CHAN", "ហេង": "HENG", "ឡុង": "LONG",
        "ប៊ុន": "BUN", "សុខ": "SOK", "អ៊ុំ": "OUM", "អ៊ុក": "OUK", "ទូច": "TOUCH",
        "សួន": "SUON", "មាស": "MEAS", "គង់": "KONG", "ពេជ្រ": "PICH", "ឈុន": "CHHUN",
        "គឹម": "KIM", "វណ្ណា": "VANNA", "រតនា": "ROTHANA", "វិចិត្រ": "VICHET",
        "ធឿន": "THOEUN", "សុខា": "SOKHA", "ពិសិដ្ឋ": "PISETH", "សំណាង": "SAMNANG",
        "តារា": "DARA", "សម្បត្តិ": "SAMBATH", "វិបុល": "VIBOL", "បញ្ញា": "PANHA",
        "ចាន់ថន": "CHANTHORN", "វុទ្ធី": "VUTHY", "សិលា": "SEILA", "សុផល": "SOPHAL",
        "សុជាតិ": "SOCHEAT", "សុភា": "SOPHEA", "កល្យាណ": "KALYAN", "ចិន្តា": "CHINDA",
        "ស្រីពៅ": "SREYPOV", "ធីតា": "THIDA", "បុប្ផា": "BOPHA", "ចរិយា": "CHORIYA",
        "មុន្នី": "MONY", "ទេវី": "DEVI", "រស្មី": "REAKSMEY", "លក្ខិណា": "LEAKHENA", "វណ្ណី": "VANNY"
    }

    # Generate 65 realistic birth certificates
    cert_idx = 1
    for v in villages:
        # 6-8 records per village
        records_for_village = random.randint(6, 8)
        for _ in range(records_for_village):
            is_female = random.choice([True, False])
            if is_female:
                fn = random.choice(kh_first_names_female)
                ln = random.choice(kh_last_names_female)
                gender = "ស្រី"
            else:
                fn = random.choice(kh_first_names_male)
                ln = random.choice(kh_last_names_male)
                gender = "ប្រុស"

            name_kh = f"{fn} {ln}"
            en_fn = latin_map.get(fn, fn)
            en_ln = latin_map.get(ln, ln)
            name_en = f"{en_fn} {en_ln}"

            # Category distribution:
            # 40% turning 18 in 2026 (born 2008)
            # 25% turning 18 next year 2027 (born 2009)
            # 20% eligible now 19-20 (born 2006-2007)
            # 15% under 17 (born 2012-2016)
            cat_rnd = random.random()
            if cat_rnd < 0.40:
                b_year = 2008
                b_month = random.randint(1, 12)
                b_day = random.randint(1, 28)
            elif cat_rnd < 0.65:
                b_year = 2009
                b_month = random.randint(1, 12)
                b_day = random.randint(1, 28)
            elif cat_rnd < 0.85:
                b_year = random.choice([2006, 2007])
                b_month = random.randint(1, 12)
                b_day = random.randint(1, 28)
            else:
                b_year = random.randint(2012, 2017)
                b_month = random.randint(1, 12)
                b_day = random.randint(1, 28)

            dob_str = f"{b_year}-{b_month:02d}-{b_day:02d}"
            cert_no = f"ស.ក-{b_year}-{cert_idx:04d}"
            book_no = f"សៀវភៅលេខ {(cert_idx // 20) + 1:02d}/{b_year}"

            father_fn = random.choice(kh_first_names_male)
            father_ln = random.choice(kh_last_names_male)
            father_name = f"{father_fn} {father_ln}"

            mother_fn = random.choice(kh_first_names_female)
            mother_ln = random.choice(kh_last_names_female)
            mother_name = f"{mother_fn} {mother_ln}"

            address_str = f"ក្រុមទី {random.randint(1, 12)} {v.name_kh}"
            pob_str = f"{v.name_kh} ឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប"

            # Check if this person should be linked to an existing voter
            matched_voter = None
            is_reg = False
            voter_id = None
            if b_year <= 2008 and random.random() < 0.50:
                # Find an active voter in this village
                voter_cand = db.query(Voter).filter(Voter.village_id == v.id, Voter.status == "active").first()
                if voter_cand:
                    # Match name and dob with this voter
                    name_kh = voter_cand.name_kh
                    name_en = voter_cand.name_en
                    gender = voter_cand.gender
                    dob_str = voter_cand.dob
                    matched_voter = voter_cand
                    is_reg = True
                    voter_id = voter_cand.id

            bc = BirthCertificate(
                certificate_no=cert_no,
                book_no=book_no,
                name_kh=name_kh,
                name_en=name_en,
                gender=gender,
                dob=dob_str,
                pob=pob_str,
                father_name=father_name,
                mother_name=mother_name,
                address=address_str,
                village_id=v.id,
                voter_id=voter_id,
                is_registered_voter=is_reg,
                notes="កត់ត្រាក្នុងបញ្ជីអត្រានុកូលដ្ឋានរដ្ឋបាលឃុំនគរភាស",
                created_at=datetime.datetime.now() - datetime.timedelta(days=random.randint(1, 30))
            )
            db.add(bc)
            cert_idx += 1

    db.commit()
    print(f"Successfully seeded {cert_idx - 1} birth certificates!")

def seed_database(db: Session):
    # Always ensure Admin account exists
    admin_exists = db.query(User).filter(User.username == "admin").first()
    if not admin_exists:
        default_admin = User(
            username="admin",
            password_hash=hash_password("admin123"),
            full_name="ស្មៀនឃុំនគរភាស (Admin)",
            role="admin",
            phone="012 999 888",
            is_active=True
        )
        db.add(default_admin)
        db.commit()
        print("Ensured default admin account exists.")

    # Always ensure birth certificates are seeded if missing
    seed_birth_certificates(db)

    # Check if already seeded
    if db.query(Village).count() > 0:
        print("Database already initialized.")
        return

    print("Initializing database schema and records for Nokor Pheas Commune (ឃុំនគរភាស)...")

    # 1. 10 Villages of Nokor Pheas Commune
    villages_data = [
        {"code": "V01", "name_kh": "ភូមិរមៀត", "name_en": "Romiet", "chief_name": "លោក ស៊ឹម ចាន់ថា", "chief_phone": "012 884 101", "households": 280},
        {"code": "V02", "name_kh": "ភូមិគោកដូង", "name_en": "Kok Doung", "chief_name": "លោក អ៊ុំ សុខា", "chief_phone": "012 884 102", "households": 310},
        {"code": "V03", "name_kh": "ភូមិទំរាប់", "name_en": "Tumreab", "chief_name": "អ្នកស្រី មាស សុផល", "chief_phone": "012 884 103", "households": 220},
        {"code": "V04", "name_kh": "ភូមិគោកស្ពាន", "name_en": "Kok Spean", "chief_name": "លោក ហេង វណ្ណា", "chief_phone": "012 884 104", "households": 290},
        {"code": "V05", "name_kh": "ភូមិតាគួយ", "name_en": "Ta Kuoy", "chief_name": "លោក កែវ សំណាង", "chief_phone": "012 884 105", "households": 195},
        {"code": "V06", "name_kh": "ភូមិព្រៃទទឹង", "name_en": "Prey Totueng", "chief_name": "លោក ចាន់ រតនា", "chief_phone": "012 884 106", "households": 245},
        {"code": "V07", "name_kh": "ភូមិដូនអែម", "name_en": "Doun Aem", "chief_name": "អ្នកស្រី គឹម សុជាតិ", "chief_phone": "012 884 107", "households": 215},
        {"code": "V08", "name_kh": "ភូមិសំបួរ", "name_en": "Sambour", "chief_name": "លោក ឡុង វិចិត្រ", "chief_phone": "012 884 108", "households": 260},
        {"code": "V09", "name_kh": "ភូមិជ្រៃ", "name_en": "Chrey", "chief_name": "លោក ប៊ុន ធឿន", "chief_phone": "012 884 109", "households": 230},
        {"code": "V10", "name_kh": "ភូមិពង្រ", "name_en": "Pongro", "chief_name": "លោក សួន ពិសិដ្ឋ", "chief_phone": "012 884 110", "households": 250},
    ]

    village_objs = {}
    for v in villages_data:
        v_obj = Village(
            code=v["code"],
            name_kh=v["name_kh"],
            name_en=v["name_en"],
            chief_name=v["chief_name"],
            chief_phone=v["chief_phone"],
            total_households=v["households"]
        )
        db.add(v_obj)
        db.flush()
        village_objs[v["code"]] = v_obj

    # 2. 14 Polling Stations (០៧០១ ដល់ ០៧១៤)
    stations_data = [
        {"code": "0701", "name": "ការិយាល័យលេខ ០៧០១", "location": "សាលាបឋមសិក្សារមៀត (បន្ទប់ទី១)", "capacity": 600, "v_code": "V01", "officer": "លោក ម៉ែន វុទ្ធី", "phone": "097 501 0701"},
        {"code": "0702", "name": "ការិយាល័យលេខ ០៧០២", "location": "សាលាបឋមសិក្សារមៀត (បន្ទប់ទី២)", "capacity": 600, "v_code": "V01", "officer": "អ្នកស្រី ពេជ្រ រចនា", "phone": "097 502 0702"},
        {"code": "0703", "name": "ការិយាល័យលេខ ០៧០៣", "location": "វត្តរមៀតបុរាណ (សាលាឆាន់)", "capacity": 550, "v_code": "V01", "officer": "លោក ទេព វិបុល", "phone": "097 503 0703"},
        {"code": "0704", "name": "ការិយាល័យលេខ ០៧០៤", "location": "សាលាបឋមសិក្សាគោកដូង (បន្ទប់ទី១)", "capacity": 650, "v_code": "V02", "officer": "លោក ហុង វីរៈ", "phone": "097 504 0704"},
        {"code": "0705", "name": "ការិយាល័យលេខ ០៧០៥", "location": "វត្តគោកដូង (សាលាពុទ្ធិក)", "capacity": 500, "v_code": "V02", "officer": "អ្នកស្រី សុខ ម៉ាលី", "phone": "097 505 0705"},
        {"code": "0706", "name": "ការិយាល័យលេខ ០៧០៦", "location": "សាលាបឋមសិក្សាទំរាប់", "capacity": 600, "v_code": "V03", "officer": "លោក អ៊ុក សារិទ្ធ", "phone": "097 506 0706"},
        {"code": "0707", "name": "ការិយាល័យលេខ ០៧០៧", "location": "សាលាបឋមសិក្សាគោកស្ពាន (បន្ទប់ទី១)", "capacity": 550, "v_code": "V04", "officer": "លោក ឃីម សុភាព", "phone": "097 507 0707"},
        {"code": "0708", "name": "ការិយាល័យលេខ ០៧០៨", "location": "សាលាបឋមសិក្សាគោកស្ពាន (បន្ទប់ទី២)", "capacity": 550, "v_code": "V04", "officer": "អ្នកស្រី ង៉ែត សុគន្ធា", "phone": "097 508 0708"},
        {"code": "0709", "name": "ការិយាល័យលេខ ០៧០៩", "location": "វត្តតាគួយ", "capacity": 500, "v_code": "V05", "officer": "លោក យិន សម្បត្តិ", "phone": "097 509 0709"},
        {"code": "0710", "name": "ការិយាល័យលេខ ០៧១០", "location": "សាលាបឋមសិក្សាព្រៃទទឹង", "capacity": 600, "v_code": "V06", "officer": "លោក ឈឹម ដារ៉ា", "phone": "097 510 0710"},
        {"code": "0711", "name": "ការិយាល័យលេខ ០៧១១", "location": "វត្តដូនអែម", "capacity": 550, "v_code": "V07", "officer": "អ្នកស្រី នួន ស្រីមុំ", "phone": "097 511 0711"},
        {"code": "0712", "name": "ការិយាល័យលេខ ០៧១២", "location": "សាលាបឋមសិក្សាសំបួរ", "capacity": 600, "v_code": "V08", "officer": "លោក គង់ សុភ័ក្រ្ត", "phone": "097 512 0712"},
        {"code": "0713", "name": "ការិយាល័យលេខ ០៧១៣", "location": "វត្តជ្រៃសុវណ្ណារាម", "capacity": 550, "v_code": "V09", "officer": "លោក ផន កុសល", "phone": "097 513 0713"},
        {"code": "0714", "name": "ការិយាល័យលេខ ០៧១៤", "location": "សាលាបឋមសិក្សាពង្រ", "capacity": 600, "v_code": "V10", "officer": "អ្នកស្រី លី ធីតា", "phone": "097 514 0714"},
    ]

    station_objs = {}
    for s in stations_data:
        s_obj = PollingStation(
            code=s["code"],
            name=s["name"],
            location=s["location"],
            capacity=s["capacity"],
            village_id=village_objs[s["v_code"]].id,
            officer_name=s["officer"],
            officer_phone=s["phone"]
        )
        db.add(s_obj)
        db.flush()
        station_objs[s["code"]] = s_obj

    # 3. User Accounts with Roles
    # Admin User
    admin_user = User(
        username="admin",
        password_hash=hash_password("admin123"),
        full_name="ស្មៀនឃុំនគរភាស (Admin)",
        role="admin",
        phone="012 999 888",
        is_active=True
    )
    db.add(admin_user)
    db.flush()

    # 14 Station Officers
    for s_code, s_obj in station_objs.items():
        officer_user = User(
            username=f"officer_{s_code}",
            password_hash=hash_password("officer123"),
            full_name=f"{s_obj.officer_name} ({s_obj.code})",
            role="officer",
            station_id=s_obj.id,
            phone=s_obj.officer_phone,
            is_active=True
        )
        db.add(officer_user)

    # 10 Village Chiefs
    for v_code, v_obj in village_objs.items():
        chief_user = User(
            username=f"chief_{v_code.lower()}",
            password_hash=hash_password("chief123"),
            full_name=f"{v_obj.chief_name} ({v_obj.name_kh})",
            role="village_chief",
            village_id=v_obj.id,
            phone=v_obj.chief_phone,
            is_active=True
        )
        db.add(chief_user)

    db.flush()

    # 4. Realistic Cambodian Voters (130+ Voters across all 14 stations)
    seed_voters = os.getenv("SEED_DEMO_VOTERS", "true").strip().lower() not in ["false", "0", "no"]
    if not seed_voters:
        db.commit()
        print(f"Initialized database with {len(villages_data)} villages, {len(stations_data)} polling stations, and staff accounts (0 demo voters).")
        return

    first_names_male = ["សុខ", "ចាន់", "វណ្ណា", "សុផល", "សម្បត្តិ", "វិបុល", "រដ្ឋា", "វិចិត្រ", "ដារ៉ា", "កុសល", "វុទ្ធី", "សារិទ្ធ", "សំណាង", "ពិសិដ្ឋ", "គង់", "ប៊ុនធឿន", "សុភាព"]
    last_names = ["ស៊ឹម", "អ៊ុំ", "មាស", "ហេង", "កែវ", "ចាន់", "គឹម", "ឡុង", "ប៊ុន", "សួន", "ម៉ែន", "ពេជ្រ", "ទេព", "ហុង", "អ៊ុក", "ឃីម", "ង៉ែត", "យិន", "ឈឹម", "នួន", "ផន", "លី", "ទិត្យ", "ជា", "សេង", "ប្រាក់"]
    first_names_female = ["ស្រីពៅ", "ចរិយា", "បុប្ផា", "ធីតា", "រចនា", "ម៉ាលី", "សុគន្ធា", "ស្រីមុំ", "សុជាតិ", "សុវណ្ណ", "កល្យាណ", "សុភា", "កញ្ញា", "ទេវី", "ស្រីនាង", "ពិសី", "ចិន្តា"]

    latin_map = {
        "ស៊ឹម": "SIM", "អ៊ុំ": "UM", "មាស": "MEAS", "ហេង": "HENG", "កែវ": "KEO", "ចាន់": "CHAN",
        "គឹម": "KIM", "ឡុង": "LONG", "ប៊ុន": "BUN", "សួន": "SUON", "ម៉ែន": "MEN", "ពេជ្រ": "PICH",
        "ទេព": "TEP", "ហុង": "HONG", "អ៊ុក": "UK", "ឃីម": "KHIM", "ង៉ែត": "NGET", "យិន": "YIN",
        "ឈឹម": "CHHIM", "នួន": "NUON", "ផន": "PHORN", "លី": "LY", "ទិត្យ": "TIT", "ជា": "CHEA",
        "សេង": "SENG", "ប្រាក់": "PRAK", "សុខ": "SOK", "វណ្ណា": "VANNA", "សុផល": "SOPHAL",
        "សម្បត្តិ": "SAMBATH", "វិបុល": "VIBOL", "រដ្ឋា": "ROTHA", "វិចិត្រ": "VICHET", "ដារ៉ា": "DARA",
        "កុសល": "KOSAL", "វុទ្ធី": "VUTHY", "សារិទ្ធ": "SARITH", "សំណាង": "SAMNANG", "ពិសិដ្ឋ": "PISETH",
        "គង់": "KONG", "ប៊ុនធឿន": "BUNTHOEUN", "សុភាព": "SOPHEAP", "ស្រីពៅ": "SREYPOV",
        "ចរិយា": "CHORIYA", "បុប្ផា": "BOPHA", "ធីតា": "THIDA", "រចនា": "ROCHANA", "ម៉ាលី": "MALY",
        "សុគន្ធា": "SOKUNTHEA", "ស្រីមុំ": "SREYMOM", "សុជាតិ": "SOCHEAT", "សុវណ្ណ": "SOVAN",
        "កល្យាណ": "KALYAN", "សុភា": "SOPHEA", "កញ្ញា": "KANHA", "ទេវី": "DEVI", "ស្រីនាង": "SREYNEANG",
        "ពិសី": "PISEY", "ចិន្តា": "CHINDA"
    }

    voter_idx = 1
    national_id_base = 20491000

    # Ensure each station gets 8 to 12 voters for a diverse, balanced dataset
    for s_code, s_obj in station_objs.items():
        num_voters_for_station = random.randint(8, 11)
        for seq in range(1, num_voters_for_station + 1):
            is_female = (seq % 2 == 0)
            ln = last_names[(voter_idx + seq) % len(last_names)]
            fn = first_names_female[(voter_idx + seq) % len(first_names_female)] if is_female else first_names_male[(voter_idx + seq) % len(first_names_male)]
            
            kh_name = f"{ln} {fn}"
            en_ln = latin_map.get(ln, ln)
            en_fn = latin_map.get(fn, fn)
            en_name = f"{en_ln} {en_fn}"
            gender = "ស្រី" if is_female else "ប្រុស"

            # Birth year between 1955 and 2006 (age 18 to 69)
            birth_year = random.randint(1955, 2005)
            birth_month = random.randint(1, 12)
            birth_day = random.randint(1, 28)
            dob_str = f"{birth_year}-{birth_month:02d}-{birth_day:02d}"

            national_id = f"0{national_id_base + voter_idx}"
            voter_code = f"NP-{s_code}-{seq:04d}"

            # Status: mostly active, a few moved/deceased/suspended
            status = "active"
            if voter_idx % 23 == 0:
                status = "moved"
            elif voter_idx % 37 == 0:
                status = "deceased"
            elif voter_idx % 41 == 0:
                status = "suspended"

            # Has voted: simulate election day progression (~45% voted for active voters)
            has_voted = False
            voted_at = None
            if status == "active" and (seq % 2 == 1 or seq % 3 == 0):
                has_voted = True
                random_hour = random.randint(7, 14)
                random_min = random.randint(0, 59)
                voted_at = datetime.datetime.now().replace(hour=random_hour, minute=random_min, second=random.randint(0, 59))

            v_village_name = village_objs[s_obj.village_id].name_kh if s_obj.village_id in village_objs else ""
            address_str = f"ក្រុមទី {random.randint(1, 15)} {v_village_name}"
            photo_url = f"/static/images/avatars/female_{(voter_idx % 3) + 1}.jpg" if is_female else f"/static/images/avatars/male_{(voter_idx % 4) + 1}.jpg"
            voter = Voter(
                voter_code=voter_code,
                list_no=seq,
                national_id=national_id,
                name_kh=kh_name,
                name_en=en_name,
                gender=gender,
                dob=dob_str,
                address=address_str,
                village_id=s_obj.village_id,
                station_id=s_obj.id,
                status=status,
                photo_url=photo_url,
                has_voted=has_voted,
                voted_at=voted_at,
                voted_by_user_id=admin_user.id if has_voted else None,
                notes="បានចុះឈ្មោះបោះឆ្នោតផ្លូវការ",
                created_at=datetime.datetime.now() - datetime.timedelta(days=(voter_idx * 3) % 10, hours=random.randint(1, 8), minutes=random.randint(0, 59))
            )
            db.add(voter)
            voter_idx += 1

    db.commit()
    print(f"Successfully seeded database with {len(villages_data)} villages, {len(stations_data)} polling stations, and {voter_idx-1} voters.")

if __name__ == "__main__":
    from app.database import SessionLocal, engine, Base
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()
