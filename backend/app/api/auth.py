import re
import secrets
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.models.student import User, StudentProfile
from app.core.security import (
    hash_password,
    create_access_token,
    verify_password,
)
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
)
from app.api.dependencies import get_db, get_current_user
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)
from app.schemas.auth import MeResponse
def generate_username(email: str, db: Session) -> str:
    """
    Generate an internal username from the email address.
    The student does not need to choose a username.
    """
    local_part = email.split("@")[0]
    base = re.sub(
        r"[^a-zA-Z0-9_]",
        "_",
        local_part,
    ).strip("_").lower()
    if not base:
        base = "student"
    base = base[:80]
    while True:
        username = f"{base}_{secrets.token_hex(8)}"
        existing = (
            db.query(User)
            .filter(User.username == username)
            .first()
        )
        if not existing:
            return username
@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=201,
)
def register_user(
    request: RegisterRequest,
    db: Session = Depends(get_db),
):
    # Normalize the email address.
    email = str(request.email).strip().lower()
    # Check whether this email is already registered.
    existing_user = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )
    if existing_user:
        raise HTTPException(
            status_code=409,
            detail="Email address is already registered",
        )
    # Generate an internal username.
    username = generate_username(email, db)
    # Hash the password before storing it.
    password_hash = hash_password(request.password)
    try:
        # Create the user account.
        new_user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role="student",
            is_active=True,
        )
        db.add(new_user)
        # Send the INSERT to PostgreSQL and obtain the user ID.
        db.flush()
        # Create the associated student profile.
        new_profile = StudentProfile(
            user_id=new_user.id,
            full_name=request.name.strip(),
            learning_level=request.learning_level,
            learning_goals=request.goals,
            learning_style=request.learning_style,
            interests=request.interests,
        )
        db.add(new_profile)
        # Save both records in one transaction.
        db.commit()
        db.refresh(new_user)
        db.refresh(new_profile)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Account could not be created. Please check whether this email is already registered.",
        )
    # Generate the access token.
    access_token = create_access_token(
        data={"sub": str(new_user.id)}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": new_user,
        "profile": new_profile,
    }
@router.post(
    "/login",
    response_model=LoginResponse,
)
def login_user(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    # Normalize the email address.
    email = str(request.email).strip().lower()
    # Find the account using email.
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )
    # Reject missing accounts and legacy accounts
    # that do not have password hashes.
    if not user or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Verify the supplied password against Argon2 hash.
    if not verify_password(
        request.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Reject disabled accounts.
    if not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Retrieve the associated student profile.
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == user.id)
        .first()
    )
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Student profile not found",
        )
    # Generate a JWT for the authenticated user.
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "profile": profile,
    }
@router.get(
    "/me",
    response_model=MeResponse,
)
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == current_user.id)
        .first()
    )
    return {
        "user": current_user,
        "profile": profile,
    }
