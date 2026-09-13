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
from app.timezone_utils import get_cambodia_now, get_cambodia_today, get_cambodia_today_str, format_khmer_date

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
    send_excel = get_setting(db, "telegram_send_excel", "true").lower() in ["true", "1", "yes"]

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
    """Build a rich, structured Khmer text report summarizing voter registrations."""
    now = get_cambodia_now()
    if not target_date_str:
        target_date_str = now.strftime("%Y-%m-%d")

    # Fetch voters registered on target_date_str
    today_voters = db.query(Voter).filter(
        func.date(Voter.created_at) == target_date_str
    ).all()

    # Birth certificates registered today
    bc_count = db.query(BirthCertificate).filter(
        func.date(BirthCertificate.created_at) == target_date_str
    ).count()

    today_total = len(today_voters)
    today_female = len([v for v in today_voters if v.gender == "ស្រី"])
    today_male = len([v for v in today_voters if v.gender == "ប្រុស"])

    # Registration types
    new_reg = len([v for v in today_voters if (v.reg_type or "new").lower() == "new"])
    legacy_reg = len([v for v in today_voters if (v.reg_type or "").lower() == "legacy"])
    transferred_reg = len([v for v in today_voters if (v.reg_type or "").lower() == "transferred"])

    # Age groups of today's registrations
    youth_c = 0
    adult_c = 0
    elderly_c = 0
    for v in today_voters:
        grp = v.age_group_info["key"]
        if grp == "youth":
            youth_c += 1
        elif grp == "adult":
            adult_c += 1
        elif grp == "elderly":
            elderly_c += 1

    # Cumulative commune stats
    all_voters = db.query(Voter).all()
    cum_total = len(all_voters)
    cum_female = len([v for v in all_voters if v.gender == "ស្រី"])
    cum_voted = len([v for v in all_voters if v.has_voted])
    cum_female_pct = round((cum_female / cum_total * 100), 1) if cum_total > 0 else 0
    cum_turnout_pct = round((cum_voted / cum_total * 100), 1) if cum_total > 0 else 0

    # Top active stations today
    station_counts = {}
    for v in today_voters:
        if v.station_id:
            station_counts[v.station_id] = station_counts.get(v.station_id, 0) + 1

    stations = db.query(PollingStation).all()
    st_map = {s.id: s for s in stations}
    top_stations = sorted(station_counts.items(), key=lambda x: x[1], reverse=True)[:3]

    st_lines = []
    if top_stations:
        for idx, (st_id, count) in enumerate(top_stations, 1):
            st = st_map.get(st_id)
            name = f"{st.code} ({st.name})" if st else f"ការិយាល័យ #{st_id}"
            st_lines.append(f"  {idx}. {name}៖ <b>{count}</b> នាក់")
    else:
        st_lines.append("  • ពុំទាន់មានទិន្នន័យចុះឈ្មោះតាមការិយាល័យនៅឡើយ")
    st_summary_str = "\n".join(st_lines)

    date_kh = format_khmer_date(now)
    time_str = now.strftime("%H:%M")

    msg = f"""🗳️ <b>របាយការណ៍បូកសរុបការចុះឈ្មោះបោះឆ្នោតប្រចាំថ្ងៃ</b>
🏛️ <b>រដ្ឋបាលឃុំនគរភាស ស្រុកអង្គរជុំ ខេត្តសៀមរាប</b>
📅 កាលបរិច្ឆេទ៖ {date_kh}
⏰ ម៉ោងចេញរបាយការណ៍៖ {time_str} នាទី

📊 <b>ស្ថិតិចុះឈ្មោះសរុបថ្ងៃនេះ ({target_date_str})៖</b>
• ចំនួនចុះឈ្មោះសរុប៖ <b>{today_total}</b> នាក់ (ស្រី <b>{today_female}</b> | ប្រុស <b>{today_male}</b>)
• ✨ ចុះឈ្មោះថ្មី (New)៖ <b>{new_reg}</b> នាក់
• 📋 បញ្ជីចាស់ (Legacy)៖ <b>{legacy_reg}</b> នាក់
• 📦 ផ្ទេរចូល (Transferred)៖ <b>{transferred_reg}</b> នាក់
• 📜 សំបុត្រកំណើតចុះថ្មី៖ <b>{bc_count}</b> ច្បាប់

👥 <b>ស្ថិតិតាមក្រុមអាយុ (ថ្ងៃនេះ)៖</b>
🟢 យុវជន (១៨-៣៥ ឆ្នាំ)៖ <b>{youth_c}</b> នាក់
🔵 វ័យកណ្តាល (៣៦-៥៩ ឆ្នាំ)៖ <b>{adult_c}</b> នាក់
🟠 មនុស្សចាស់ (៦០ ឆ្នាំឡើង)៖ <b>{elderly_c}</b> នាក់

🏢 <b>ការិយាល័យចុះឈ្មោះសកម្មបំផុតថ្ងៃនេះ៖</b>
{st_summary_str}

📈 <b>ទិន្នន័យបូកសរុបទូទាំងឃុំនគរភាស (១០ ភូមិ • ១៤ ការិយាល័យ)៖</b>
• សរុបអ្នកក្នុងបញ្ជីទាំងអស់៖ <b>{cum_total}</b> នាក់
• សរុបស្រី៖ <b>{cum_female}</b> នាក់ ({cum_female_pct}%)
• បានបោះឆ្នោតរួច៖ <b>{cum_voted}</b> នាក់ ({cum_turnout_pct}%)
--------------------------------------------
✨ <i>ប្រព័ន្ធគ្រប់គ្រងអ្នកបោះឆ្នោតឃុំនគរភាស (VoterList Nokor Pheas)</i>"""

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
    send_excel: bool = True,
    token: str = None,
    chat_id: str = None
) -> dict:
    """Send both the structured message report and optional Excel attachment to Telegram."""
    cfg = get_telegram_config(db)
    use_token = token or cfg["token"]
    use_chat_id = chat_id or cfg["chat_id"]
    attach_excel = send_excel if send_excel is not None else cfg["send_excel"]

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
