import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Registers a new user and issues a JWT bearer token."""
    existing_user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    user_id = f"user-{uuid.uuid4().hex[:8]}"
    avatar = payload.avatar or f"https://api.dicebear.com/7.x/bottts/svg?seed={payload.name.replace(' ', '')}"

    new_user = User(
        id=user_id,
        email=payload.email.lower().strip(),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role or "Engineer",
        avatar=avatar,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(data={"sub": new_user.id, "email": new_user.email})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticates user credentials and returns a JWT token."""
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(data={"sub": user.id, "email": user.email})

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Returns the authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.get("/demo-users", response_model=List[UserResponse])
def get_demo_users(db: Session = Depends(get_db)):
    """Returns list of pre-seeded team members for instant 1-click test signin."""
    users = db.query(User).all()
    return [UserResponse.model_validate(u) for u in users]
