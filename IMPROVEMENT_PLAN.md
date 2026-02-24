# План улучшения проекта Revit MCP
_Составлен: 2026-02-24_

## Текущее состояние (до Фазы 1)
- `startup.py` — монолитный файл: маршруты + логика + API
- `create_warehouse` создаёт 4 стены с `gap_ft` зазорами (баг — щели в углах)
- `NewFloor()` использует устаревший API через `CurveArray`
- Нет отслеживания созданных элементов (нет state)
- Нет валидации геометрии

---

## ФАЗА 1 — Правильный фундамент [КРИТИЧЕСКИЙ]

### 1.1 Рефакторинг → lib/ структура
- [x] Создать папку `lib/` внутри расширения
- [x] `__init__.py`
- [x] `geometry_utils.py` — mm_to_ft, build_curve_loop, get_wall_midpoint
- [x] `revit_builders.py` — create_walls, create_floor, create_level
- [x] `validation.py` — check_segment_length, check_loop_closed
- [x] `state_manager.py` — in-memory {client_id → ElementId}
- [x] `startup.py` — только sys.path + register_routes()

### 1.2 Исправить баг gap_ft + JoinGeometry
- [x] Убрать зазоры (gap_ft), создавать стены встык
- [x] Вызывать JoinGeometryUtils.JoinGeometry() после транзакции

### 1.3 Валидация длин сегментов
- [x] check_segment_length через Application.ShortCurveTolerance
- [x] Обработка ошибки "line too short" до создания элемента

### 1.4 In-memory State Manager
- [x] Словарь {client_id: {revit_id, type, name, created_at}}
- [x] register_element(), find_element(), list_elements()
- [x] Возвращать client_id в ответе каждого create-запроса

---

## ФАЗА 2 — Многоэтажность и MCP-расширение [ВЫСОКИЙ]

### 2.1 Управление уровнями
- [x] POST /level/create — создать уровень на заданной высоте
- [x] MCP-инструмент create_level

### 2.2 Новые MCP-инструменты
- [x] delete_element
- [x] list_elements
- [x] get_model_info (обновить)

### 2.3 Удаление элементов
- [x] POST /element/delete по client_id
- [x] doc.Delete(elem.Id) внутри транзакции

---

## ФАЗА 3 — Сложные формы и окна/двери [СРЕДНИЙ]

### 3.1 Grid-based координаты
- [x] Читать оси проекта — GET /grid/revit (read_revit_grids)
- [x] Строить виртуальную сетку — build_grid_map в geometry_utils
- [x] POST /grid/setup — задать сетку (x_step, y_step, x_count, y_count)
- [x] GET /grid/nodes — текущая сетка
- [x] POST /wall/create_by_grid — стена по узлам "A1"→"A3"
- [x] MCP: setup_grid, create_wall_by_grid

### 3.2 Полигональные контуры (Г, П, Т-форма)
- [x] build_curve_array_from_points() + get_wall_lines_from_points() в geometry_utils
- [x] check_polygon_closed, check_polygon_segments_mm в validation
- [x] POST /building/create_polygon — N стен + пол по контуру
- [x] MCP: create_polygon_building

### 3.3 JoinGeometry автоматически
- [x] _try_join_pair (BoundingBox check + JoinGeometry)
- [x] _auto_join_adjacent — соединяет смежные стены в списке
- [x] Применяется в create_warehouse и create_polygon_building

### 3.4 Окна и двери
- [x] POST /opening/create — окно/дверь в стене
- [x] Поиск хоста через state_manager (find_revit_element)
- [x] FamilySymbol поиск по "Тип" или "Семейство : Тип"
- [x] Точка вставки: start + direction * offset_ft
- [x] MCP: create_opening (возвращает список доступных семейств при ошибке)

---

## ФАЗА 4 — Надёжность и CRUD [СРЕДНИЙ]

### 4.1 Extensible Storage [СЛОЖНОСТЬ: Высокая]
- [ ] Создать Schema с фиксированным GUID
- [ ] Записывать client_id в каждый созданный элемент
- [ ] ExtensibleStorageFilter для поиска
- [ ] Пережить рестарт Revit

### 4.2 Безопасное обновление элементов [СЛОЖНОСТЬ: Средняя-Высокая]
- [ ] POST /element/update
- [ ] Длина → MakeBound (не заменять кривую напрямую)
- [ ] Тип → wall.ChangeTypeId()
- [ ] Позиция → ElementTransformUtils.MoveElement()

---

## ФАЗА 5 — Архитектурная масштабируемость [НИЗКИЙ]

### 5.1 Проверка коллизий [СЛОЖНОСТЬ: Высокая]
- [ ] BoundingBoxIntersectsFilter (быстрый)
- [ ] ElementIntersectsSolidFilter (точный)
- [ ] GeometryCreationUtilities.CreateExtrusionGeometry

### 5.2 Асинхронная очередь (External Events) [СЛОЖНОСТЬ: Очень высокая]
- [ ] task_queue глобальная
- [ ] IExternalEventHandler + ExternalEvent.Raise()
- [ ] GET /task/status?id=... — опрос результата
- [ ] Немедленный ответ {"status": "queued", "task_id": "..."}

---

## Прогресс

| Фаза | Статус |
|------|--------|
| Фаза 1 | ✅ Выполнено |
| Фаза 2 | ✅ Выполнено |
| Фаза 3 | ✅ Выполнено |
| Фаза 4 | ⏳ Ожидает |
| Фаза 5 | ⏳ Ожидает |
