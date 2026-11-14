"""Request/response models for /bins."""

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9:_-]*$"
WasteType = Literal["general", "organic", "recyclable", "hazardous", "other"]
BinStatus = Literal["active", "maintenance", "retired"]


class GeoPoint(BaseModel):
    """GeoJSON point; coordinates are [longitude, latitude]."""

    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]

    @field_validator("coordinates")
    @classmethod
    def in_range(cls, value):
        lng, lat = value
        if not (-180 <= lng <= 180 and -90 <= lat <= 90):
            raise ValueError("tọa độ phải là [kinh độ -180..180, vĩ độ -90..90]")
        return value


class _BinFields(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    location: GeoPoint | None = None
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)

    @model_validator(mode="after")
    def lat_lng_to_location(self):
        if (self.lat is None) != (self.lng is None):
            raise ValueError("lat và lng phải đi cùng nhau")
        if self.lat is not None and self.location is None:
            self.location = GeoPoint(coordinates=(self.lng, self.lat))
        return self


class BinCreate(_BinFields):
    code: str = Field(min_length=1, max_length=40, pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=300)
    ward_code: str = Field(min_length=1, max_length=40)
    waste_type: WasteType
    capacity_l: float | None = Field(None, ge=1, le=100000)
    notes: str | None = Field(None, min_length=1, max_length=1000)


class BinUpdate(_BinFields):
    """Partial update: only fields present in the request are changed."""

    name: str | None = Field(None, min_length=1, max_length=120)
    address: str | None = Field(None, min_length=1, max_length=300)
    ward_code: str | None = Field(None, min_length=1, max_length=40)
    waste_type: WasteType | None = None
    capacity_l: float | None = Field(None, ge=1, le=100000)
    status: BinStatus | None = None
    notes: str | None = Field(None, min_length=1, max_length=1000)

    NOT_NULL: ClassVar[tuple[str, ...]] = ("name", "address", "ward_code", "waste_type", "status")

    @model_validator(mode="after")
    def required_fields_not_null(self):
        for field in self.NOT_NULL:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} không được để trống")
        return self

    def changes(self):
        """Fields the client actually sent, with lat/lng folded into location."""
        sent = self.model_dump(exclude_unset=True, exclude={"lat", "lng", "location"})
        if self.model_fields_set & {"location", "lat", "lng"}:
            sent["location"] = self.location.model_dump() if self.location else None
        return sent


class StateOut(BaseModel):
    device_id: str
    fill_pct: float | None
    distance_mm: int | None
    sampled_at: str | None
    latest_quality: str
    latest_sampled_at: str | None
    alarm_active: bool | None
    last_contact_at: str | None
    last_collected_at: str | None
    fresh: bool


class BinOut(BaseModel):
    id: str
    code: str
    name: str
    address: str
    ward_code: str
    waste_type: WasteType
    capacity_l: float | None
    status: BinStatus
    location: GeoPoint | None
    lat: float | None
    lng: float | None
    state: StateOut | None
