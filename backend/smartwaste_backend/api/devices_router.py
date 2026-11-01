"""HTTP endpoints for devices: register, calibrate, attach to a bin (admin only)."""

from fastapi import APIRouter, Depends, Request

from ..core.security import require_roles
from ..schemas.devices_schemas import (
    AssignmentCreate, AssignmentOut, ConfigCreate, ConfigOut, DeviceCreate, DeviceOut,
)
from ..services import devices_service


router = APIRouter(tags=["devices"])
admin_only = require_roles("admin")


@router.post("/devices", status_code=201, response_model=DeviceOut)
def create_device(body: DeviceCreate, request: Request, user=Depends(admin_only)):
    return devices_service.create_device(body, user, request.state.request_id)


@router.post("/devices/{device_id}/configs", status_code=201, response_model=ConfigOut)
def create_config(device_id: str, body: ConfigCreate, request: Request,
                  user=Depends(admin_only)):
    """Declare the calibration flashed on the node; without it the bin shows no readings."""
    return devices_service.create_config(device_id, body, user, request.state.request_id)


@router.post("/bins/{bin_id}/assignments", status_code=201, response_model=AssignmentOut)
def assign_device(bin_id: str, body: AssignmentCreate, request: Request,
                  user=Depends(admin_only)):
    """Attach a device to a bin, replacing the current one in a single transaction."""
    return devices_service.assign_device(bin_id, body, user, request.state.request_id)
