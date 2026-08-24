import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base

class Village(Base):
    __tablename__ = "villages"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False) # e.g. V01 to V10
    name_kh = Column(String(100), nullable=False)                     # e.g. ភូមិរមៀត
    name_en = Column(String(100), nullable=False)                     # e.g. Romiet Village
    chief_name = Column(String(100), nullable=True)                  # e.g. លោក ឈុន វុទ្ធី
    chief_phone = Column(String(50), nullable=True)                  # e.g. 012 345 678
    total_households = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    stations = relationship("PollingStation", back_populates="village")
    voters = relationship("Voter", back_populates="village")
    users = relationship("User", back_populates="village")

    @property
    def total_voters(self):
        return len([v for v in self.voters if v.status == "active"])

    @property
    def total_voted(self):
        return len([v for v in self.voters if v.status == "active" and v.has_voted])


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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

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
    photo_url = Column(String(255), nullable=True)                          # Profile photo path
    has_voted = Column(Boolean, default=False)
    voted_at = Column(DateTime, nullable=True)
    voted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Relationships
    village = relationship("Village", back_populates="voters")
    station = relationship("PollingStation", back_populates="voters")
    voted_by_user = relationship("User", foreign_keys=[voted_by_user_id])

    @property
    def photo_display(self):
        if self.photo_url and self.photo_url.strip():
            return self.photo_url
        # Default gender avatar
        if self.gender == "ស្រី":
            return "/static/images/avatars/female_1.jpg"
        return "/static/images/avatars/male_1.jpg"


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
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationships
    station = relationship("PollingStation", back_populates="users")
    village = relationship("Village", back_populates="users")


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
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    # Relationship
    user = relationship("User", foreign_keys=[user_id])
