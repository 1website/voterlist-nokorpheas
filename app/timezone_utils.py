import datetime
from zoneinfo import ZoneInfo

# Cambodia Timezone (ICT, UTC+7 / Asia/Phnom_Penh)
try:
    CAMBODIA_TZ = ZoneInfo("Asia/Phnom_Penh")
except Exception:
    CAMBODIA_TZ = datetime.timezone(datetime.timedelta(hours=7))

KHMER_DIGITS = {
    '0': '០', '1': '១', '2': '២', '3': '៣', '4': '៤',
    '5': '៥', '6': '៦', '7': '៧', '8': '៨', '9': '៩'
}

def to_khmer_num(num) -> str:
    """Converts Arabic numbers/digits into Khmer numerals."""
    if num is None:
        return ""
    return "".join(KHMER_DIGITS.get(c, c) for c in str(num))

KHMER_WEEKDAYS = {
    0: "ថ្ងៃ ចន្ទ",
    1: "ថ្ងៃ អង្គារ",
    2: "ថ្ងៃ ពុធ",
    3: "ថ្ងៃ ព្រហស្បតិ៍",
    4: "ថ្ងៃ សុក្រ",
    5: "ថ្ងៃ សៅរ៍",
    6: "ថ្ងៃ អាទិត្យ"
}

KHMER_MONTHS = {
    1: "មករា", 2: "កុម្ភៈ", 3: "មីនា", 4: "មេសា",
    5: "ឧសភា", 6: "មិថុនា", 7: "កក្កដា", 8: "សីហា",
    9: "កញ្ញា", 10: "តុលា", 11: "វិច្ឆិកា", 12: "ធ្នូ"
}

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

def format_khmer_date(val, include_weekday: bool = True, leading_zero_day: bool = True) -> str:
    """
    Formats a date string (YYYY-MM-DD) or datetime/date object to official Khmer date format.
    Example: '2026-01-02' -> 'ថ្ងៃ សុក្រ ទី ០២ ខែ មករា ឆ្នាំ ២០២៦'
    Example: '2025-12-19' -> 'ថ្ងៃ សុក្រ ទី ១៩ ខែ ធ្នូ ឆ្នាំ ២០២៥'
    """
    if not val:
        return ""
    if isinstance(val, (datetime.date, datetime.datetime)):
        w_idx = val.weekday()
        w_str = KHMER_WEEKDAYS.get(w_idx, "")
        d_str = to_khmer_num(f"{val.day:02d}" if leading_zero_day else str(val.day))
        m_str = KHMER_MONTHS.get(val.month, "")
        y_str = to_khmer_num(val.year)
        if include_weekday and w_str:
            return f"{w_str} ទី {d_str} ខែ {m_str} ឆ្នាំ {y_str}".strip()
        else:
            return f"ថ្ងៃទី {d_str} ខែ {m_str} ឆ្នាំ {y_str}".strip()

    s = str(val).strip()
    if not s:
        return ""

    parts = [int(p) for p in s.replace('/', '-').replace('.', '-').split('-') if p.isdigit()]
    if len(parts) == 3:
        if parts[0] > 1000:
            y, m, d = parts[0], parts[1], parts[2]
        else:
            d, m, y = parts[0], parts[1], parts[2]
        try:
            dt = datetime.date(y, m, d)
            w_str = KHMER_WEEKDAYS.get(dt.weekday(), "")
            d_str = to_khmer_num(f"{d:02d}" if leading_zero_day else str(d))
            m_str = KHMER_MONTHS.get(m, "")
            y_str = to_khmer_num(y)
            if include_weekday and w_str:
                return f"{w_str} ទី {d_str} ខែ {m_str} ឆ្នាំ {y_str}".strip()
            else:
                return f"ថ្ងៃទី {d_str} ខែ {m_str} ឆ្នាំ {y_str}".strip()
        except Exception:
            return s
    elif len(parts) == 2:
        y, m = (parts[0], parts[1]) if parts[0] > 1000 else (parts[1], parts[0])
        m_str = KHMER_MONTHS.get(m, "")
        y_str = to_khmer_num(y)
        return f"ខែ {m_str} ឆ្នាំ {y_str}".strip()
    elif len(parts) == 1 and parts[0] > 1000:
        return f"ឆ្នាំ {to_khmer_num(parts[0])}".strip()

    return s

