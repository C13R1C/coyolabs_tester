from pathlib import Path
import inspect

from app.controllers import reservations_controller


TEMPLATE_PATH = Path("app/templates/reservations/request.html")


def test_request_template_no_longer_renders_material_checkbox_label():
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "Solicitar materiales para esta práctica" not in content


def test_request_template_has_no_legacy_material_input_names():
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert 'name="request_materials"' not in content
    assert 'name="material_id[]"' not in content
    assert 'name="quantity[]"' not in content


def test_request_reservation_submit_no_longer_reads_legacy_material_fields():
    source = inspect.getsource(reservations_controller.request_reservation)
    assert 'request.form.get("request_materials")' not in source
    assert 'request.form.getlist("material_id[]")' not in source
    assert 'request.form.getlist("quantity[]")' not in source
