"""Router de autenticação."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel

from config.settings import ADMINS, get_secret
from core.auth import verify_pin

router = APIRouter()

# Configuração JWT
SECRET_KEY = get_secret("jwt_secret") or "gnr-escala-secret-2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    user_nome: str
    is_admin: bool


class TokenData(BaseModel):
    user_id: Optional[str] = None


def criar_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def obter_user_atual(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


def obter_admin(current_user: dict = Depends(obter_user_atual)) -> dict:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login só por PIN — percorre todos os utilizadores e encontra o match."""
    try:
        from services.data_loader_factory import get_data_loader
        loader = get_data_loader()
        df_util = loader.carregar_usuarios()
    except Exception:
        raise HTTPException(status_code=503, detail="Erro ao ligar ao servidor")

    if df_util.empty:
        raise HTTPException(status_code=503, detail="Erro ao carregar utilizadores")

    pin_input = form_data.username.strip() or form_data.password.strip()

    # Percorrer todos os utilizadores e verificar o PIN
    row_match = None
    for _, row in df_util.iterrows():
        pin_hash = str(row.get("pin", "")).strip()
        if not pin_hash or pin_hash == "nan":
            continue
        if verify_pin(pin_input, pin_hash):
            row_match = row
            break

    if row_match is None:
        raise HTTPException(status_code=401, detail="PIN incorreto")

    user_id = str(row_match.get("id", "")).strip()
    user_nome = str(row_match.get("nome", "")).strip()
    user_email = str(row_match.get("email", "")).strip()
    is_admin = user_email.lower() in {a.lower() for a in ADMINS}

    token = criar_token({
        "sub": user_id,
        "nome": user_nome,
        "email": user_email,
        "is_admin": is_admin,
    })

    return Token(
        access_token=token,
        token_type="bearer",
        user_id=user_id,
        user_nome=user_nome,
        is_admin=is_admin,
    )


@router.get("/me")
async def me(current_user: dict = Depends(obter_user_atual)):
    """Devolve info do utilizador autenticado."""
    return {
        "user_id": current_user.get("sub"),
        "nome": current_user.get("nome"),
        "email": current_user.get("email"),
        "is_admin": current_user.get("is_admin", False),
    }
