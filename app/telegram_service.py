import os
import io
import json
import uuid
import datetime
import urllib.request
import urllib.parse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import SystemSetting, Voter, BirthCertificate, PollingStation, Village
from app.timezone_utils import get_cambodia_now, get_cambodia_today, get_cambodia_today_str, format_khmer_date, to_khmer_num

# Default configurations provided for Nokor Pheas Commune
DEFAULT_BOT_TOKEN = "8543218727:AAEQkvkMTdKvjT0JAANOapjM4HHSmxlxOn4"
DEFAULT_CHAT_ID = "-5440917794"
DEFAULT_CHAT_TITLE = "របាយការណ៍ចុះឈ្មោះបោះឆ្នោត"

def get_setting(db: Session, key: str, default: str = "") -> str:
    """Read a setting from system_settings table, falling back to environment variable, then default."""
    if db:
        try:
            row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
            if row and row.value is not None and row.value != "":
                return row.value.strip()
        except Exception:
            pass
    env_val = os.getenv(key.upper(), "")
    if env_val:
        return env_val.strip()
    return default

def set_setting(db: Session, key: str, value: str, description: str = ""):
    """Store or update a setting in system_settings table."""
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row:
            row.value = str(value)
            if description:
                row.description = description
            row.updated_at = get_cambodia_now()
        else:
            new_row = SystemSetting(
                key=key,
                value=str(value),
                description=description,
                updated_at=get_cambodia_now()
            )
            db.add(new_row)
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error saving setting {key}: {e}")

def get_telegram_config(db: Session = None) -> dict:
    """Retrieve the full Telegram Bot configuration."""
    token = get_setting(db, "telegram_bot_token", DEFAULT_BOT_TOKEN)
    chat_id = get_setting(db, "telegram_chat_id", DEFAULT_CHAT_ID)
    chat_title = get_setting(db, "telegram_chat_title", DEFAULT_CHAT_TITLE)
    enabled = get_setting(db, "telegram_enabled", "true").lower() in ["true", "1", "yes"]
    auto_send = get_setting(db, "telegram_auto_send", "true").lower() in ["true", "1", "yes"]
    auto_time = get_setting(db, "telegram_auto_time", "17:00")
    send_excel = get_setting(db, "telegram_send_excel", "false").lower() in ["true", "1", "yes"]

    return {
        "token": token,
        "chat_id": chat_id,
        "chat_title": chat_title,
        "enabled": enabled,
        "auto_send": auto_send,
        "auto_time": auto_time,
        "send_excel": send_excel,
    }

