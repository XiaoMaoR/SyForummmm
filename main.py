from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from email_api import send_email, verify_code
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi.staticfiles import StaticFiles
import shutil
import uvicorn
import hashlib
import db_utils
import uuid
import json
import jwt
import os

SECRET_KEY = "key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440
UADATABASE = "db/agreements.db"
FMDATABASE = "db/SyForummmm.db"

verify_code_list = []
request_log = {}
security = HTTPBearer()
app = FastAPI(max_request_size=256 * 1024 * 1024)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/app", StaticFiles(directory="app"), name="app")
ua_conn = db_utils.create_connection(UADATABASE)
if ua_conn is not None:
    db_utils.create_table(ua_conn)
else:
    raise RuntimeError("无法连接到用户协议数据库")
fm_conn = db_utils.create_connection(FMDATABASE)
if fm_conn is not None:
    db_utils.create_forum_table(fm_conn)
else:
    raise RuntimeError("无法连接到论坛数据库")

class Agreement(BaseModel):
    qq: str
    agreement: str

class ForumPost(BaseModel):
    qq: str
    title: str
    text: str
    other: str | None = None
    anonymous :bool | None = False

class Comment(BaseModel):
    id: int
    qq: str
    text: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        qq = payload.get("sub")
        if not qq:
            raise HTTPException(status_code=400, detail="token 中缺少 QQ 信息")
        return qq
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=401,
            detail="无效或过期的令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.get("/api/getlist/{page}")
async def get_list(page: int):
    if fm_conn is None:
        raise HTTPException(status_code=500, detail="数据库错误")
    cur = fm_conn.cursor()
    offset = (page - 1) * 10
    cur.execute("SELECT id, data FROM forum_data ORDER BY id DESC LIMIT 10 OFFSET ?", (offset,))
    rows = cur.fetchall()
    return {
        "status": "success",
        "data": [{"id": row[0], "title": json.loads(row[1])["title"]} for row in rows]
    }

@app.post("/api/post")
async def post_up(*, token_payload: dict = Depends(verify_token), post: ForumPost):
    if token_payload != post.qq:
        raise HTTPException(status_code=403, detail="神经病吧，验证用的什么你就填什么qq还想伪造咋地，要几把干啥，我一个人全站容易吗我请问呢，这个破学校也没人会，我真的要破防了，大半夜还要写这个验证，还不是怕你们瞎搞我真的服了哈，能不能别让主播担心，这个墙跟死了似的，受不了。")
    post_data = {
        "qq": post.qq,
        "anyonymous": post.anonymous,
        "title": post.title,
        "text": post.text,
        "other": post.other,
        "pinned": False,
        "comment":[],
        "timestamp": datetime.now().timestamp(),
    }
    if fm_conn is None:
        raise HTTPException(status_code=500, detail="数据库错误")
    db_utils.insert_forum_data(fm_conn, post_data)
    return {"status": "success", "user_info": token_payload}

@app.post("/api/comment")
async def comment(comment: Comment, token_payload: dict = Depends(verify_token)):
    if token_payload != comment.qq:
        raise HTTPException(status_code=403, detail="神经病吧，验证用的什么你就填什么qq还想伪造咋地，要几把干啥，我一个人全站容易吗我请问呢，这个破学校也没人会，我真的要破防了，大半夜还要写这个验证，还不是怕你们瞎搞我真的服了哈，能不能别让主播担心，这个墙跟死了似的，受不了。")
    comment_data = {
        "qq": comment.qq,
        "text": comment.text,
        "timestamp": datetime.now().timestamp(),
    }
    if fm_conn is None:
        raise HTTPException(status_code=500, detail="数据库错误")
    post_data = db_utils.get_forum_data(fm_conn, comment.id)
    if not post_data:
        raise HTTPException(status_code=404, detail="帖子不存在")
    post_data["comment"].append(comment_data)
    db_utils.update_forum_data(fm_conn, comment.id, post_data)
    return {"status": "success"}

@app.get("/api/getinfo/{id}")
async def get_info(id: int):
    if fm_conn is None:
        raise HTTPException(status_code=500, detail="数据库错误")
    data = db_utils.get_forum_data(fm_conn,id)
    if not data:
        raise HTTPException(status_code=404, detail="数据不存在")
    if data["anyonymous"] == True:
        data["qq"] = "匿名"
    return {"status": "success","data": data}

