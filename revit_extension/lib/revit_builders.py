# -*- coding: utf-8 -*-
"""
revit_builders.py — создание Revit-элементов через API.
Вся бизнес-логика создания элементов — здесь.
IronPython 2.7 compatible
"""

from Autodesk.Revit.DB import (
    FilteredElementCollector, Wall, WallType, Floor, FloorType,
    Level, Transaction, JoinGeometryUtils, Line, XYZ,
    Element, FamilySymbol,
)
from Autodesk.Revit.DB.Structure import StructuralType
import geometry_utils as gu
import validation as val
import state_manager as sm


def _get_first(doc, cls):
    """Получить первый элемент заданного класса из документа."""
    return FilteredElementCollector(doc).OfClass(cls).FirstElement()


# ─── Фаза 1: склад (прямоугольник) ───────────────────────────

def create_warehouse(doc, length_mm, width_mm, height_mm,
                     wall_type=None, floor_type=None, level=None):
    """
    Создаёт прямоугольный склад: 4 стены + пол.
    Параметры в мм, конвертация в футы внутри.
    """
    errors = val.check_dimensions(length_mm, width_mm, height_mm)
    if errors:
        return {"error": "Validation failed: " + "; ".join(errors)}

    length_ft = gu.mm_to_ft(length_mm)
    width_ft  = gu.mm_to_ft(width_mm)
    height_ft = gu.mm_to_ft(height_mm)

    level      = level      or _get_first(doc, Level)
    wall_type  = wall_type  or _get_first(doc, WallType)
    floor_type = floor_type or _get_first(doc, FloorType)

    if not level:      return {"error": "No Level found in document"}
    if not wall_type:  return {"error": "No WallType found in document"}
    if not floor_type: return {"error": "No FloorType found in document"}

    wall_lines = gu.build_rect_wall_lines(length_ft, width_ft)
    ok, seg_errors = val.validate_wall_lines(wall_lines, doc.Application)
    if not ok:
        return {"error": "Geometry validation failed: " + "; ".join(seg_errors)}

    t = Transaction(doc, "MCP: Create Warehouse")
    t.Start()
    try:
        created_walls = []
        for line in wall_lines:
            wall = Wall.Create(doc, line, wall_type.Id, level.Id, height_ft, 0, False, False)
            created_walls.append(wall)
        curve_array = gu.build_rect_curve_array(length_ft, width_ft)
        floor = doc.Create.NewFloor(curve_array, floor_type, level, False)
        _auto_join_adjacent(doc, created_walls)
        t.Commit()

        wall_client_ids = [sm.register_element(w, "Wall") for w in created_walls]
        floor_client_id = sm.register_element(floor, "Floor")
        return {
            "success": True,
            "walls_created": len(created_walls),
            "floor_created": True,
            "dimensions_mm": "{0}x{1}x{2}".format(length_mm, width_mm, height_mm),
            "wall_client_ids": wall_client_ids,
            "floor_client_id": floor_client_id,
        }
    except Exception as e:
        t.RollBack()
        return {"error": str(e)}


def create_level(doc, elevation_mm, name=None):
    """Создаёт уровень на заданной высоте (в мм)."""
    elevation_ft = gu.mm_to_ft(elevation_mm)
    t = Transaction(doc, "MCP: Create Level")
    t.Start()
    try:
        level = Level.Create(doc, elevation_ft)
        if name:
            level.Name = name
        t.Commit()
        cid = sm.register_element(level, "Level", name or level.Name)
        return {"success": True, "level_name": level.Name,
                "elevation_mm": elevation_mm, "client_id": cid}
    except Exception as e:
        t.RollBack()
        return {"error": str(e)}


def delete_element(doc, client_id):
    """Удаляет элемент Revit по client_id."""
    elem = sm.find_revit_element(doc, client_id)
    if not elem:
        return {"error": "Element not found for client_id: {0}".format(client_id)}
    t = Transaction(doc, "MCP: Delete Element")
    t.Start()
    try:
        doc.Delete(elem.Id)
        t.Commit()
        sm.remove_element(client_id)
        return {"success": True, "deleted_client_id": client_id}
    except Exception as e:
        t.RollBack()
        return {"error": str(e)}


# ─── Фаза 3.3: автоматический JoinGeometry ───────────────────

def _try_join_pair(doc, elem_a, elem_b):
    """Пробует соединить два элемента через JoinGeometry (BoundingBox check)."""
    try:
        bb_a = elem_a.get_BoundingBox(None)
        bb_b = elem_b.get_BoundingBox(None)
        if bb_a is None or bb_b is None:
            return False
        tol = 0.5  # ~150 мм — учитывает толщину стен
        if (bb_a.Max.X + tol < bb_b.Min.X or bb_b.Max.X + tol < bb_a.Min.X or
                bb_a.Max.Y + tol < bb_b.Min.Y or bb_b.Max.Y + tol < bb_a.Min.Y):
            return False
        JoinGeometryUtils.JoinGeometry(doc, elem_a, elem_b)
        return True
    except Exception:
        return False


def _auto_join_adjacent(doc, wall_list):
    """Соединяет смежные стены: i ↔ i+1, последняя ↔ первая."""
    n = len(wall_list)
    for i in range(n):
        _try_join_pair(doc, wall_list[i], wall_list[(i + 1) % n])


# ─── Фаза 3.2: полигональное здание ──────────────────────────

