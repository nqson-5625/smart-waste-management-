"""Request/response models for /devices, /devices/{id}/configs and /bins/{id}/assignments."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .bins_schemas import ID_PATTERN


DEVICE_ID_PATTERN = r"^bin-[0-9]{3,6}$"
GATEWAY_ID_PATTERN = r"^gw-[a-zA-Z0-9-]{1,24}$"


class SensorIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sensor_id: str = Field(min_length=1, max_length=80, pattern=ID_PATTERN)
    type: Literal["ultrasonic", "lid_switch"]
    model: str = Field(min_length=1, max_length=60)


class DeviceCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(pattern=DEVICE_ID_PATTERN, description="Dạng bin-001, 3 đến 6 chữ số")
    hardware_model: str = Field(min_length=1, max_length=80)
    firmware_version: str = Field(min_length=1, max_length=30)
    gateway_ids: list[str] = Field(min_length=1, max_length=8)
    sensors: list[SensorIn] = Field(min_length=1, max_length=8)
    serial_number: str | None = Field(None, min_length=1, max_length=100)
    notes: str | None = Field(None, min_length=1, max_length=1000)

    @field_validator("gateway_ids")
    @classmethod
    def valid_gateways(cls, value):
        bad =[gateway for gateway in value if not re.match(GATEWAY_ID_PATTERN, gateway)]
        if bad:
            raise ValueError(f"mã gateway không hợp lệ: {', '.join(bad)} (dạng gw-001)")
        if len(set(value)) != len(value):
            raise ValueError("gateway_ids bị lặp")
        return value

    @field_validator("sensors")
    @classmethod
    def one_ultrasonic(cls, value):
        if len({sensor.sensor_id for sensor in value}) != len(value):
            raise ValueError("sensor_id bị lặp")
        if not any(sensor.type == "ultrasonic" for sensor in value):
            raise ValueError("cần ít nhất một cảm biến siêu âm (ultrasonic)")
        return value


class SensorOut(BaseModel):
    sensor_id: str
    type: str
    model: str
    status: str


class DeviceOut(BaseModel):
    id: str
    hardware_model: str
    serial_number: str | None
    firmware_version: str
    gateway_ids: list[str]
    enabled: bool
    lifecycle: Literal["stock", "installed", "maintenance", "retired"]
    applied_config_rev: int | None
    sensors: list[SensorOut]
    commissioned_at: str
    notes: str | None


class ConfigCreate(BaseModel):
    config_rev: int = Field(ge=1, le=65535, description="Phải trùng giá trị đang nạp trên node")
    empty_distance_mm: int = Field(ge=21, le=4000, description="Khoảng cách khi thùng rỗng")
    full_distance_mm: int = Field(ge=20, le=3999, description="Khoảng cách khi thùng đầy")
    sample_interval_s: int = Field(60, ge=5, le=86400)
    report_interval_s: int = Field(21600, ge=5, le=604800)
    note: str | None = Field(None, min_length=1, max_length=1000)

    @model_validator(mode="after")
    def consistent(self):
        if self.full_distance_mm >= self.empty_distance_mm:
            raise ValueError("full_distance_mm phải nhỏ hơn empty_distance_mm")
        if self.report_interval_s < self.sample_interval_s:
            raise ValueError("report_interval_s phải lớn hơn hoặc bằng sample_interval_s")
        return self


class ConfigOut(BaseModel):
    id: str
    device_id: str
    config_rev: int
    sensor_id: str
    empty_distance_mm: int
    full_distance_mm: int
    sample_interval_s: int
    report_interval_s: int
    full_threshold_pct: int
    clear_threshold_pct: int
    confirm_cycles: int
    status: Literal["draft", "verified"]
    verified_at: str | None
    note: str | None
    requeued_messages: int = Field(description="Số bản tin đang bị chặn được đưa lại hàng đợi")


class AssignmentCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    device_id: str = Field(pattern=DEVICE_ID_PATTERN)
    reason: str = Field(min_length=1, max_length=300)


class AssignmentOut(BaseModel):
    id: str
    bin_id: str
    device_id: str
    assignment_version: int
    installed_at: str
    reason: str
    replaced_device_id: str | None = Field(description="Thiết bị cũ vừa được tháo, nếu có")
