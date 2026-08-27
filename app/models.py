import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.timezone_utils import get_cambodia_now

class Village(Base):
    __tablename__ = "villages"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False) # e.g. V01 to V10
    name_kh = Column(String(100), nullable=False)                     # e.g. ភូមិរមៀត
    name_en = Column(String(100), nullable=False)                     # e.g. Romiet Village
    chief_name = Column(String(100), nullable=True)                  # e.g. លោក ឈុន វុទ្ធី
    chief_phone = Column(String(50), nullable=True)                  # e.g. 012 345 678
    total_households = Column(Integer, default=0)
    created_at = Column(DateTime, default=get_cambodia_now)

    # Relationships
    stations = relationship("PollingStation", back_populates="village")
    voters = relationship("Voter", back_populates="village")
    users = relationship("User", back_populates="village")
    birth_certificates = relationship("BirthCertificate", back_populates="village")

    @property
    def total_voters(self):
        return len([v for v in self.voters if v.status == "active"])

    @property
    def total_voted(self):
        return len([v for v in self.voters if v.status == "active" and v.has_voted])

    @property
    def total_birth_records(self):
        return len(self.birth_certificates)

    @property
    def eligible_youth_count(self):
        return len([b for b in self.birth_certificates if b.is_eligible_now or b.is_turning_18_this_year])

    @property
    def unregistered_youth_count(self):
        return len([b for b in self.birth_certificates if (b.is_eligible_now or b.is_turning_18_this_year) and not b.is_registered_voter])


class PollingStation(Base):
    __tablename__ = "polling_stations"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False) # e.g. 0701 to 0714
    name = Column(String(150), nullable=False)                         # e.g. ការិយាល័យលេខ ០៧០១
    location = Column(String(200), nullable=False)                     # e.g. សាលាបឋមសិក្សារមៀត (បន្ទប់ទី១)
    capacity = Column(Integer, default=600)                            # Maximum capacity
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=True)
    officer_name = Column(String(100), nullable=True)                  # Head of polling station
    officer_phone = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_cambodia_now)

    # Relationships
    village = relationship("Village", back_populates="stations")
    voters = relationship("Voter", back_populates="station")
    users = relationship("User", back_populates="station")

    @property
    def registered_count(self):
        return len([v for v in self.voters if v.status == "active"])

    @property
    def voted_count(self):
        return len([v for v in self.voters if v.status == "active" and v.has_voted])

    @property
    def turnout_percentage(self):
        reg = self.registered_count
        if reg == 0:
            return 0.0
        return round((self.voted_count / reg) * 100, 1)


