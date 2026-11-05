from pydantic import BaseModel, ConfigDict, EmailStr, Field
class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    learning_level: str = "beginner"
    goals: list[str] = Field(default_factory=list)
    learning_style: str | None = None
    interests: list[str] = Field(default_factory=list)
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
class UserInfo(BaseModel):
    id: int
    email: EmailStr
    role: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)
class StudentProfileInfo(BaseModel):
    id: int
    full_name: str | None
    learning_level: str
    learning_goals: list[str]
    learning_style: str | None
    interests: list[str]
    model_config = ConfigDict(from_attributes=True)
class RegisterResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    profile: StudentProfileInfo
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserInfo
    profile: StudentProfileInfo
class MeResponse(BaseModel):
    user: UserInfo
    profile: StudentProfileInfo | None = None
