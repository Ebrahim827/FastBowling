"""
Auth: password hashing (bcrypt via passlib) + JWT tokens (python-jose).

IMPORTANT BEFORE GOING TO PRODUCTION:
- Change SECRET_KEY below to a long random value, and load it from an
  environment variable instead of hardcoding it in source - anyone who
  can read this file can otherwise forge tokens for any user.
- Consider a shorter ACCESS_TOKEN_EXPIRE_MINUTES for a production app,
  or add refresh tokens - 7 days is convenient for development/testing.
"""

import os
import datetime
import bcrypt
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db, User

SECRET_KEY = os.environ.get("BOWLING_APP_SECRET_KEY", "dev-only-change-this-before-deploying")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")


def hash_password(password: str) -> str:
    # Using the bcrypt library directly rather than passlib - passlib's
    # bcrypt compatibility shim has a known bug with newer bcrypt
    # versions (fails on password length detection). bcrypt truncates
    # at 72 bytes internally regardless, which is fine for a password.
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def require_coach(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "coach":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Coach access required")
    return current_user