class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, index=True)
    voter_code = Column(String(50), unique=True, index=True, nullable=False) # e.g. NP-0701-0001
    list_no = Column(Integer, nullable=False)                                # 1, 2, 3 in station
    national_id = Column(String(50), unique=True, index=True, nullable=False) # 9 or 10 digit Khmer ID card
    name_kh = Column(String(100), nullable=False)                            # ឈ្មោះខ្មែរ (e.g. ស៊ឹម ចាន់ថន)
    name_en = Column(String(100), nullable=False)                            # ឈ្មោះឡាតាំង (e.g. SIM CHANTHORN)
    gender = Column(String(20), nullable=False)                              # ប្រុស / ស្រី
    dob = Column(String(50), nullable=False)                                 # 1990-04-15 or 1990
    address = Column(String(255), nullable=True)                             # ក្រុមទី...
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    station_id = Column(Integer, ForeignKey("polling_stations.id"), nullable=False)
    status = Column(String(30), default="active")                            # active, moved, deceased, suspended
    reg_type = Column(String(30), default="new")                              # new (ចុះថ្មី), legacy (បញ្ជីចាស់), transferred (ផ្ទេរចូល)
    reg_year = Column(Integer, default=2026)                                  # ឆ្នាំចុះឈ្មោះ (2026, 2025, 2024...)
    reg_reason = Column(String(100), nullable=True)                           # first_time_18, never_registered, relocated, legacy
    photo_url = Column(Text, nullable=True)                                  # Base64 Data URI or Image path
    has_voted = Column(Boolean, default=False)
    voted_at = Column(DateTime, nullable=True)
    voted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_cambodia_now)
    updated_at = Column(DateTime, default=get_cambodia_now, onupdate=get_cambodia_now)

    # Relationships
    village = relationship("Village", back_populates="voters")
    station = relationship("PollingStation", back_populates="voters")
    voted_by_user = relationship("User", foreign_keys=[voted_by_user_id])
    birth_certificate = relationship("BirthCertificate", back_populates="voter", uselist=False)

    @property
    def reg_type_badge(self):
        yr = self.reg_year or 2026
        t = (self.reg_type or "new").lower()
        if t == "legacy":
            return {
                "text": f"បញ្ជីចាស់ ({yr})",
                "icon": "📋",
                "class": "badge-reg-legacy bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-300 dark:border-slate-700",
                "type": "legacy",
                "year": yr
            }
        elif t == "transferred":
            return {
                "text": f"ផ្ទេរចូល {yr}",
                "icon": "📦",
                "class": "badge-reg-transferred bg-purple-100 dark:bg-purple-950/60 text-purple-800 dark:text-purple-300 border-purple-300 dark:border-purple-700/60",
                "type": "transferred",
                "year": yr
            }
        else:
            return {
                "text": f"ចុះថ្មី {yr}",
                "icon": "✨",
                "class": "badge-reg-new bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300 border-emerald-300 dark:border-emerald-700/60",
                "type": "new",
                "year": yr
            }

    @property
    def photo_display(self):
        default_img = "/static/images/avatars/female_1.jpg" if self.gender == "ស្រី" else "/static/images/avatars/male_1.jpg"
        if self.photo_url and self.photo_url.strip():
            url = self.photo_url.strip()
            # 1. Base64 Data URI (permanently stored in database - immune to git pushes and server redeploys)
            if url.startswith("data:image/"):
                return url
            # 2. Static avatar preset or external URL
            if url.startswith("/static/images/avatars/") or url.startswith("http://") or url.startswith("https://"):
                return url
            # 3. Local uploaded file path fallback
            if url.startswith("/static/uploads/"):
                import os
                base_dir = os.path.dirname(os.path.abspath(__file__))
                clean_rel = url.lstrip("/").replace("/", os.sep)
                abs_path = os.path.join(base_dir, clean_rel)
                root_path = os.path.join(os.path.dirname(base_dir), clean_rel)
                if os.path.exists(abs_path) or os.path.exists(root_path) or os.path.exists(clean_rel):
                    return url
                return default_img
            return url
        return default_img


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False) # admin, officer, village_chief
    station_id = Column(Integer, ForeignKey("polling_stations.id"), nullable=True) # for station officers
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=True)         # for village chiefs
    phone = Column(String(50), nullable=True)
    photo_url = Column(Text, nullable=True)                                        # Base64 Data URI or Image path
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=get_cambodia_now)

    # Relationships
    station = relationship("PollingStation", back_populates="users")
    village = relationship("Village", back_populates="users")

    @property
    def avatar_display(self):
        if self.role == "admin":
            default_avatar = "/static/images/avatars/male_1.jpg"
        elif self.role == "officer":
            default_avatar = "/static/images/avatars/male_2.jpg"
        elif self.role == "viewer":
            default_avatar = "/static/images/avatars/female_1.jpg"
        else:
            default_avatar = "/static/images/avatars/male_3.jpg"

        if self.photo_url and self.photo_url.strip():
            url = self.photo_url.strip()
            # 1. Base64 Data URI (permanently stored in database - immune to git pushes and server redeploys)
            if url.startswith("data:image/"):
                return url
            # 2. Static avatar preset or external URL
            if url.startswith("/static/images/avatars/") or url.startswith("http://") or url.startswith("https://"):
                return url
            # 3. Local uploaded file path fallback
            if url.startswith("/static/uploads/"):
                import os
                base_dir = os.path.dirname(os.path.abspath(__file__))
                clean_rel = url.lstrip("/").replace("/", os.sep)
                abs_path = os.path.join(base_dir, clean_rel)
                root_path = os.path.join(os.path.dirname(base_dir), clean_rel)
                if os.path.exists(abs_path) or os.path.exists(root_path) or os.path.exists(clean_rel):
                    return url
                return default_avatar
            return url
        return default_avatar


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50), nullable=True)
    user_full_name = Column(String(100), nullable=True)
    user_role = Column(String(30), nullable=True)
    action = Column(String(50), nullable=False) # LOGIN, LOGOUT, CREATE_VOTER, UPDATE_VOTER, DELETE_VOTER, CHECKIN, UNCHECKIN, BACKUP, RESTORE, EXPORT
    action_type = Column(String(30), default="info") # info, success, warning, danger
    target_type = Column(String(50), nullable=True) # voter, user, station, village, system
    target_id = Column(String(50), nullable=True)
    description = Column(Text, nullable=False)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=get_cambodia_now)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])


