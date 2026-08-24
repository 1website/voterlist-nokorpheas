import datetime
from zoneinfo import ZoneInfo

# Cambodia Timezone (ICT, UTC+7 / Asia/Phnom_Penh)
try:
    CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")
except Exception:
    CAMBODIA_TZ = datetime.timezone(datetime.timedelta(hours=7))

def get_cambodia_now() -> datetime.datetime:
    """
    Returns naive datetime in Cambodia local time (UTC+7 / ICT).
    Always guarantees consistent local time regardless of host/server OS timezone (Render, Docker, Windows, Linux).
    """
    return datetime.datetime.now(CAMBODIA_TZ).replace(tzinfo=None)

def get_cambodia_today() -> datetime.date:
    """
    Returns today's date in Cambodia timezone (UTC+7).
    """
    return datetime.datetime.now(CAMBODIA_TZ).date()

def get_cambodia_today_str() -> str:
    """
    Returns today's date string 'YYYY-MM-DD' in Cambodia timezone.
    """
    return get_cambodia_today().strftime("%Y-%m-%d")
