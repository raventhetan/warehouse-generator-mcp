"""
Warehouse Generator MCP Server
Генерация и управление BIM-элементами в Revit через естественный язык.
"""

from mcp.server.fastmcp import FastMCP
import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Any
import urllib.request
import urllib.error

REVIT_BASE_URL = "http://192.168.31.44:48884/revit-mcp-v1"
REVIT_TIMEOUT = 30

mcp = FastMCP("Warehouse Generator")

PROJECT_DIR = os.path.dirname(__file__)
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def call_revit_post(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """HTTP POST → pyRevit Routes."""
    url = f"{REVIT_BASE_URL}{endpoint}"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=REVIT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": f"HTTP {e.code}: {raw[:500]}"}
    except Exception as e:
        return {"error": str(e)}


def call_revit_get(endpoint: str) -> Dict[str, Any]:
    """HTTP GET → pyRevit Routes."""
    url = f"{REVIT_BASE_URL}{endpoint}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=REVIT_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            return json.loads(raw)
        except Exception:
            return {"error": f"HTTP {e.code}: {raw[:500]}"}
    except Exception as e:
        return {"error": str(e)}


def validate_design_rules(params: Dict[str, Any]) -> List[str]:
    errors = []
    length = params.get('length', 0)
    width = params.get('width', 0)
    height = params.get('height', 0)
    wall_thickness = params.get('wall_thickness', 0)
    if length < 6 or width < 6:
        errors.append("Минимальные размеры здания: 6×6 м")
    if length > 60 or width > 40:
        errors.append("Максимальные размеры без спец. расчета: 60×40 м")
    if height < 3.0:
        errors.append("Минимальная высота здания: 3.0 м")
    if height > 15:
        errors.append("При высоте > 15 м требуется индивидуальный расчет")
    if wall_thickness < 380:
        errors.append("Минимальная толщина несущих стен: 380 мм")
    if height > 10 and wall_thickness < 510:
        errors.append("При высоте > 10 м минимальная толщина стен: 510 мм")
    return errors


def get_design_recommendations(params: Dict[str, Any]) -> List[str]:
    recommendations = []
    length = params.get('length', 0)
    width = params.get('width', 0)
    height = params.get('height', 0)
    wall_thickness = params.get('wall_thickness', 0)
    ratio = length / width if width > 0 else 1
    if ratio > 3:
        recommendations.append("Соотношение сторон > 3:1 может потребовать дополнительных опор")
    if height <= 8 and wall_thickness > 380:
        recommendations.append("При данной высоте достаточно стен 380 мм (экономия материала)")
    area = length * width
    if area > 1000:
        recommendations.append("При площади > 1000 м² рекомендуется деление на пожарные отсеки")
    return recommendations


@mcp.tool()
def generate_warehouse(
    length: float, width: float, height: float,
    wall_thickness: int, region: str = "Юг", project_name: str = None
) -> str:
    """
    Генерирует складское здание в Revit с заданными параметрами.

    Args:
        length: Длина здания в метрах (например, 42.0)
        width: Ширина здания в метрах (например, 18.0)
        height: Высота здания в метрах (например, 8.0)
        wall_thickness: Толщина наружных стен в мм (например, 380)
        region: Регион строительства для нормативов ("Юг", "Север")
        project_name: Название проекта (опционально)
    """
    validation_errors = validate_design_rules({
        'length': length, 'width': width,
        'height': height, 'wall_thickness': wall_thickness
    })
    if validation_errors:
        return "Ошибки валидации:\n" + "\n".join(validation_errors)

    project_id = str(uuid.uuid4())[:8]
    if not project_name:
        project_name = "Склад_{0}x{1}_{2}".format(
            length, width, datetime.now().strftime('%Y%m%d_%H%M')
        )

    revit_result = call_revit_post("/warehouse/create", {
        "length": int(length * 1000),
        "width":  int(width  * 1000),
        "height": int(height * 1000),
    })

    if revit_result.get("error"):
        return "Ошибка Revit API: " + revit_result["error"]
    if not revit_result.get("success"):
        return "Revit вернул неудачу: " + str(revit_result)

    project_dir = os.path.join(OUTPUT_DIR, "{0}_{1}".format(project_id, project_name))
    os.makedirs(project_dir, exist_ok=True)
    with open(os.path.join(project_dir, "project_info.json"), "w", encoding="utf-8") as f:
        json.dump({
            "project_name": project_name, "project_id": project_id,
            "created_date": datetime.now().isoformat(),
            "parameters": {"length": length, "width": width, "height": height,
                           "wall_thickness": wall_thickness, "region": region},
            "revit_response": revit_result,
        }, f, ensure_ascii=False, indent=2)

    wall_ids = revit_result.get("wall_client_ids", [])
    floor_id  = revit_result.get("floor_client_id", "")
    return (
        'Склад "{name}" создан в Revit!\n\n'
        'Размеры: {l}x{w}x{h} м\nСтены: {wc} шт\nПол: {fc}\n\n'
        'client_id стен: {wids}\nclient_id пола: {fid}\n\n'
        'Сохраните client_id — они нужны для удаления или изменения элементов.'
    ).format(
        name=project_name, l=length, w=width, h=height,
        wc=revit_result.get("walls_created", 0),
        fc="да" if revit_result.get("floor_created") else "нет",
        wids=", ".join(wall_ids) if wall_ids else "нет данных",
        fid=floor_id or "нет данных",
    )


@mcp.tool()
def get_model_info() -> str:
    """
    Возвращает информацию о текущем Revit-документе:
    уровни (с высотами), доступные типы стен и полов.
    """
    result = call_revit_get("/model_info/")
    if result.get("error"):
        return "Ошибка: " + result["error"]
    levels = result.get("levels", [])
    lines = ["Документ: " + result.get("document_title", "неизвестно"), "", "Уровни:"]
    for lv in levels:
        lines.append("  {name} — {elevation_mm} мм".format(**lv))
    lines.append("")
    wt = result.get("wall_types", [])
    ft = result.get("floor_types", [])
    lines.append("Типы стен: " + ", ".join(wt) if wt else "Типы стен: нет данных")
    lines.append("Типы полов: " + ", ".join(ft) if ft else "Типы полов: нет данных")
    return "\n".join(lines)


@mcp.tool()
def create_level(elevation_mm: int, name: str = None) -> str:
    """
    Создаёт новый уровень (этаж) в Revit на заданной высоте.

    Args:
        elevation_mm: Высота уровня от нуля в миллиметрах (например, 3000 для 2-го этажа)
        name: Имя уровня (например, "Level 2"). Если не указано — Revit назначит автоматически.

    Returns:
        Результат с именем уровня и его client_id
    """
    payload = {"elevation": elevation_mm}
    if name:
        payload["name"] = name
    result = call_revit_post("/level/create", payload)
    if result.get("error"):
        return "Ошибка создания уровня: " + result["error"]
    return 'Уровень "{name}" создан!\nВысота: {elevation_mm} мм\nclient_id: {client_id}'.format(**result)


@mcp.tool()
def delete_element(client_id: str) -> str:
    """
    Удаляет элемент из Revit по его client_id.
    client_id выдаётся при создании элемента (стена, пол, уровень).

    Args:
        client_id: Идентификатор элемента, полученный при создании

    Returns:
        Подтверждение удаления или сообщение об ошибке
    """
    result = call_revit_post("/element/delete", {"client_id": client_id})
    if result.get("error"):
        return "Ошибка удаления: " + result["error"]
    return "Элемент {0} успешно удалён из Revit.".format(
        result.get("deleted_client_id", client_id)
    )


@mcp.tool()
def list_elements() -> str:
    """
    Показывает все элементы, созданные в текущей сессии Revit.
    Выводит client_id, тип, имя и дату создания каждого элемента.
    Внимание: список сбрасывается при рестарте Revit.

    Returns:
        Таблица созданных элементов с их client_id
    """
    result = call_revit_get("/elements/list")
    if result.get("error"):
        return "Ошибка: " + result["error"]
    elements = result.get("elements", [])
    count = result.get("count", 0)
    if count == 0:
        return "В текущей сессии элементов не создано."
    lines = ["Элементов в сессии: {0}".format(count), ""]
    for el in elements:
        lines.append("[{type}] {name}".format(**el))
        lines.append("  client_id:  {client_id}".format(**el))
        lines.append("  revit_id:   {revit_id}".format(**el))
        lines.append("  создан:     {created_at}".format(**el))
        lines.append("")
    return "\n".join(lines)


@mcp.tool()
def validate_building_parameters(
    length: float, width: float, height: float,
    wall_thickness: int, region: str = "Юг"
) -> str:
    """
    Проверяет соответствие параметров здания нормативным требованиям.

    Args:
        length: Длина здания в метрах
        width: Ширина здания в метрах
        height: Высота здания в метрах
        wall_thickness: Толщина стен в мм
        region: Регион строительства

    Returns:
        Отчёт о соответствии нормативам с рекомендациями
    """
    params = {'length': length, 'width': width, 'height': height,
              'wall_thickness': wall_thickness, 'region': region}
    errors = validate_design_rules(params)
    recommendations = get_design_recommendations(params)
    lines = []
    if not errors:
        lines.append("Все параметры соответствуют нормативным требованиям")
    else:
        lines.append("Обнаружены нарушения нормативов:")
        for e in errors:
            lines.append("  - " + e)
    if recommendations:
        lines.append("")
        lines.append("Рекомендации по оптимизации:")
        for r in recommendations:
            lines.append("  - " + r)
    return "\n".join(lines)


@mcp.tool()
def calculate_building_quantities(
    length: float, width: float, height: float, wall_thickness: int
) -> str:
    """
    Рассчитывает объёмы работ и материалов для складского здания.

    Args:
        length: Длина здания в метрах
        width: Ширина здания в метрах
        height: Высота здания в метрах
        wall_thickness: Толщина стен в мм

    Returns:
        Детальная ведомость объёмов работ
    """
    wt_m = wall_thickness / 1000
    perimeter = 2 * (length + width)
    wall_volume = perimeter * height * wt_m
    foundation_volume = perimeter * 0.5 * 0.6
    roof_area = length * width
    brick_count = wall_volume * 400
    roof_m2 = roof_area * 1.1
    return (
        "ВЕДОМОСТЬ ОБЪЁМОВ РАБОТ\n\n"
        "Размеры: {l} x {w} x {h} м, стены {wt} мм\n"
        "Периметр: {per:.1f} м\n\n"
        "Объёмы:\n"
        "  Кирпичная кладка: {wv:.2f} м3 ({bc:,.0f} шт)\n"
        "  Бетон фундамента: {fv:.2f} м3\n"
        "  Площадь кровли: {ra:.1f} м2 (материал {rm:.1f} м2)\n\n"
        "Стоимость материалов:\n"
        "  Кирпич: {bc_cost:,.0f} тг\n"
        "  Бетон: {fv_cost:,.0f} тг\n"
        "  Кровля: {rm_cost:,.0f} тг\n"
        "  ИТОГО: {total:,.0f} тг"
    ).format(
        l=length, w=width, h=height, wt=wall_thickness,
        per=perimeter, wv=wall_volume, bc=brick_count,
        fv=foundation_volume, ra=roof_area, rm=roof_m2,
        bc_cost=brick_count * 15,
        fv_cost=foundation_volume * 45000,
        rm_cost=roof_m2 * 8000,
        total=brick_count * 15 + foundation_volume * 45000 + roof_m2 * 8000,
    )


@mcp.tool()
def list_generated_projects() -> str:
    """
    Показывает список всех сгенерированных проектов (из локальной папки output).

    Returns:
        Список проектов с параметрами и датой создания
    """
    if not os.path.exists(OUTPUT_DIR):
        return "Папка проектов пуста. Создайте первый проект!"
    projects = []
    for item in os.listdir(OUTPUT_DIR):
        info_file = os.path.join(OUTPUT_DIR, item, "project_info.json")
        if os.path.exists(info_file):
            with open(info_file, 'r', encoding='utf-8') as f:
                projects.append(json.load(f))
    if not projects:
        return "Нет сгенерированных проектов."
    lines = ["Сгенерированные проекты ({0} шт):".format(len(projects)), ""]
    for i, info in enumerate(projects, 1):
        p = info.get("parameters", {})
        lines.append("{0}. {1}".format(i, info.get("project_name", "?")))
        lines.append("   Создан: " + info.get("created_date", "?")[:19])
        lines.append("   Размеры: {l}x{w}x{h} м, стены {wt} мм".format(
            l=p.get('length','?'), w=p.get('width','?'),
            h=p.get('height','?'), wt=p.get('wall_thickness','?')
        ))
        revit = info.get("revit_response", {})
        if revit.get("wall_client_ids"):
            lines.append("   Стены: " + ", ".join(revit["wall_client_ids"]))
        if revit.get("floor_client_id"):
            lines.append("   Пол: " + revit["floor_client_id"])
        lines.append("")
    return "\n".join(lines)


# ─── Фаза 3 ───────────────────────────────────────────────────

@mcp.tool()
def create_polygon_building(
    points: list, height: float, project_name: str = None,
) -> str:
    """
    Создаёт здание произвольной формы (Г, П, Т и т.д.) по списку угловых точек.

    Args:
        points: Список точек [[x, y], ...] в метрах, минимум 3.
                Контур замыкается автоматически — НЕ нужно повторять первую точку.
                Пример Г-образного здания 12×12 с вырезом 6×6 в правом верхнем углу:
                [[0,0],[12,0],[12,6],[6,6],[6,12],[0,12]]
        height: Высота здания в метрах
        project_name: Название проекта (опционально)

    Returns:
        Результат создания с client_id стен и пола
    """
    if len(points) < 3:
        return "Ошибка: минимум 3 точки, передано {0}".format(len(points))
    points_mm = [[int(p[0] * 1000), int(p[1] * 1000)] for p in points]
    result = call_revit_post("/building/create_polygon", {
        "points": points_mm, "height": int(height * 1000),
    })
    if result.get("error"):
        return "Ошибка Revit API: " + result["error"]
    wall_ids = result.get("wall_client_ids", [])
    return (
        "Полигональное здание создано!\n\n"
        "Стен: {walls}\nПол: {floor}\n\n"
        "client_id стен: {wids}\nclient_id пола: {fid}\n\n"
        "Сохраните client_id для удаления/изменения элементов."
    ).format(
        walls=result.get("walls_created", 0),
        floor="да" if result.get("floor_created") else "нет",
        wids=", ".join(wall_ids) if wall_ids else "нет данных",
        fid=result.get("floor_client_id", "нет данных"),
    )


@mcp.tool()
def setup_grid(
    x_step: float, y_step: float, x_count: int, y_count: int,
    origin_x: float = 0.0, origin_y: float = 0.0,
) -> str:
    """
    Настраивает именованную сетку осей для удобного размещения стен.
    Строки: A, B, C, ... (ось Y). Колонны: 1, 2, 3, ... (ось X).
    После настройки используйте create_wall_by_grid для создания стен.

    Args:
        x_step:   Шаг по X в метрах (расстояние между колоннами)
        y_step:   Шаг по Y в метрах (расстояние между строками)
        x_count:  Количество колонн
        y_count:  Количество строк
        origin_x: Начало по X в метрах (по умолчанию 0)
        origin_y: Начало по Y в метрах (по умолчанию 0)

    Returns:
        Карта узлов сетки с координатами
    """
    result = call_revit_post("/grid/setup", {
        "x_step_mm":   int(x_step * 1000),
        "y_step_mm":   int(y_step * 1000),
        "x_count":     x_count,
        "y_count":     y_count,
        "origin_x_mm": int(origin_x * 1000),
        "origin_y_mm": int(origin_y * 1000),
    })
    if result.get("error"):
        return "Ошибка: " + result["error"]
    nodes = result.get("nodes", {})
    lines = ["Сетка настроена! Узлов: {0}".format(result.get("nodes_count", 0)), ""]
    for name in sorted(nodes.keys()):
        coords = nodes[name]
        lines.append("  {0}: ({1:.1f}, {2:.1f}) м".format(
            name, coords[0] / 1000.0, coords[1] / 1000.0
        ))
    return "\n".join(lines)


@mcp.tool()
def create_wall_by_grid(
    from_node: str, to_node: str, height: float,
) -> str:
    """
    Создаёт стену между двумя узлами именованной сетки.
    Требует предварительной настройки сетки через setup_grid.

    Args:
        from_node: Начальный узел сетки (например "A1")
        to_node:   Конечный узел сетки (например "A3")
        height:    Высота стены в метрах

    Returns:
        Результат с client_id созданной стены
    """
    result = call_revit_post("/wall/create_by_grid", {
        "from": from_node, "to": to_node, "height": int(height * 1000),
    })
    if result.get("error"):
        return "Ошибка: " + result["error"]
    return (
        "Стена {from_node} → {to_node} создана!\n"
        "client_id: {client_id}\nВысота: {height_mm} мм"
    ).format(
        from_node=result.get("from_node", from_node),
        to_node=result.get("to_node", to_node),
        client_id=result.get("client_id", "?"),
        height_mm=result.get("height_mm", int(height * 1000)),
    )


@mcp.tool()
def create_opening(
    wall_client_id: str, family_type_name: str,
    offset_mm: int, sill_height_mm: int = 0,
) -> str:
    """
    Вставляет дверь или окно в стену.

    Args:
        wall_client_id:   client_id стены-хоста (из generate_warehouse или create_wall_by_grid)
        family_type_name: Имя типа семейства.
                          Формат: "Имя типа" или "Семейство : Имя типа".
                          Если неизвестно — передайте любое имя, в ответе будет список доступных.
        offset_mm:        Отступ от начала стены в мм (где будет центр элемента)
        sill_height_mm:   Высота нижнего края от уровня в мм.
                          0 — дверь (от пола); 900 — типовой подоконник окна.

    Returns:
        Результат с client_id вставленного элемента, либо список доступных семейств при ошибке
    """
    result = call_revit_post("/opening/create", {
        "wall_client_id":   wall_client_id,
        "family_type_name": family_type_name,
        "offset_mm":        offset_mm,
        "sill_height_mm":   sill_height_mm,
    })
    if result.get("error"):
        msg = "Ошибка: " + result["error"]
        if result.get("available_types"):
            msg += "\n\nДоступные семейства в проекте:\n"
            msg += "\n".join("  - " + t for t in result["available_types"])
        return msg
    return (
        "Элемент '{family_type}' вставлен!\n"
        "Отступ от начала стены: {offset_along_wall_mm} мм\n"
        "Высота нижнего края: {sill_height_mm} мм\n"
        "client_id: {client_id}"
    ).format(**result)


@mcp.resource("warehouse://design-rules")
def get_design_rules() -> str:
    """Справочная информация по нормативным требованиям для складских зданий."""
    return (
        "НОРМАТИВНЫЕ ТРЕБОВАНИЯ ДЛЯ СКЛАДСКИХ ЗДАНИЙ\n\n"
        "Стены: мин. 380 мм (> 10 м: 510 мм, > 15 м: расчёт)\n"
        "Фундамент: Юг 0.5 м, Север 1.2 м\n"
        "Геометрия: мин. 6×6 м, макс. 60×40 м, высота 3–12 м"
    )


if __name__ == "__main__":
    mcp.run()
