"""模型管理 API —— 模型列表、切换、配置、测试连接。"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.model_manager import ModelManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["模型管理"])

model_manager = ModelManager()


# ── 请求模型 ─────────────────────────────────────────────

class SwitchModelRequest(BaseModel):
    model_id: str = Field(..., description="要切换到的模型 ID")


class ModelConfigRequest(BaseModel):
    id: str = Field(default="", description="更新已有模型时必填，新增时留空")
    name: str = Field(..., description="模型显示名称")
    provider: str = Field(default="自定义", description="厂商名称")
    base_url: str = Field(..., description="API 端点地址")
    model_name: str = Field(..., description="模型名")
    model_name_large: str = Field(default="", description="大模型名（用于质检）")
    api_key: str = Field(default="", description="API Key")


class TestConnectionRequest(BaseModel):
    base_url: str = Field(..., description="API 端点地址")
    api_key: str = Field(default="", description="API Key")
    model_name: str = Field(..., description="模型名")


# ── 端点 ─────────────────────────────────────────────────

@router.get("/list")
async def list_models():
    """获取所有可用模型列表（API Key 脱敏显示）。"""
    return {"models": model_manager.list_models(), "total": len(model_manager._providers)}


@router.get("/current")
async def get_current_model():
    """获取当前激活的模型配置。"""
    config = model_manager.get_active_config()
    if not config:
        raise HTTPException(status_code=404, detail="未找到激活的模型")
    # 脱敏 API Key
    api_key = config.get("api_key", "")
    if api_key and len(api_key) > 8:
        config["api_key"] = api_key[:4] + "****" + api_key[-4:]
    elif api_key:
        config["api_key"] = "****"
    config["has_api_key"] = bool(api_key)
    config["is_active"] = True
    return config


@router.post("/switch")
async def switch_model(body: SwitchModelRequest):
    """切换到指定的模型。"""
    try:
        config = model_manager.switch_model(body.model_id)
        api_key = config.get("api_key", "")
        if api_key and len(api_key) > 8:
            config["api_key"] = api_key[:4] + "****" + api_key[-4:]
        elif api_key:
            config["api_key"] = "****"
        config["has_api_key"] = bool(api_key)
        config["is_active"] = True
        return {"success": True, "current": config}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/config")
async def save_model_config(body: ModelConfigRequest):
    """保存或更新模型配置（含 API Key）。新增模型会自动切换为当前模型。"""
    try:
        is_new = not body.id
        config = model_manager.save_model_config(body.model_dump())
        if is_new:
            model_manager.switch_model(config["id"])
        return {"success": True, "model": config, "is_new": is_new}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/test")
async def test_connection(body: TestConnectionRequest):
    """测试模型连接是否正常。"""
    result = await model_manager.test_connection(body.model_dump())
    return result