def create_polygon_building(doc, points_mm, height_mm,
                             wall_type=None, floor_type=None, level=None):
    """Создаёт здание произвольной полигональной формы."""
    ok, err = val.check_polygon_closed(points_mm)
    if not ok:
        return {"error": err}
    dim_errors = val.check_dimensions_2d(points_mm, height_mm)
    if dim_errors:
        return {"error": "; ".join(dim_errors)}
    ok, seg_errors = val.check_polygon_segments_mm(points_mm)
    if not ok:
        return {"error": "Geometry: " + "; ".join(seg_errors)}

    height_ft  = gu.mm_to_ft(height_mm)
    level      = level      or _get_first(doc, Level)
    wall_type  = wall_type  or _get_first(doc, WallType)
    floor_type = floor_type or _get_first(doc, FloorType)

    if not level:      return {"error": "No Level found in document"}
    if not wall_type:  return {"error": "No WallType found in document"}
    if not floor_type: return {"error": "No FloorType found in document"}

    wall_lines  = gu.get_wall_lines_from_points(points_mm)
    curve_array = gu.build_curve_array_from_points(points_mm)

    t = Transaction(doc, "MCP: Create Polygon Building")
    t.Start()
    try:
        created_walls = []
        for line in wall_lines:
            wall = Wall.Create(doc, line, wall_type.Id, level.Id, height_ft, 0, False, False)
            created_walls.append(wall)
        floor = doc.Create.NewFloor(curve_array, floor_type, level, False)
        _auto_join_adjacent(doc, created_walls)
        t.Commit()

        wall_client_ids = [sm.register_element(w, "Wall") for w in created_walls]
        floor_client_id = sm.register_element(floor, "Floor")
        return {
            "success": True,
            "walls_created": len(created_walls),
            "floor_created": True,
            "wall_client_ids": wall_client_ids,
            "floor_client_id": floor_client_id,
        }
    except Exception as e:
        t.RollBack()
        return {"error": str(e)}


# ─── Фаза 3.1: одна стена (grid-based) ───────────────────────

def create_wall_single(doc, from_mm, to_mm, height_mm,
                       wall_type=None, level=None):
    """Создаёт одну стену от точки from_mm=[x,y] до to_mm=[x,y] (мм)."""
    pt1 = XYZ(gu.mm_to_ft(from_mm[0]), gu.mm_to_ft(from_mm[1]), 0)
    pt2 = XYZ(gu.mm_to_ft(to_mm[0]),   gu.mm_to_ft(to_mm[1]),   0)
    ok, err = val.check_segment_length(pt1, pt2, doc.Application)
    if not ok:
        return {"error": err}

    height_ft = gu.mm_to_ft(height_mm)
    level     = level     or _get_first(doc, Level)
    wall_type = wall_type or _get_first(doc, WallType)
    if not level: return {"error": "No Level found in document"}

    t = Transaction(doc, "MCP: Create Wall")
    t.Start()
    try:
        line = Line.CreateBound(pt1, pt2)
        wall = Wall.Create(doc, line, wall_type.Id, level.Id, height_ft, 0, False, False)
        t.Commit()
        cid = sm.register_element(wall, "Wall")
        return {"success": True, "client_id": cid,
                "from_mm": from_mm, "to_mm": to_mm, "height_mm": height_mm}
    except Exception as e:
        t.RollBack()
        return {"error": str(e)}


# ─── Фаза 3.4: окна и двери ───────────────────────────────────

def create_opening(doc, wall_client_id, family_type_name,
                   offset_along_wall_mm, sill_height_mm):
    """Вставляет дверь или окно в стену-хост."""
    wall = sm.find_revit_element(doc, wall_client_id)
    if not wall:
        return {"error": "Wall not found: " + wall_client_id}

    collector = FilteredElementCollector(doc).OfClass(FamilySymbol)
    symbol = None
    for s in list(collector):
        sym_name    = Element.Name.__get__(s)
        family_name = Element.Name.__get__(s.Family) if s.Family else ""
        full_name   = "{0} : {1}".format(family_name, sym_name)
        if sym_name == family_type_name or full_name == family_type_name:
            symbol = s
            break

    if not symbol:
        available = []
        for s in list(FilteredElementCollector(doc).OfClass(FamilySymbol))[:20]:
            sym_name    = Element.Name.__get__(s)
            family_name = Element.Name.__get__(s.Family) if s.Family else ""
            available.append("{0} : {1}".format(family_name, sym_name))
        return {
            "error": "FamilySymbol '{0}' not found".format(family_type_name),
            "available_types": available,
        }

    wall_curve = wall.Location.Curve
    wall_start = wall_curve.GetEndPoint(0)
    wall_end   = wall_curve.GetEndPoint(1)
    wall_dir   = (wall_end - wall_start).Normalize()
    offset_ft  = gu.mm_to_ft(offset_along_wall_mm)
    sill_ft    = gu.mm_to_ft(sill_height_mm)
    insert_pt  = XYZ(
        wall_start.X + wall_dir.X * offset_ft,
        wall_start.Y + wall_dir.Y * offset_ft,
        wall_start.Z + sill_ft,
    )
    level = doc.GetElement(wall.LevelId)

    t = Transaction(doc, "MCP: Create Opening")
    t.Start()
    try:
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()
        instance = doc.Create.NewFamilyInstance(
            insert_pt, symbol, wall, level, StructuralType.NonStructural,
        )
        t.Commit()
        cid = sm.register_element(instance, "Opening", Element.Name.__get__(symbol))
        return {
            "success": True, "client_id": cid,
            "family_type": family_type_name,
            "offset_along_wall_mm": offset_along_wall_mm,
            "sill_height_mm": sill_height_mm,
        }
    except Exception as e:
        t.RollBack()
        return {"error": str(e)}
