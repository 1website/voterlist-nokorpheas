from pydantic import BaseModel, Field
from typing import Optional

class VoterCreateSchema(BaseModel):
    name_kh: str
    name_en: str
    gender: str
    dob: str
    national_id: str
    address: Optional[str] = ""
    village_id: int
    station_id: int
    notes: Optional[str] = ""

class VoterUpdateSchema(BaseModel):
    name_kh: str
    name_en: str
    gender: str
    dob: str
    national_id: str
    address: Optional[str] = ""
    village_id: int
    station_id: int
    status: str
    notes: Optional[str] = ""

class QuickCheckinSchema(BaseModel):
    voter_id: Optional[int] = None
    voter_code: Optional[str] = None
    national_id: Optional[str] = None

class VillageSchema(BaseModel):
    code: str
    name_kh: str
    name_en: str
    chief_name: Optional[str] = ""
    chief_phone: Optional[str] = ""
    total_households: Optional[int] = 0

class StationSchema(BaseModel):
    code: str
    name: str
    location: str
    capacity: int
    village_id: Optional[int] = None
    officer_name: Optional[str] = ""
    officer_phone: Optional[str] = ""

class BirthCertificateCreateSchema(BaseModel):
    certificate_no: str
    book_no: Optional[str] = ""
    name_kh: str
    name_en: str
    gender: str
    dob: str
    pob: Optional[str] = ""
    father_name: Optional[str] = ""
    mother_name: Optional[str] = ""
    address: Optional[str] = ""
    village_id: int
    registered_date: Optional[str] = ""
    notes: Optional[str] = ""

class ConvertToVoterSchema(BaseModel):
    birth_id: int
    national_id: str
    station_id: int
    address: Optional[str] = ""
    notes: Optional[str] = ""

