# -*- coding: utf-8 -*-
"""
state_manager.py — отслеживание созданных элементов в памяти.
Phase 1: in-memory dict (живёт пока Revit открыт).
Phase 4 (будущее): замена на Extensible Storage.
IronPython 2.7 compatible
"""

import uuid
from datetime import datetime

# {client_id: {"revit_id": int, "type": str, "name": str, "created_at": str}}
_registry = {}


def new_client_id():
    return str(uuid.uuid4())


def register_element(revit_element, elem_type, name=""):
    """Регистрирует Revit-элемент. Возвращает client_id."""
    client_id = new_client_id()
    _registry[client_id] = {
        "revit_id": revit_element.Id.IntegerValue,
        "type": elem_type,
        "name": name or "{0}_{1}".format(elem_type, revit_element.Id.IntegerValue),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return client_id


def find_by_client_id(client_id):
    return _registry.get(client_id)


def find_revit_element(doc, client_id):
    """Ищет Revit-элемент в документе по client_id. Возвращает Element или None."""
    from Autodesk.Revit.DB import ElementId
    record = _registry.get(client_id)
    if not record:
        return None
    try:
        return doc.GetElement(ElementId(record["revit_id"]))
    except Exception:
        return None


def list_elements(elem_type=None):
    """Возвращает список всех записей реестра."""
    result = []
    for cid, record in _registry.items():
        if elem_type is None or record["type"] == elem_type:
            entry = dict(record)
            entry["client_id"] = cid
            result.append(entry)
    return result


def remove_element(client_id):
    if client_id in _registry:
        del _registry[client_id]
        return True
    return False


def clear_registry():
    _registry.clear()


# ─── Фаза 3: виртуальная сетка осей ─────────────────────────

_grid_state = {
    "nodes":  {},   # {"A1": [x_mm, y_mm], ...}
    "config": {},
}


def set_grid(nodes, config=None):
    _grid_state["nodes"]  = dict(nodes)
    _grid_state["config"] = config or {}


def get_grid_node(node_name):
    return _grid_state["nodes"].get(node_name)


def get_all_grid_nodes():
    return dict(_grid_state["nodes"])


def clear_grid():
    _grid_state["nodes"].clear()
    _grid_state["config"].clear()
