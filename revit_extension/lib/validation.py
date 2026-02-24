# -*- coding: utf-8 -*-
"""
validation.py — проверка геометрии перед созданием элементов
IronPython 2.7 compatible
"""

import math


def check_segment_length(pt1, pt2, app):
    """
    Проверяет, что длина сегмента не меньше порога точности Revit.
    Возвращает (ok: bool, error_msg: str|None).
    """
    length = pt1.DistanceTo(pt2)
    tol = app.ShortCurveTolerance
    if length < tol:
        return False, "Segment too short: {0:.6f} ft (min {1:.6f} ft)".format(length, tol)
    return True, None


def check_dimensions(length_mm, width_mm, height_mm):
    """
    Базовая проверка строительных размеров.
    Возвращает список строк с ошибками (пустой список = всё ок).
    """
    errors = []
    if length_mm <= 0: errors.append("length must be > 0 mm")
    if width_mm  <= 0: errors.append("width must be > 0 mm")
    if height_mm <= 0: errors.append("height must be > 0 mm")
    if length_mm < 100: errors.append("length < 100 mm — too small for Revit")
    if width_mm  < 100: errors.append("width < 100 mm — too small for Revit")
    if height_mm < 100: errors.append("height < 100 mm — too small for Revit")
    return errors


def validate_wall_lines(lines, app):
    """
    Проверяет набор Line перед созданием стен.
    Возвращает (ok: bool, errors: list).
    """
    errors = []
    for i, line in enumerate(lines):
        ok, msg = check_segment_length(line.GetEndPoint(0), line.GetEndPoint(1), app)
        if not ok:
            errors.append("Wall #{0}: {1}".format(i, msg))
    return len(errors) == 0, errors


# ─── Фаза 3: полигональные контуры ───────────────────────────

def check_polygon_closed(points_mm):
    """
    Проверяет что полигон содержит минимум 3 точки.
    Возвращает (ok: bool, error: str|None).
    """
    if len(points_mm) < 3:
        return False, "Polygon requires at least 3 points, got {0}".format(len(points_mm))
    return True, None


def check_polygon_segments_mm(points_mm, min_length_mm=30):
    """
    Проверяет все стороны полигона на минимальную длину (в мм).
    30 мм ≈ Application.ShortCurveTolerance (0.1 ft ≈ 30.5 мм).
    Возвращает (ok: bool, errors: list).
    """
    errors = []
    n = len(points_mm)
    for i in range(n):
        p1 = points_mm[i]
        p2 = points_mm[(i + 1) % n]
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.sqrt(dx * dx + dy * dy)
        if length < min_length_mm:
            errors.append(
                "Segment {0}->{1}: {2:.1f} mm < min {3} mm".format(
                    i, (i + 1) % n, length, min_length_mm
                )
            )
    return len(errors) == 0, errors


def check_dimensions_2d(points_mm, height_mm):
    """
    Базовая проверка для полигонального здания.
    Возвращает список строк с ошибками.
    """
    errors = []
    if height_mm <= 0:  errors.append("height must be > 0 mm")
    if height_mm < 100: errors.append("height < 100 mm — too small for Revit")
    if len(points_mm) < 3: errors.append("At least 3 polygon points required")
    return errors
