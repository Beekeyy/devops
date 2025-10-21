Готовый проект включающий в себя:
    Микросервис website – функционал управления пользователями, комнатами;
    Микросервис chat – функционал Websocket чатов;
    База данных;
    Веб-сервер.

## Как запустить

```bash
cd website
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Как пользоваться

Откройте: http://127.0.0.1:8000

- Зарегистрируйтесь, войдите
- Перейдите в «Чаты», создайте чат, приглашайте участников по email зарегистрированных пользователей

## Структура

website/
|- app/
│  |- __init__.py
│  |- main.py
│  |- database.py
│  |- models.py
│  |- routes.py
│  |- auth.py
|
|- templates/
│  |- base.html
│  |- home.html
│  |- signin.html
│  |- signup.html
│  |- chats.html
│  |- chat_detail.html
│  |- static/
│     |- style.css
|
|- requirements.txt
|- .env