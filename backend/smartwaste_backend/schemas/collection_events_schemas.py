"""Request/response models for /collection-events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .bins_schemas import ID_PATTERN


WeightSource = Literal["scale", "manual", "unknown"]


class CollectionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    bin_id: str = Field(min_length=1, max_length=80, pattern=ID_PATTERN)
    completed_at: datetime
    measured_weight_kg: float | None = Field(None, ge=0, le=100000)
    weight_source: WeightSource | None = None
    fill_before_pct: float | None = Field(None, ge=0, le=100)
    fill_after_pct: float | None = Field(None, ge=0, le=100)
    note: str | None = Field(None, min_length=1, max_length=1000)
    route_id: str | None = Field(None, min_length=1, max_length=80, pattern=ID_PATTERN)
    stop_order: int | None = Field(None, ge=1, le=200)

    @model_validator(mode="after")
    def consistent(self):
        if (self.route_id is None) != (self.stop_order is None):
            raise ValueError("route_id và stop_order phải đi cùng nhau")
        # A weight always has a source; no weight means the source is unknown (never guessed).
        if self.measured_weight_kg is None:
            if self.weight_source not in (None, "unknown"):
                raise ValueError("weight_source scale/manual cần có measured_weight_kg")
            self.weight_source = "unknown"
        elif self.weight_source == "unknown":
            raise ValueError("có measured_weight_kg thì weight_source phải là scale hoặc manual")
        else:
            self.weight_source = self.weight_source or "manual"
        return self


class CollectionOut(BaseModel):
    id: str
    bin_id: str
    worker_id: str
    worker_name: str | None
    route_id: str | None
    stop_order: int | None
    completed_at: str
    recorded_at: str
    waste_type: str
    measured_weight_kg: float | None
    weight_source: WeightSource
    fill_before_pct: float | None
    fill_after_pct: float | None
    note: str | None
