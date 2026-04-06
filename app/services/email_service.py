import os
try:
    import resend
except ModuleNotFoundError:  # pragma: no cover - depende del entorno
    resend = None


def _get_resend_client():
    if resend is None:
        return None
    resend.api_key = (os.getenv("RESEND_API_KEY") or "").strip()
    return resend


def send_verification_email(to_email: str, verify_url: str):
    client = _get_resend_client()
    from_email = (os.getenv("MAIL_DEFAULT_SENDER") or "").strip()

    if client is None:
        raise RuntimeError("Proveedor de correo no disponible (resend no instalado).")

    if not client.api_key:
        raise RuntimeError("RESEND_API_KEY no está configurada.")

    if not from_email:
        raise RuntimeError("MAIL_DEFAULT_SENDER no está configurado.")

    params = {
        "from": f"CoyoLabs <{from_email}>",
        "to": [to_email],
        "subject": "Verifica tu cuenta - Sistema de Laboratorios",
        "html": f"""
        <div style="font-family: Arial, sans-serif; color: #111; line-height: 1.6;">
            <h2 style="margin-bottom: 8px;">CoyoLabs</h2>
            <p>Hola.</p>
            <p>Para activar tu cuenta institucional, haz clic en el siguiente botón:</p>
            <p>
                <a href="{verify_url}"
                   style="display:inline-block;padding:12px 20px;background:#03A9F4;color:#fff;text-decoration:none;border-radius:8px;">
                   Verificar cuenta
                </a>
            </p>
            <p>Si el botón no funciona, abre este enlace:</p>
            <p><a href="{verify_url}">{verify_url}</a></p>
            <p>Este enlace expira en 1 hora.</p>
        </div>
        """,
        "text": (
            "Hola.\n\n"
            "Para activar tu cuenta institucional, abre este enlace:\n\n"
            f"{verify_url}\n\n"
            "Este enlace expira en 1 hora.\n"
        ),
    }

    return client.Emails.send(params)


def send_password_reset_email(to_email: str, reset_url: str):
    client = _get_resend_client()
    from_email = (os.getenv("MAIL_DEFAULT_SENDER") or "").strip()

    if client is None:
        raise RuntimeError("Proveedor de correo no disponible (resend no instalado).")

    if not client.api_key:
        raise RuntimeError("RESEND_API_KEY no está configurada.")

    if not from_email:
        raise RuntimeError("MAIL_DEFAULT_SENDER no está configurado.")

    params = {
        "from": f"CoyoLabs <{from_email}>",
        "to": [to_email],
        "subject": "Recuperación de contraseña - CoyoLabs",
        "html": f"""
        <div style="font-family: Arial, sans-serif; color: #111; line-height: 1.6;">
            <h2 style="margin-bottom: 8px;">CoyoLabs</h2>
            <p>Recibimos una solicitud para restablecer tu contraseña.</p>
            <p>Haz clic en el siguiente botón para crear una nueva contraseña:</p>
            <p>
                <a href="{reset_url}"
                   style="display:inline-block;padding:12px 20px;background:#03A9F4;color:#fff;text-decoration:none;border-radius:8px;">
                   Restablecer contraseña
                </a>
            </p>
            <p>Si el botón no funciona, abre este enlace:</p>
            <p><a href="{reset_url}">{reset_url}</a></p>
            <p>Este enlace expira en 1 hora.</p>
            <p>Si no solicitaste este cambio, ignora este mensaje.</p>
        </div>
        """,
        "text": (
            "Recibimos una solicitud para restablecer tu contraseña.\n\n"
            "Abre este enlace para crear una nueva contraseña:\n\n"
            f"{reset_url}\n\n"
            "Este enlace expira en 1 hora.\n"
            "Si no solicitaste este cambio, ignora este mensaje.\n"
        ),
    }

    return client.Emails.send(params)


def send_print3d_ready_email(to_email: str, *, job_id: int, job_title: str, jobs_url: str):
    client = _get_resend_client()
    from_email = (os.getenv("MAIL_DEFAULT_SENDER") or "").strip()

    if client is None:
        raise RuntimeError("Proveedor de correo no disponible (resend no instalado).")

    if not client.api_key:
        raise RuntimeError("RESEND_API_KEY no está configurada.")

    if not from_email:
        raise RuntimeError("MAIL_DEFAULT_SENDER no está configurado.")

    safe_title = (job_title or "").strip() or f"Trabajo #{job_id}"

    params = {
        "from": f"CoyoLabs <{from_email}>",
        "to": [to_email],
        "subject": "Tu impresión 3D está lista",
        "html": f"""
        <div style="font-family: Arial, sans-serif; color: #111; line-height: 1.6;">
            <h2 style="margin-bottom: 8px;">CoyoLabs</h2>
            <p>¡Tu trabajo de impresión 3D ya está listo para entrega!</p>
            <p><strong>Solicitud:</strong> #{job_id} - {safe_title}</p>
            <p>
                <a href="{jobs_url}"
                   style="display:inline-block;padding:12px 20px;background:#03A9F4;color:#fff;text-decoration:none;border-radius:8px;">
                   Ver mis impresiones 3D
                </a>
            </p>
            <p>También puedes revisar el estado directamente en:</p>
            <p><a href="{jobs_url}">{jobs_url}</a></p>
        </div>
        """,
        "text": (
            "Tu trabajo de impresión 3D ya está listo para entrega.\n\n"
            f"Solicitud: #{job_id} - {safe_title}\n\n"
            f"Consulta el detalle en: {jobs_url}\n"
        ),
    }

    return client.Emails.send(params)
