from .campus_forms import (
    CampusForm,
)

from .building_forms import (
    BuildingForm,
    ChangeBuildingGenderPolicyForm,
    ChangeBuildingPopulationForm,
    ChangeDefaultBedConfigurationForm,
)

from .floor_forms import (
    FloorForm,
    CreateFloorForm,
    ChangeFloorGenderForm,
    FloorRestrictionForm,
    FloorBedConfigurationForm,
)

from .room_forms import (
    RoomForm,
    CreateRoomForm,
    RoomBedConfigurationForm,
)

from .bed_configuration_forms import (
    BedConfigurationForm,
    BedConfigurationStatusForm,
)

from .bed_forms import (
    BedForm,
    CreateBedForm,
    UpdateBedPositionForm,
    SetBedStatusForm,
)

from .migration_forms import (
    InspectRoomConfigurationForm,
    ExpandRoomForm,
    PrepareRoomReductionForm,
    ApplyRoomReductionForm,
    ReconfigureRoomForm,
)