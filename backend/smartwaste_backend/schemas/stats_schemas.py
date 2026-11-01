"""Response models for /stats."""

from pydantic import BaseModel, Field


class WasteTypeStat(BaseModel):
    waste_type: str
    bin_count: int = Field(description="Số thùng đang dùng (field, chưa ngừng) thuộc loại này")
    collection_count: int = Field(description="Số lượt thu gom trong khoảng thời gian")
    avg_fill_pct: float | None = Field(
        description="Mức đầy trung bình của các mẫu đo tốt trong khoảng; null nếu không có mẫu")
    known_weight_kg: float | None = Field(description="Tổng kg của các lượt có cân; null nếu không có")
    known_weight_count: int
    unknown_weight_count: int


class WasteStatsOut(BaseModel):
    items: list[WasteTypeStat]