class BirthCertificate(Base):
    __tablename__ = "birth_certificates"

    id = Column(Integer, primary_key=True, index=True)
    certificate_no = Column(String(50), unique=True, index=True, nullable=False) # e.g. ស.ក-២០២៦-០០១
    book_no = Column(String(50), nullable=True)                                  # e.g. ០១/២០២៦
    name_kh = Column(String(100), nullable=False)                                # ឈ្មោះខ្មែរ
    name_en = Column(String(100), nullable=False)                                # ឈ្មោះឡាតាំង
    gender = Column(String(20), nullable=False)                                  # ប្រុស / ស្រី
    dob = Column(String(50), nullable=False)                                     # YYYY-MM-DD
    pob = Column(String(255), nullable=True)                                     # ទីកន្លែងកំណើត
    father_name = Column(String(100), nullable=True)                             # ឈ្មោះឪពុក
    mother_name = Column(String(100), nullable=True)                             # ឈ្មោះម្តាយ
    address = Column(String(255), nullable=True)                                 # ក្រុមទី...
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=False)
    
    # ភ្ជាប់ជាមួយ Voter ពេលគាត់បានចុះឈ្មោះបោះឆ្នោត
    voter_id = Column(Integer, ForeignKey("voters.id"), nullable=True)
    is_registered_voter = Column(Boolean, default=False)
    registered_date = Column(String(50), nullable=True)                          # YYYY-MM-DD កាលបរិច្ឆេទចុះបញ្ជី
    attachment_url = Column(String(255), nullable=True)                          # PDF or Image attachment path
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=get_cambodia_now)
    updated_at = Column(DateTime, default=get_cambodia_now, onupdate=get_cambodia_now)

    # Relationships
    village = relationship("Village", back_populates="birth_certificates")
    voter = relationship("Voter", back_populates="birth_certificate", foreign_keys=[voter_id])

    @property
    def registered_date_effective(self):
        """Returns registered_date or falls back to created_at date (YYYY-MM-DD)"""
        if self.registered_date and self.registered_date.strip():
            return self.registered_date.strip()
        if self.created_at:
            if isinstance(self.created_at, datetime.datetime):
                return self.created_at.strftime("%Y-%m-%d")
            elif isinstance(self.created_at, str):
                return self.created_at[:10]
        return ""

    @property
    def registered_year(self):
        d = self.registered_date_effective
        if d and len(d) >= 4 and d[:4].isdigit():
            return int(d[:4])
        return 0

    @property
    def registered_month(self):
        d = self.registered_date_effective
        if d and len(d) >= 7 and d[5:7].isdigit():
            return int(d[5:7])
        return 0

    @property
    def is_pdf(self):
        if self.attachment_url:
            return self.attachment_url.lower().endswith(".pdf")
        return False

    @property
    def is_image(self):
        if self.attachment_url:
            return any(self.attachment_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif"])
        return False

    @property
    def age(self):
        try:
            today = get_cambodia_now().date()
            dob_parts = [int(p) for p in self.dob.strip().split("-") if p.isdigit()]
            if len(dob_parts) >= 1:
                birth_year = dob_parts[0]
                birth_month = dob_parts[1] if len(dob_parts) >= 2 else 1
                birth_day = dob_parts[2] if len(dob_parts) >= 3 else 1
                birth_date = datetime.date(birth_year, birth_month, birth_day)
                age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                return max(0, age)
        except Exception:
            pass
        return 0

    @property
    def birth_year(self):
        try:
            dob_parts = [int(p) for p in self.dob.strip().split("-") if p.isdigit()]
            if dob_parts:
                return dob_parts[0]
        except Exception:
            pass
        return 0

    @property
    def is_eligible_now(self):
        """Has reached 18 years of age today"""
        return self.age >= 18

    @property
    def is_turning_18_this_year(self):
        """Turns 18 during the current calendar year (e.g. 2026 - birth_year == 18)"""
        current_year = get_cambodia_now().year
        return (current_year - self.birth_year) == 18

    @property
    def is_turning_18_next_year(self):
        """Turns 18 during next calendar year (e.g. 2026 - birth_year == 17)"""
        current_year = get_cambodia_now().year
        return (current_year - self.birth_year) == 17

    @property
    def eligibility_category(self):
        if self.is_eligible_now:
            return "eligible_now" # គ្រប់អាយុបោះឆ្នោត (១៨+)
        elif self.is_turning_18_this_year:
            return "turning_18_this_year" # គ្រប់អាយុ ១៨ ឆ្នាំក្នុងឆ្នាំនេះ
        elif self.is_turning_18_next_year:
            return "turning_18_next_year" # នឹងគ្រប់អាយុ ១៨ ឆ្នាំនៅឆ្នាំក្រោយ
        else:
            return "under_18" # អនីតិជន (<១៧)

    @property
    def eligibility_badge(self):
        if self.is_eligible_now:
            return {
                "text": "គ្រប់អាយុ (១៨+)",
                "class": "bg-emerald-100 text-emerald-800 border-emerald-300",
                "icon": "✅"
            }
        elif self.is_turning_18_this_year:
            return {
                "text": "គ្រប់អាយុឆ្នាំនេះ",
                "class": "bg-amber-100 text-amber-800 border-amber-300",
                "icon": "⚡"
            }
        elif self.is_turning_18_next_year:
            return {
                "text": "គ្រប់អាយុឆ្នាំក្រោយ",
                "class": "bg-blue-100 text-blue-800 border-blue-300",
                "icon": "⏳"
            }
        else:
            return {
                "text": "អនីតិជន (<១៧)",
                "class": "bg-slate-100 text-slate-700 border-slate-300",
                "icon": "👶"
            }