@app.get("/api/send_qqverify")
async def send_qqverify(request: Request, qq: str):
    now = datetime.now()
    client_ip = request.headers.get("X-Real-IP", "unknown")
    if client_ip not in request_log:
        request_log[client_ip] = []
    request_log[client_ip] = [timestamp for timestamp in request_log[client_ip] if now - timestamp < timedelta(days=1)]
    if len(request_log[client_ip]) >= 15:
        raise HTTPException(status_code=400, detail="今天的请求次数已达到上限（15次）")
    if request_log[client_ip] and now - request_log[client_ip][-1] < timedelta(seconds=60):
        raise HTTPException(status_code=400, detail="请求频率过高，请稍后再试")
    code = verify_code()
    expiration_time = now + timedelta(minutes=10)
    request_log[client_ip].append(now)
    verify_code_list.append({
        "qq": qq,
        "code": code,
        "expiration_time": expiration_time
    })
    send_email(f"{qq}@qq.com", code)
    return {"status": "success"}

@app.get("/api/qqverify")
async def qqverify(qq: str, code: str):
    record = next((item for item in verify_code_list if item["qq"] == qq and item["code"] == code), None)
    if not record:
        raise HTTPException(status_code=404, detail="验证码无效或不存在")
    if record["expiration_time"] < datetime.now():
        verify_code_list.remove(record)
        raise HTTPException(status_code=400, detail="验证码已过期")
    verify_code_list.remove(record)
    access_token = create_access_token(data={"sub": qq})
    return {"status": "success", "access_token": access_token, "token_type": "bearer"}

@app.get("/api/jwtok~喵喵喵")
async def jwtok(request: Request, token_payload: dict = Depends(verify_token)):
    if token_payload == None:
        return "拒签！！！"
    return "闺蜜闺蜜你的验证通过了~~~"

@app.post("/api/agreement")
async def agreement(agreement: Agreement, request: Request, token_payload: dict = Depends(verify_token)):
    if token_payload != agreement.qq:
        raise HTTPException(status_code=403, detail="神经病吧，验证用的什么你就填什么qq还想伪造咋地，要几把干啥，我一个人全站容易吗我请问呢，这个破学校也没人会，我真的要破防了，大半夜还要写这个验证，还不是怕你们瞎搞我真的服了哈，能不能别让主播担心，这个墙跟死了似的，受不了。")
    if  agreement.agreement != "8e827c5e08281a2e1051d6cebe6d31f1b73a6e9d897dc8631bac2abaddf667e6":
        raise HTTPException(status_code=429, detail="提交协议错误")
    user_agent = request.headers.get("user-agent", "unknown")
    user_agreement = {
        "timestamp": datetime.now().timestamp(),
        "qq": agreement.qq,
        "agreement": agreement.agreement,
        "ua": user_agent,
        "ip": request.headers.get("X-Real-IP", "unknown")
    }
    user_agreement_hash = hashlib.sha256(str(user_agreement).encode("utf-8")).hexdigest()
    if ua_conn is None:
        raise HTTPException(status_code=500, detail="数据库错误")
    agreement_id = db_utils.insert_agreement(ua_conn, {"hash": user_agreement_hash,"record": user_agreement})
    if agreement_id is None:
        raise HTTPException(status_code=500, detail="无法保存")
    return {
        "hash": user_agreement_hash,
        "record": user_agreement,
        "id": agreement_id
    }

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), token_payload: dict = Depends(verify_token)):
    if token_payload == None:
        raise HTTPException(status_code=403, detail="懒得喷，请先验证")
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名无效")
    _, ext = os.path.splitext(file.filename)
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join("static/temp", unique_filename)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return {
            "status": "success",
            "filename": unique_filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="文件上传失败")

@app.get("/", response_class=HTMLResponse)
async def index_page():
    with open("app/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/info/{id}", response_class=HTMLResponse)
async def info_page(id: str):
    with open("app/info.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/post", response_class=HTMLResponse)
async def post_page():
    with open("app/post.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/token", response_class=HTMLResponse)
async def token_page():
    with open("app/token.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

uvicorn.run(app, host="127.0.0.1", port=8001)
