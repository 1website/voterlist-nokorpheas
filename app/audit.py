import datetime
from app.models import AuditLog
from app.timezone_utils import get_cambodia_now

def log_activity(
    db,
    user=None,
    action: str = "GENERAL",
    description: str = "",
    target_type: str = None,
    target_id: str = None,
    action_type: str = "info",
    request = None,
    ip_address: str = None
):
    """
    Record an administrative or operational event into AuditLog.
    action_type: 'info', 'success', 'warning', 'danger'
    """
    try:
        ip = ip_address
        if not ip and request and hasattr(request, "client") and request.client:
            ip = request.client.host
        if not ip:
            ip = "127.0.0.1"

        user_id = user.id if user and hasattr(user, "id") else None
        username = user.username if user and hasattr(user, "username") else "admin"
        user_full_name = user.full_name if user and hasattr(user, "full_name") else "មន្ត្រីរដ្ឋបាល"
        user_role = user.role if user and hasattr(user, "role") else "admin"

        log = AuditLog(
            user_id=user_id,
            username=username,
            user_full_name=user_full_name,
            user_role=user_role,
            action=action,
            action_type=action_type,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            description=description,
            ip_address=ip,
            created_at=get_cambodia_now()
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Failed to write audit log: {e}")