def send_telegram_message(
    text: str,
    token: str = None,
    chat_id: str = None,
    parse_mode: str = "HTML"
) -> dict:
    """Send an HTML/text message via Telegram Bot API."""
    use_token = (token or DEFAULT_BOT_TOKEN).strip()
    use_chat_id = (chat_id or DEFAULT_CHAT_ID).strip()

    if not use_token or not use_chat_id:
        return {"success": False, "error": "Bot Token ឬ Chat ID មិនទាន់បានកំណត់"}

    url = f"https://api.telegram.org/bot{use_token}/sendMessage"
    payload = {
        "chat_id": use_chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
            result = json.loads(body)
            return {"success": result.get("ok", False), "result": result}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return {"success": False, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def send_telegram_document(
    file_bytes: bytes,
    filename: str,
    caption: str = "",
    token: str = None,
    chat_id: str = None
) -> dict:
    """Send an Excel or document file via Telegram Bot API."""
    use_token = (token or DEFAULT_BOT_TOKEN).strip()
    use_chat_id = (chat_id or DEFAULT_CHAT_ID).strip()

    if not use_token or not use_chat_id:
        return {"success": False, "error": "Bot Token ឬ Chat ID មិនទាន់បានកំណត់"}

    url = f"https://api.telegram.org/bot{use_token}/sendDocument"
    boundary = f"----TelegramBoundary{uuid.uuid4().hex}"
    
    body = io.BytesIO()
    # chat_id field
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{use_chat_id}\r\n".encode("utf-8"))
    # caption field
    if caption:
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode("utf-8"))
    # document field
    body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{filename}\"\r\nContent-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n".encode("utf-8"))
    body.write(file_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))

    data = body.getvalue()

    try:
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            body_res = resp.read().decode("utf-8")
            result = json.loads(body_res)
            return {"success": result.get("ok", False), "result": result}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if hasattr(e, "read") else str(e)
        return {"success": False, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def detect_active_chats(token: str = None) -> list:
    """Query getUpdates to find all Telegram groups and chats where the bot is a member."""
    use_token = (token or DEFAULT_BOT_TOKEN).strip()
    url = f"https://api.telegram.org/bot{use_token}/getUpdates"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "NokorPheasVoterSystem/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if not data.get("ok"):
                return []
            
            chats = {}
            for update in data.get("result", []):
                msg = update.get("message") or update.get("my_chat_member") or update.get("channel_post")
                if msg and "chat" in msg:
                    chat = msg["chat"]
                    c_id = str(chat["id"])
                    c_title = chat.get("title") or chat.get("first_name", "Unnamed Chat")
                    c_type = chat.get("type", "unknown")
                    chats[c_id] = {
                        "id": c_id,
                        "title": c_title,
                        "type": c_type
                    }
            return list(chats.values())
    except Exception as e:
        print(f"Error detecting active Telegram chats: {e}")
        return []

def build_daily_report_message(db: Session, target_date_str: str = None) -> str:
    """
    Build text daily report matching the exact official template:
    📋 របាយការណ៍ចុះឈ្មោះបោះឆ្នោតប្រចាំឆ្នាំ ២០២៦

    🗓️ កាលបរិច្ឆេទ៖ ១២/០៩/២០២៦ (ម៉ោង ០៤:២៩ រសៀល)
    ⏰ រយៈពេលយុទ្ធនាការ៖ ០៤ តុលា ២០២៦ ដល់ ០៣ ធ្នូ ២០២៦
    ───────────────────────────────
    👥 ចុះឈ្មោះប្រចាំថ្ងៃសរុប៖ ១ នាក់
    👩 ស្រី៖ ០ នាក់ (0.0%)
    ───────────────────────────────
    🏢 បូកសរុបតាមការិយាល័យបោះឆ្នោត៖

    • ការិ ០០៦៤៖ ១ នាក់ (ស្រី ០ នាក់)
    ───────────────────────────────
    📡 ផ្ញើចេញពីប្រព័ន្ធគ្រប់គ្រងការបោះឆ្នោត (Vote Notification Bot)
    """
    now = get_cambodia_now()
    if not target_date_str:
        target_date_str = now.strftime("%Y-%m-%d")

    try:
        dt_target = datetime.datetime.strptime(target_date_str, "%Y-%m-%d")
    except Exception:
        dt_target = now

    # Target date formatted as DD/MM/YYYY in Khmer numerals
    day_str = f"{dt_target.day:02d}"
    month_str = f"{dt_target.month:02d}"
    year_str = f"{dt_target.year}"
    date_kh = f"{to_khmer_num(day_str)}/{to_khmer_num(month_str)}/{to_khmer_num(year_str)}"
    year_kh = to_khmer_num(year_str)

    # Time formatted as 12-hour (e.g., ម៉ោង ០៤:២៩ រសៀល)
    h24 = now.hour
    h12 = h24 % 12
    if h12 == 0:
        h12 = 12
    hour_kh = to_khmer_num(f"{h12:02d}")
    minute_kh = to_khmer_num(f"{now.minute:02d}")
    
    if h24 < 12:
        period_kh = "ព្រឹក"
    elif h24 < 17:
        period_kh = "រសៀល"
    else:
        period_kh = "ល្ងាច"

    time_kh_full = f"(ម៉ោង {hour_kh}:{minute_kh} {period_kh})"

    # Campaign period
    campaign_period = get_setting(db, "telegram_campaign_period", "០៤ តុលា ២០២៦ ដល់ ០៣ ធ្នូ ២០២៦")

    # Fetch voters registered on target_date_str
    today_voters = db.query(Voter).filter(
        func.date(Voter.created_at) == target_date_str
    ).all()

    today_total = len(today_voters)
    today_female = len([v for v in today_voters if v.gender == "ស្រី"])
    female_pct = f"{(today_female / today_total * 100):.1f}%" if today_total > 0 else "0.0%"

    # Breakdown by Polling Station
    station_stats = {}
    for v in today_voters:
        if v.station_id:
            if v.station_id not in station_stats:
                station_stats[v.station_id] = {"total": 0, "female": 0}
            station_stats[v.station_id]["total"] += 1
            if v.gender == "ស្រី":
                station_stats[v.station_id]["female"] += 1

    stations = db.query(PollingStation).all()
    st_map = {s.id: s for s in stations}

    st_lines = []
    if station_stats:
        sorted_st_ids = sorted(
            station_stats.keys(),
            key=lambda sid: (st_map.get(sid).code if st_map.get(sid) and st_map.get(sid).code else str(sid))
        )
        for sid in sorted_st_ids:
            st = st_map.get(sid)
            code = st.code if st and st.code else f"{sid:04d}"
            cnt = station_stats[sid]["total"]
            fem_cnt = station_stats[sid]["female"]
            st_lines.append(f"• ការិ {to_khmer_num(code)}៖ {to_khmer_num(cnt)} នាក់ (ស្រី {to_khmer_num(fem_cnt)} នាក់)")
    else:
        st_lines.append("• គ្មានការចុះឈ្មោះក្នុងថ្ងៃនេះ")

    stations_block = "\n".join(st_lines)
    divider = "───────────────────────────────"

    msg = f"""📋 <b>របាយការណ៍ចុះឈ្មោះបោះឆ្នោតប្រចាំឆ្នាំ {year_kh}</b>

🗓️ <b>កាលបរិច្ឆេទ៖</b> {date_kh} {time_kh_full}
⏰ <b>រយៈពេលយុទ្ធនាការ៖</b> {campaign_period}
{divider}
👥 <b>ចុះឈ្មោះប្រចាំថ្ងៃសរុប៖</b> {to_khmer_num(today_total)} នាក់
👩 <b>ស្រី៖</b> {to_khmer_num(today_female)} នាក់ ({female_pct})
{divider}
🏢 <b>បូកសរុបតាមការិយាល័យបោះឆ្នោត៖</b>

{stations_block}
{divider}
📡 <i>ផ្ញើចេញពីប្រព័ន្ធគ្រប់គ្រងការបោះឆ្នោត (Vote Notification Bot)</i>"""

    return msg

def generate_daily_excel_bytes(db: Session, target_date_str: str = None) -> tuple[bytes, str]:
    """Generate the official openpyxl Excel registration sheet for target date."""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    from openpyxl.utils import get_column_letter

    now = get_cambodia_now()
    if not target_date_str:
        target_date_str = now.strftime("%Y-%m-%d")

    voters = db.query(Voter).filter(
        func.date(Voter.created_at) == target_date_str
    ).order_by(Voter.station_id.asc(), Voter.list_no.asc()).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "របាយការណ៍ប្រចាំថ្ងៃ"
    ws.views.sheetView[0].showGridLines = True

    # Styling definitions
    title_font = Font(name="Khmer OS Muol Light", size=14, bold=True, color="1E3A8A")
    sub_font = Font(name="Khmer OS Siemreap", size=11, bold=True, color="475569")
    header_font = Font(name="Khmer OS Siemreap", size=10, bold=True, color="FFFFFF")
    data_font = Font(name="Khmer OS Siemreap", size=10)

    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    sub_header_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )

    # Title rows
    ws.merge_cells("A1:K1")
    ws["A1"] = "ព្រះរាជាណាចក្រកម្ពុជា ជាតិ សាសនា ព្រះមហាក្សត្រ"
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:K2")
    ws["A2"] = "រដ្ឋបាលឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប"
    ws["A2"].font = sub_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:K3")
    ws["A3"] = f"បញ្ជីឈ្មោះអ្នកចុះឈ្មោះបោះឆ្នោតប្រចាំថ្ងៃ៖ {target_date_str} (សរុប {len(voters)} នាក់)"
    ws["A3"].font = Font(name="Khmer OS Siemreap", size=11, bold=True, color="0F766E")
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    # Table Header
    headers = [
        "ល.រ", "ម៉ោង", "កូដអ្នកបោះឆ្នោត", "លេខអត្តសញ្ញាណ",
        "គោត្តនាម-នាម", "អក្សរឡាតាំង", "ភេទ", "ថ្ងៃខែឆ្នាំកំណើត",
        "ភូមិ", "ការិយាល័យបោះឆ្នោត", "កំណត់សម្គាល់"
    ]

    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=5, column=col_num, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border

    row_num = 6
    for idx, v in enumerate(voters, 1):
        time_str = v.created_at.strftime("%H:%M:%S") if v.created_at else ""
        ws.cell(row=row_num, column=1, value=idx).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=2, value=time_str).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=3, value=v.voter_code).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=4, value=v.national_id).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=5, value=v.name_kh).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=6, value=v.name_en).alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=7, value=v.gender).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=8, value=v.dob).alignment = Alignment(horizontal="center")
        ws.cell(row=row_num, column=9, value=v.village.name_kh if v.village else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=10, value=f"{v.station.code} - {v.station.name}" if v.station else "").alignment = Alignment(horizontal="left")
        ws.cell(row=row_num, column=11, value=v.notes or "បានចុះឈ្មោះ").alignment = Alignment(horizontal="left")

        for c in range(1, 12):
            cell = ws.cell(row=row_num, column=c)
            cell.font = data_font
            cell.border = thin_border
            if row_num % 2 == 1:
                cell.fill = sub_header_fill
        row_num += 1

    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.row < 5:
                continue
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"Daily_Registrations_Nokor_Pheas_{target_date_str}.xlsx"
    return output.getvalue(), filename

