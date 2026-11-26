"""Request bodies for /routes (docs/06 section 3.14)."""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from .bins_schemas import ID_PATTERN


RouteStatus = Literal["planned", "assigned", "in_progress", "completed", "cancelled"]
DATE_PATTERN = r"^\d{4}-\d{2}-\d{2}$"


class RouteStatusChange(BaseModel):
    status: Literal["assigned", "in_progress", "completed", "cancelled"]
    assigned_worker_id: str | None = Field(None, pattern=ID_PATTERN, max_length=80)
    actual_distance_m: float | None = Field(None, ge=0, le=1_000_000)
    actual_distance_source: Literal["odometer", "gps", "manual"] | None = None
    skip_reason: str | None = Field(None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def consistent(self):
        if self.status == "assigned" and not self.assigned_worker_id:
            raise ValueError("giao tuyến cần assigned_worker_id")
        if (self.actual_distance_m is None) != (self.actual_distance_source is None):
            raise ValueError("actual_distance_m và actual_distance_source phải đi cùng nhau")
        return self
