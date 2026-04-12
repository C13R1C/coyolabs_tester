# Importar todos los modelos aquí asegura que SQLAlchemy los registre
# en la metadata antes de correr migraciones.

from .user import User  # noqa: F401
from .lab import Lab  # noqa: F401
from .material import Material  # noqa: F401
from .logbook import LogbookEvent  # noqa: F401
from .debt import Debt  # noqa: F401
from .reservation import Reservation  # noqa: F401
from .lost_found import LostFound  # noqa: F401
from .software import Software  # noqa: F401
from .inventory_request_ticket import InventoryRequestTicket  # noqa: F401
from .inventory_request_item import InventoryRequestItem  # noqa: F401
from .career import Career  # noqa: F401
from .academic_level import AcademicLevel  # noqa: F401
from .subject import Subject  # noqa: F401
from .teacher_academic_load import TeacherAcademicLoad  # noqa: F401
from .profile_change_request import ProfileChangeRequest  # noqa: F401
from .critical_action_request import CriticalActionRequest  # noqa: F401
from .forum_post import ForumPost  # noqa: F401
from .forum_comment import ForumComment  # noqa: F401
from .permission import Permission, RolePermission  # noqa: F401
from .print3d_job import Print3DJob  # noqa: F401
from .push_subscription import PushSubscription  # noqa: F401
