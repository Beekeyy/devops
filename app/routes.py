from typing import Optional
from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User, Chat, Message, chat_users
from app.database import get_db
from app.auth import hash_for_password, password_verification, access_token

app_router = APIRouter()
templates = Jinja2Templates(directory="templates")

async def get_current_user(request: Request, db: AsyncSession) -> Optional[User]:
    email = request.session.get("email")
    if not email:
        return None
    res = await db.execute(select(User).where(User.email == email))
    return res.scalar_one_or_none()

def require_login(user: Optional[User]):
    if not user:
        raise HTTPException(status_code=401, detail="Требуется вход в систему")

async def is_member(db: AsyncSession, chat_id: int, user_id: int) -> bool:
    res = await db.execute(
        select(chat_users).where(
            (chat_users.c.chat_id == chat_id) & (chat_users.c.user_id == user_id)
        )
    )
    return bool(res.first())

@app_router.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    user_email = request.session.get("email")
    return templates.TemplateResponse("home.html", {"request": request, "user_email": user_email})

@app_router.get("/signup", response_class=HTMLResponse)
async def signup_page(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app_router.post("/signup")
async def signup_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    exists = await db.execute(select(User).where(User.email == email))
    if exists.scalar_one_or_none():
        return templates.TemplateResponse(
            "signup.html",
            {"request": request, "error": "Email уже зарегистрирован"},
            status_code=400,
        )

    u = User(email=email, password=hash_for_password(password))
    db.add(u)
    await db.commit()

    request.session["email"] = email
    request.session["token"] = access_token({"sub": email})
    return RedirectResponse("/", status_code=303)

@app_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("signin.html", {"request": request})

@app_router.post("/login")
async def login_action(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(User).where(User.email == email))
    u = res.scalar_one_or_none()
    if not u or not password_verification(password, u.password):
        return templates.TemplateResponse(
            "signin.html",
            {"request": request, "error": "Неверные email или пароль"},
            status_code=400,
        )

    request.session["email"] = email
    request.session["token"] = access_token({"sub": email})
    return RedirectResponse("/", status_code=303)

@app_router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)

@app_router.get("/chats", response_class=HTMLResponse)
async def list_chats(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    require_login(user)

    q = (
        select(Chat)
        .join(chat_users, chat_users.c.chat_id == Chat.id, isouter=True)
        .join(User, isouter=True)
        .where((chat_users.c.user_id == user.id) | (Chat.owner_id == user.id))
        .distinct()
        .order_by(Chat.id.desc())
    )
    chats = (await db.execute(q)).scalars().all()
    return templates.TemplateResponse(
        "chats.html",
        {
            "request": request,
            "user_email": user.email,
            "user_id": user.id,
            "chats": chats,
        },
    )

@app_router.post("/chats/create")
async def create_chat(
    request: Request,
    name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    require_login(user)

    chat = Chat(name=name.strip(), owner_id=user.id)
    db.add(chat)
    await db.flush()

    await db.execute(chat_users.insert().values(chat_id=chat.id, user_id=user.id))

    await db.commit()
    return RedirectResponse(f"/chats/{chat.id}", status_code=303)

@app_router.get("/chats/{chat_id}", response_class=HTMLResponse)
async def chat_detail(
    request: Request,
    chat_id: int,
    db: AsyncSession = Depends(get_db),
    error: Optional[str] = None,
):
    user = await get_current_user(request, db)
    require_login(user)

    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    member = await is_member(db, chat_id, user.id)
    if not member and chat.owner_id != user.id:
        return RedirectResponse("/chats", status_code=303)

    msgs = (
        await db.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
        )
    ).scalars().all()

    participants = (
        await db.execute(
            select(User)
            .join(chat_users, chat_users.c.user_id == User.id)
            .where(chat_users.c.chat_id == chat_id)
            .order_by(User.email.asc())
        )
    ).scalars().all()

    return templates.TemplateResponse(
        "chat_detail.html",
        {
            "request": request,
            "user_email": user.email,
            "user_id": user.id,
            "chat": chat,
            "messages": msgs,
            "participants": participants,
            "is_owner": chat.owner_id == user.id,
            "error": error,
        },
    )

@app_router.post("/chats/{chat_id}/message")
async def send_message(
    request: Request,
    chat_id: int,
    content: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    require_login(user)

    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    member = await is_member(db, chat_id, user.id)
    if not member and chat.owner_id != user.id:
        return RedirectResponse("/chats", status_code=303)

    text = content.strip()
    if text:
        msg = Message(chat_id=chat_id, user_id=user.id, content=text)
        db.add(msg)
        await db.commit()
    return RedirectResponse(f"/chats/{chat_id}", status_code=303)

@app_router.post("/chats/{chat_id}/join")
async def join_chat(
    request: Request,
    chat_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    require_login(user)

    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    if not await is_member(db, chat_id, user.id):
        await db.execute(chat_users.insert().values(chat_id=chat_id, user_id=user.id))
        await db.commit()

    return RedirectResponse(f"/chats/{chat_id}", status_code=303)

@app_router.post("/chats/{chat_id}/invite")
async def invite_user(
    request: Request,
    chat_id: int,
    email: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    require_login(user)

    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    member = await is_member(db, chat_id, user.id)
    if not member and chat.owner_id != user.id:
        return RedirectResponse("/chats", status_code=303)

    target_res = await db.execute(select(User).where(User.email == email.strip()))
    target = target_res.scalar_one_or_none()
    if not target:
        msgs = (
            await db.execute(
                select(Message).where(Message.chat_id == chat_id).order_by(Message.created_at.asc())
            )
        ).scalars().all()
        participants = (
            await db.execute(
                select(User)
                .join(chat_users, chat_users.c.user_id == User.id)
                .where(chat_users.c.chat_id == chat_id)
                .order_by(User.email.asc())
            )
        ).scalars().all()
        return templates.TemplateResponse(
            "chat_detail.html",
            {
                "request": request,
                "user_email": user.email,
                "user_id": user.id,
                "chat": chat,
                "messages": msgs,
                "participants": participants,
                "is_owner": chat.owner_id == user.id,
                "error": "Пользователь с таким email не найден",
            },
            status_code=400,
        )

    if not await is_member(db, chat_id, target.id):
        await db.execute(chat_users.insert().values(chat_id=chat_id, user_id=target.id))
        await db.commit()

    return RedirectResponse(f"/chats/{chat_id}", status_code=303)

@app_router.post("/chats/{chat_id}/delete")
async def delete_chat(
    request: Request,
    chat_id: int,
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user(request, db)
    require_login(user)

    chat = await db.get(Chat, chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")

    if chat.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Только владелец может удалить чат")

    await db.execute(delete(Message).where(Message.chat_id == chat_id))
    await db.execute(delete(chat_users).where(chat_users.c.chat_id == chat_id))
    await db.delete(chat)
    await db.commit()

    return RedirectResponse("/chats", status_code=303)