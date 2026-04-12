from app.controllers.users_controller import (
    ADMIN_ASSIGNABLE_ROLES,
    ROOT_SUPERADMIN_ASSIGNABLE_ROLES,
    SUPERADMIN_ASSIGNABLE_ROLES,
)
from app.utils.text import role_label


def test_admin_assignable_roles_include_staff():
    assert "STAFF" in ADMIN_ASSIGNABLE_ROLES


def test_superadmin_assignable_roles_include_staff():
    assert "STAFF" in SUPERADMIN_ASSIGNABLE_ROLES


def test_root_superadmin_assignable_roles_include_superadmin():
    assert "SUPERADMIN" in ROOT_SUPERADMIN_ASSIGNABLE_ROLES


def test_staff_role_label_is_human_friendly():
    assert role_label("STAFF") == "Staff"
