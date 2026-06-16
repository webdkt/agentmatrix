"""
Session management routes: sessions, emails, attachments, mark-read, select, subject.
"""

import asyncio
from pathlib import Path
from typing import Optional, List
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Form, File, UploadFile, Request
from fastapi.responses import Response, FileResponse

from ..state import server_state

router = APIRouter()


@router.get("/api/sessions")
async def get_sessions(page: int = 1, per_page: int = 20):
    """Get user's email sessions"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    per_page = min(per_page, 100)

    user_agent_name = server_state.matrix_runtime.get_user_agent_name()

    result = await server_state.matrix_runtime.post_office.email_db.get_user_sessions(
        user_agent_name=user_agent_name,
        page=page,
        per_page=per_page,
    )

    sessions = []
    for conv in result["sessions"]:
        sessions.append(
            {
                "session_id": conv["session_id"],
                "agent_name": conv.get("agent_name"),
                "agent_session_id": conv.get("agent_session_id"),
                "task_id": conv.get("task_id"),
                "subject": conv["subject"],
                "last_email_time": conv["last_email_time"],
                "participants": conv["participants"],
                "is_unread": conv.get("is_unread", False),
                "last_email_id": conv.get("last_email_id"),
            }
        )

    return {
        "success": True,
        "sessions": sessions,
        "total": result["total"],
        "page": result["page"],
        "per_page": result["per_page"],
        "total_pages": result["total_pages"],
    }


@router.post("/api/sessions/{session_id}/emails")
async def send_email(
    session_id: str,
    task_id: Optional[str] = Form(None),
    recipient: str = Form(...),
    subject: Optional[str] = Form(""),
    body: str = Form(...),
    in_reply_to: Optional[str] = Form(None),
    recipient_session_id: Optional[str] = Form(None),
    attachments: List[UploadFile] = File(default=[]),
):
    """Send an email with attachments (new session or reply)"""
    print(
        f"📧 Received email request: recipient={recipient}, subject={subject}, body_length={len(body)}, attachments={len(attachments)}"
    )

    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    user_agent_name = server_state.matrix_runtime.get_user_agent_name()
    user_agent = server_state.matrix_runtime.agents.get(user_agent_name)
    if not user_agent:
        raise HTTPException(
            status_code=404, detail=f"User agent '{user_agent_name}' not found"
        )

    effective_task_id = task_id
    if effective_task_id is None:
        if session_id == "new":
            import uuid
            effective_task_id = str(uuid.uuid4())
            print(f"📧 New session: generated task_id={effective_task_id}")
        else:
            effective_task_id = session_id
            print(
                f"📧 Reply: using task_id={effective_task_id}, in_reply_to={in_reply_to}"
            )
    else:
        print(f"📧 Using provided task_id={effective_task_id}")

    if not effective_task_id or effective_task_id in ("null", "undefined", "None"):
        raise HTTPException(
            status_code=400, detail=f"Invalid task_id: {effective_task_id}"
        )

    attachment_metadata = []
    if attachments:
        user_attachments_dir = user_agent.runtime.paths.get_agent_attachments_dir(
            user_agent.name, effective_task_id
        )
        user_attachments_dir.mkdir(parents=True, exist_ok=True)

        recipient_agent_name = recipient
        if recipient != user_agent_name:
            try:
                recipient_attachments_dir = (
                    user_agent.runtime.paths.get_agent_attachments_dir(
                        recipient_agent_name, effective_task_id
                    )
                )
                recipient_attachments_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                recipient_attachments_dir = None
                print(f"⚠️ 无法获取收件人 {recipient_agent_name} 的附件目录: {e}")
        else:
            recipient_attachments_dir = None

        for attachment in attachments:
            try:
                content = await attachment.read()
                filename = attachment.filename or "unnamed"

                user_file_path = user_attachments_dir / filename

                def save_file():
                    with open(user_file_path, "wb") as f:
                        f.write(content)

                await asyncio.to_thread(save_file)

                if recipient_attachments_dir is not None:
                    import shutil
                    recipient_file_path = recipient_attachments_dir / filename

                    def copy_file():
                        shutil.copy2(user_file_path, recipient_file_path)

                    await asyncio.to_thread(copy_file)
                    print(
                        f"✅ Attachment copied to recipient: {filename} -> {recipient_file_path}"
                    )

                attachment_metadata.append(
                    {
                        "filename": filename,
                        "size": len(content),
                        "container_path": f"~/current_task/attachments/{filename}",
                    }
                )
                print(
                    f"✅ Attachment saved: {filename} ({len(content)} bytes) -> {user_file_path}"
                )
            except Exception as e:
                print(f"❌ Failed to save attachment {attachment.filename}: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Failed to save attachment: {str(e)}"
                )

    effective_session_id = session_id
    if session_id == "new":
        effective_session_id = effective_task_id
        print(f"📧 New session: using session_id={effective_session_id}")
    else:
        effective_session_id = session_id
        print(f"📧 Reply: using session_id={effective_session_id}")

    new_email = await user_agent.speak(
        session_id=effective_session_id,
        task_id=effective_task_id,
        to=recipient,
        subject=subject,
        content=body,
        reply_to_id=in_reply_to,
        recipient_session_id=recipient_session_id,
        attachments=attachment_metadata if attachment_metadata else None,
    )

    email_dict = {
        "id": new_email.id,
        "timestamp": new_email.timestamp.isoformat()
        if hasattr(new_email.timestamp, "isoformat")
        else str(new_email.timestamp),
        "sender": new_email.sender,
        "recipient": new_email.recipient,
        "subject": new_email.subject,
        "body": new_email.body,
        "in_reply_to": new_email.in_reply_to,
        "task_id": new_email.task_id,
        "recipient_session_id": new_email.recipient_session_id,
        "sender_session_id": new_email.sender_session_id,
        "is_from_user": True,
        "attachments": new_email.attachments or [],
    }

    return {
        "success": True,
        "task_id": new_email.task_id,
        "message": "Email sent successfully",
        "attachments_count": len(attachment_metadata),
        "email": email_dict,
    }


@router.get("/api/sessions/{session_id}/emails")
async def get_session_emails(session_id: str):
    """Get all emails for a specific session"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        emails = await server_state.matrix_runtime.post_office.get_session_emails_for_user(session_id)

        emails_data = []
        for email in emails:
            emails_data.append(
                {
                    "id": email.id,
                    "timestamp": email.timestamp.isoformat()
                    if hasattr(email.timestamp, "isoformat")
                    else str(email.timestamp),
                    "sender": email.sender,
                    "recipient": email.recipient,
                    "subject": email.subject,
                    "body": email.body,
                    "in_reply_to": email.in_reply_to,
                    "task_id": email.task_id,
                    "recipient_session_id": email.recipient_session_id,
                    "is_from_user": getattr(email, "is_from_user", False),
                    "attachments": email.attachments,
                }
            )

        await server_state.matrix_runtime.post_office.email_db.mark_session_as_read(session_id)

        return {"success": True, "emails": emails_data, "total_count": len(emails_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/sessions/{session_id}/mark-read")
async def mark_session_read(session_id: str):
    """Mark a user session as read by updating check time"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        await server_state.matrix_runtime.post_office.email_db.update_check_time(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/sessions/{session_id}/select")
async def select_session(session_id: str):
    """User selects a session - update check time"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        await server_state.matrix_runtime.post_office.email_db.update_check_time(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/sessions/{session_id}/subject")
async def update_session_subject(session_id: str, request: Request):
    """Update session subject"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        data = await request.json()
        new_subject = data.get("subject", "").strip()

        await server_state.matrix_runtime.post_office.email_db.update_user_session(
            user_session_id=session_id,
            subject=new_subject if new_subject else None,
        )

        return {"success": True, "subject": new_subject}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/sessions/{session_id}/emails/{email_id}/attachments/{filename}")
async def download_email_attachment(session_id: str, email_id: str, filename: str):
    """Download an attachment from an email"""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")

    try:
        emails = await server_state.matrix_runtime.post_office.get_session_emails_for_user(session_id)
        target_email = None
        for email in emails:
            if email.id == email_id:
                target_email = email
                break

        if not target_email:
            raise HTTPException(status_code=404, detail="Email not found")

        recipient_name = target_email.recipient
        task_id = target_email.task_id

        recipient_agent = server_state.matrix_runtime.agents.get(recipient_name)
        if not recipient_agent:
            raise HTTPException(
                status_code=404, detail=f"Agent not found: {recipient_name}"
            )

        attachment_path = (
            recipient_agent.runtime.paths.get_agent_attachments_dir(
                recipient_name, task_id
            )
            / filename
        )

        if not attachment_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Attachment not found: {filename}"
            )

        file_ext = Path(filename).suffix.lower()

        previewable_extensions = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".json": "application/json",
            ".xml": "application/xml",
            ".html": "text/html",
            ".css": "text/css",
            ".js": "application/javascript",
            ".pdf": "application/pdf",
            ".svg": "image/svg+xml",
        }

        image_extensions = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }

        all_previewable = {**previewable_extensions, **image_extensions}

        if file_ext in all_previewable:
            media_type = all_previewable[file_ext]

            def read_file():
                with open(attachment_path, "rb") as f:
                    return f.read()

            file_content = await asyncio.to_thread(read_file)
            encoded_filename = quote(filename, safe="")

            return Response(
                content=file_content,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"inline; filename*=UTF-8''{encoded_filename}"
                },
            )
        else:
            return FileResponse(
                path=str(attachment_path),
                filename=filename,
                media_type="application/octet-stream",
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/sessions/by-agent/{agent_session_id}")
async def get_session_by_agent_session(agent_session_id: str):
    """Look up a user session by the agent's session_id."""
    if not server_state.matrix_runtime:
        raise HTTPException(status_code=503, detail="Runtime not initialized")
    try:
        row = await server_state.matrix_runtime.post_office.email_db.get_user_session_by_agent_session(
            agent_session_id
        )
        if not row:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "success": True,
            "session": {
                "session_id": row["user_session_id"],
                "agent_name": row.get("agent_name"),
                "agent_session_id": row.get("agent_session_id"),
                "task_id": row.get("task_id"),
                "subject": row.get("subject"),
                "last_email_id": row.get("last_email_id"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get a specific session"""
    return {"session_id": session_id, "messages": []}