def send_daily_report(
    db: Session,
    target_date_str: str = None,
    send_excel: bool = False,
    token: str = None,
    chat_id: str = None
) -> dict:
    """Send structured text report (and optional Excel attachment if explicitly requested) to Telegram."""
    cfg = get_telegram_config(db)
    use_token = token or cfg["token"]
    use_chat_id = chat_id or cfg["chat_id"]
    attach_excel = send_excel if send_excel is not None else cfg.get("send_excel", False)

    # 1. Send HTML Text Report
    report_text = build_daily_report_message(db, target_date_str)
    msg_res = send_telegram_message(report_text, token=use_token, chat_id=use_chat_id)

    doc_res = None
    if attach_excel:
        # 2. Generate and send Excel Document
        excel_bytes, filename = generate_daily_excel_bytes(db, target_date_str)
        caption = f"📊 ឯកសារបញ្ជីឈ្មោះអ្នកចុះឈ្មោះបោះឆ្នោតប្រចាំថ្ងៃ៖ {target_date_str or get_cambodia_today_str()} (រដ្ឋបាលឃុំនគរភាស)"
        doc_res = send_telegram_document(excel_bytes, filename, caption=caption, token=use_token, chat_id=use_chat_id)

    return {
        "success": msg_res.get("success", False),
        "message_result": msg_res,
        "document_result": doc_res
    }
