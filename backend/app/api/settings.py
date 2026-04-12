from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.models import AppSettings
from pydantic import BaseModel

router = APIRouter()


class SettingsResponse(BaseModel):
    nif_api_enabled: bool


class SettingsUpdate(BaseModel):
    nif_api_enabled: bool


def get_setting(db: Session, key: str, default: str = "true") -> str:
    """Get a setting value from database, create if not exists"""
    setting = db.query(AppSettings).filter(AppSettings.key == key).first()
    if not setting:
        setting = AppSettings(key=key, value=default)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting.value


def set_setting(db: Session, key: str, value: str) -> None:
    """Update or create a setting"""
    setting = db.query(AppSettings).filter(AppSettings.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = AppSettings(key=key, value=value)
        db.add(setting)
    db.commit()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    """Get application settings"""
    nif_api_enabled = get_setting(db, "nif_api_enabled", "true") == "true"
    
    return SettingsResponse(nif_api_enabled=nif_api_enabled)


@router.post("/settings", response_model=SettingsResponse)
async def update_settings(
    settings: SettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update application settings"""
    set_setting(db, "nif_api_enabled", "true" if settings.nif_api_enabled else "false")
    
    return SettingsResponse(nif_api_enabled=settings.nif_api_enabled)
