# Warehouse Generator MCP — Revit Integration

Claude Desktop / Claude Code → MCP-сервер (Python 3) → HTTP → pyRevit Routes (IronPython 2.7 внутри Revit) → Revit API.

Создание и управление BIM-элементами (склады, стены, полы, уровни, окна, двери) командами на естественном языке.

---

## Архитектура

```
Claude Code / Claude Desktop
      │  MCP (stdio)  [инструмент: warehouse-revit]
      ▼
mcp/warehouse_generator_mcp.py          (Python 3)
      │  HTTP POST/GET  →  http://192.168.31.44:48884/revit-mcp-v1
      ▼
pyRevit Routes (IronPython 2.7, внутри Revit 2021)
revit_extension/startup.py              (только маршруты)
      │  импортирует модули из lib/
      ▼
lib/geometry_utils.py  /  lib/revit_builders.py  /  lib/validation.py  /  lib/state_manager.py
      │  Revit API (транзакция)
      ▼
Autodesk Revit 2021
```

---

## Структура репозитория

```
warehouse-generator-mcp/
├── README.md
├── IMPROVEMENT_PLAN.md
├── mcp/
│   └── warehouse_generator_mcp.py      # MCP-сервер (Python 3)
└── revit_extension/
    ├── startup.py                      # Revit-сторона (маршруты)
    └── lib/
        ├── __init__.py
        ├── geometry_utils.py           # mm_to_ft, wall lines, grid, polygon
        ├── revit_builders.py           # create_warehouse, create_level, create_opening...
        ├── validation.py               # ShortCurveTolerance, polygon checks
        └── state_manager.py            # in-memory {client_id → revit_id}
```

---

## Локальные пути (рабочая машина)

| Файл репо | Локальный путь |
|-----------|----------------|
| `mcp/warehouse_generator_mcp.py` | `C:\GEMINI\projects\warehouse_generator_project\warehouse_generator_mcp.py` |
| `revit_extension/startup.py` | `C:\MCP\WORKING_RevitMCP\WorkingRevitMCP.extension\startup.py` |
| `revit_extension/lib/*.py` | `C:\MCP\WORKING_RevitMCP\WorkingRevitMCP.extension\lib\*.py` |

---

## MCP-инструменты

| Инструмент | Описание |
|---|---|
| `generate_warehouse(length, width, height, wall_thickness, region)` | Создаёт прямоугольный склад. Возвращает client_id стен и пола. |
| `get_model_info()` | Уровни, типы стен и полов открытого документа |
| `create_level(elevation_mm, name)` | Создаёт уровень. Возвращает client_id. |
| `delete_element(client_id)` | Удаляет элемент из Revit |
| `list_elements()` | Список всех элементов сессии с client_id |
| `validate_building_parameters(...)` | Проверка нормативов (без Revit) |
| `calculate_building_quantities(...)` | Ведомость материалов (без Revit) |
| `list_generated_projects()` | Список сохранённых проектов из output/ |
| `create_polygon_building(points, height)` | Г/П/Т-образное здание по точкам [[x,y],...] в метрах |
| `setup_grid(x_step, y_step, x_count, y_count)` | Настроить именованную сетку осей |
| `create_wall_by_grid(from_node, to_node, height)` | Стена между узлами "A1"→"A3" |
| `create_opening(wall_client_id, family_type_name, offset_mm, sill_height_mm)` | Дверь или окно в стену |

---

## API-маршруты Revit (port 48884)

Базовый URL: `http://192.168.31.44:48884/revit-mcp-v1`

| Метод | Маршрут | Описание |
|-------|---------|----------|
| GET | `/status/` | Статус сервера, версия 3.0 |
| GET | `/model_info/` | Уровни, типы стен и полов |
| POST | `/warehouse/create` | Создать прямоугольный склад (length/width/height в мм) |
| POST | `/level/create` | Создать уровень (elevation мм, name) |
| POST | `/element/delete` | Удалить элемент по client_id |
| GET | `/elements/list` | Список элементов сессии |
| POST | `/building/create_polygon` | Полигональное здание по точкам мм |
| POST | `/grid/setup` | Настроить виртуальную сетку осей |
| GET | `/grid/nodes` | Текущая виртуальная сетка |
| GET | `/grid/revit` | Оси из документа Revit |
| POST | `/wall/create_by_grid` | Стена по узлам сетки |
| POST | `/opening/create` | Вставить окно/дверь |

---

## Быстрый старт

### 1. Регистрация MCP в Claude Code

```bash
claude mcp add --scope user warehouse-revit python "C:\GEMINI\projects\warehouse_generator_project\warehouse_generator_mcp.py"
```

- `--scope user` обязателен
- После — перезапустить Claude Code
- В шапке должно появиться `warehouse-revit · connected`

### 2. Проверка Revit API

```bash
curl http://192.168.31.44:48884/revit-mcp-v1/status/
# {"status": "active", "api": "revit-mcp-v1", "version": "3.0"}
```

### 3. Создать склад 42×18×8 м

```bash
curl -X POST http://192.168.31.44:48884/revit-mcp-v1/warehouse/create \
  -H "Content-Type: application/json" \
  -d '{"length": 42000, "width": 18000, "height": 8000}'
```

---

## Критические правила

1. `%APPDATA%\pyRevit\Extensions\` должна быть **пустой** — иначе грузится старый код
2. Путь поиска расширений = `C:\MCP\WORKING_RevitMCP` (родитель, не сама папка)
3. `request.data` в обработчиках уже dict — не вызывать `json.loads()`
4. Стены создавать встык (без gap), JoinGeometry соединяет углы
5. Валидация геометрии — ДО открытия транзакции
6. После правки `startup.py` — только полный рестарт Revit
7. IronPython: срезы C# коллекций — `list(col)[:N]`, не `col[:N]`

---

## Статус фаз

| Фаза | Описание | Статус |
|------|----------|--------|
| 1 | lib/ структура, геометрия, валидация, state_manager | ✅ |
| 2 | create_level, delete_element, list_elements, get_model_info | ✅ |
| 3 | Grid, полигоны, JoinGeometry, окна/двери | ✅ |
| 4 | Extensible Storage, безопасное обновление элементов | ⏳ |
| 5 | Проверка коллизий, External Events | ⏳ |

---

## pyRevit

- Clone: `C:\Users\ART\AppData\Roaming\pyRevit-Master` (v4.8.12, IPY277)
- Revit: Autodesk Revit 2021 (21.1.21.45)
- Extension search path: `C:\MCP\WORKING_RevitMCP`
