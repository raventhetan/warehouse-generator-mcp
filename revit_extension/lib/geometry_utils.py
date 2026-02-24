# -*- coding: utf-8 -*-
"""
geometry_utils.py — вспомогательные функции геометрии
IronPython 2.7 compatible
"""

from Autodesk.Revit.DB import XYZ, Line, CurveArray

MM_TO_FT = 0.00328084


def mm_to_ft(value_mm):
    """Конвертация миллиметров в футы."""
    return value_mm * MM_TO_FT


def ft_to_mm(value_ft):
    """Конвертация футов в миллиметры."""
    return value_ft / MM_TO_FT


def build_rect_curve_array(length_ft, width_ft):
    """
    Строит CurveArray прямоугольного контура для NewFloor().
    Точки идут по часовой стрелке, контур замкнут.
    """
    pts = [
        XYZ(0,         0,        0),
        XYZ(length_ft, 0,        0),
        XYZ(length_ft, width_ft, 0),
        XYZ(0,         width_ft, 0),
    ]
    curve_array = CurveArray()
    n = len(pts)
    for i in range(n):
        curve_array.Append(Line.CreateBound(pts[i], pts[(i + 1) % n]))
    return curve_array


def build_rect_wall_lines(length_ft, width_ft):
    """
    Возвращает список Line для 4 стен прямоугольника.
    Стены создаются встык (без зазоров) — JoinGeometry соединит углы.
    """
    pts = [
        XYZ(0,         0,        0),
        XYZ(length_ft, 0,        0),
        XYZ(length_ft, width_ft, 0),
        XYZ(0,         width_ft, 0),
    ]
    lines = []
    n = len(pts)
    for i in range(n):
        lines.append(Line.CreateBound(pts[i], pts[(i + 1) % n]))
    return lines


def get_wall_midpoint(wall):
    """Возвращает XYZ центра стены."""
    loc = wall.Location
    curve = loc.Curve
    return curve.Evaluate(0.5, True)


# ─── Фаза 3: полигональные контуры ───────────────────────────

def build_curve_array_from_points(points_mm):
    """
    Строит CurveArray из списка [[x, y], ...] точек в мм.
    Используется для doc.Create.NewFloor() в Revit 2021.
    Контур замыкается автоматически.
    """
    pts = [XYZ(mm_to_ft(p[0]), mm_to_ft(p[1]), 0) for p in points_mm]
    curve_array = CurveArray()
    n = len(pts)
    for i in range(n):
        curve_array.Append(Line.CreateBound(pts[i], pts[(i + 1) % n]))
    return curve_array


def get_wall_lines_from_points(points_mm):
    """
    Возвращает список Line для стен полигонального контура.
    points_mm — список [[x, y], ...] в мм.
    Контур замыкается автоматически (последняя точка → первая).
    """
    pts = [XYZ(mm_to_ft(p[0]), mm_to_ft(p[1]), 0) for p in points_mm]
    lines = []
    n = len(pts)
    for i in range(n):
        lines.append(Line.CreateBound(pts[i], pts[(i + 1) % n]))
    return lines


# ─── Фаза 3: виртуальная сетка осей ─────────────────────────

def build_grid_map(x_step_mm, y_step_mm, x_count, y_count,
                   origin_x_mm=0, origin_y_mm=0):
    """
    Строит карту именованных узлов виртуальной сетки.
    Строки: A, B, C, ... (по Y).  Колонны: 1, 2, 3, ... (по X).
    Возвращает {"A1": [x_mm, y_mm], ...}
    """
    row_labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    grid = {}
    for row_idx in range(min(y_count, len(row_labels))):
        row_label = row_labels[row_idx]
        for col_idx in range(x_count):
            node_name = "{0}{1}".format(row_label, col_idx + 1)
            x = origin_x_mm + col_idx * x_step_mm
            y = origin_y_mm + row_idx * y_step_mm
            grid[node_name] = [x, y]
    return grid


def read_revit_grids(doc):
    """
    Читает именованные оси (Grid) из текущего документа Revit.
    Возвращает список {"name": str, "start": [x_mm, y_mm], "end": [x_mm, y_mm]}.
    """
    from Autodesk.Revit.DB import FilteredElementCollector, Grid
    grids = FilteredElementCollector(doc).OfClass(Grid).ToElements()
    result = []
    for g in grids:
        curve = g.Curve
        pt1 = curve.GetEndPoint(0)
        pt2 = curve.GetEndPoint(1)
        result.append({
            "name":  g.Name,
            "start": [int(round(ft_to_mm(pt1.X))), int(round(ft_to_mm(pt1.Y)))],
            "end":   [int(round(ft_to_mm(pt2.X))), int(round(ft_to_mm(pt2.Y)))],
        })
    return result
