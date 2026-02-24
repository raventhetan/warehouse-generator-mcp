# -*- coding: utf-8 -*-
"""
pyRevit MCP Routes - startup.py  version 3.0
Только регистрация маршрутов. Бизнес-логика — в lib/.
IronPython 2.7 compatible
"""

import sys
import os

_lib_path = os.path.join(os.path.dirname(__file__), 'lib')
if _lib_path not in sys.path:
    sys.path.insert(0, _lib_path)

from pyrevit import routes, revit, DB
import revit_builders as builders
import geometry_utils as gu
import state_manager as sm


def register_routes():
    api = routes.API('revit-mcp-v1')

    @api.route('/status/', methods=["GET"])
    def get_status(doc=None):
        doc = doc or revit.doc
        return {
            "status": "active",
            "document_title": doc.Title if doc else "no document",
            "api": "revit-mcp-v1",
            "version": "3.0"
        }

    @api.route('/model_info/', methods=["GET"])
    def get_model_info(doc=None):
        doc = doc or revit.doc
        levels = DB.FilteredElementCollector(doc).OfClass(DB.Level).ToElements()
        level_info = [
            {"name": DB.Element.Name.__get__(l), "elevation_mm": round(l.Elevation / 0.00328084)}
            for l in levels
        ]
        wall_types = DB.FilteredElementCollector(doc).OfClass(DB.WallType).ToElements()
        floor_types = DB.FilteredElementCollector(doc).OfClass(DB.FloorType).ToElements()
        return {
            "document_title": doc.Title,
            "levels": level_info,
            "wall_types": [DB.Element.Name.__get__(wt) for wt in list(wall_types)[:10]],
            "floor_types": [DB.Element.Name.__get__(ft) for ft in list(floor_types)[:5]],
        }

    @api.route('/warehouse/create', methods=["POST"])
    def create_warehouse(request, doc=None):
        doc = doc or revit.doc
        data = request.data if isinstance(request.data, dict) else {}
        return builders.create_warehouse(
            doc,
            length_mm=data.get('length', 6000),
            width_mm=data.get('width', 6000),
            height_mm=data.get('height', 3000),
        )

    @api.route('/level/create', methods=["POST"])
    def create_level(request, doc=None):
        doc = doc or revit.doc
        data = request.data if isinstance(request.data, dict) else {}
        return builders.create_level(
            doc,
            elevation_mm=data.get('elevation', 3000),
            name=data.get('name', None),
        )

    @api.route('/element/delete', methods=["POST"])
    def delete_element(request, doc=None):
        doc = doc or revit.doc
        data = request.data if isinstance(request.data, dict) else {}
        client_id = data.get('client_id')
        if not client_id:
            return {"error": "client_id is required"}
        return builders.delete_element(doc, client_id)

    @api.route('/elements/list', methods=["GET"])
    def list_elements(doc=None):
        elements = sm.list_elements()
        return {"count": len(elements), "elements": elements}

    # ═══ Фаза 3 ═══════════════════════════════════════════════

    @api.route('/building/create_polygon', methods=["POST"])
    def create_polygon_building(request, doc=None):
        doc = doc or revit.doc
        data = request.data if isinstance(request.data, dict) else {}
        points = data.get('points', [])
        if not points:
            return {"error": "points list is required"}
        return builders.create_polygon_building(doc, points, data.get('height', 3000))

    @api.route('/grid/setup', methods=["POST"])
    def setup_grid(request, doc=None):
        data = request.data if isinstance(request.data, dict) else {}
        x_step   = data.get('x_step_mm',   6000)
        y_step   = data.get('y_step_mm',   6000)
        x_count  = data.get('x_count',     5)
        y_count  = data.get('y_count',     4)
        origin_x = data.get('origin_x_mm', 0)
        origin_y = data.get('origin_y_mm', 0)
        nodes = gu.build_grid_map(x_step, y_step, x_count, y_count, origin_x, origin_y)
        sm.set_grid(nodes, {"x_step_mm": x_step, "y_step_mm": y_step,
                            "x_count": x_count, "y_count": y_count})
        return {"success": True, "nodes_count": len(nodes), "nodes": nodes}

    @api.route('/grid/nodes', methods=["GET"])
    def get_grid_nodes(doc=None):
        nodes = sm.get_all_grid_nodes()
        return {"nodes_count": len(nodes), "nodes": nodes}

    @api.route('/grid/revit', methods=["GET"])
    def get_revit_grids(doc=None):
        doc = doc or revit.doc
        grids = gu.read_revit_grids(doc)
        return {"grids_count": len(grids), "grids": grids}

    @api.route('/wall/create_by_grid', methods=["POST"])
    def create_wall_by_grid(request, doc=None):
        doc = doc or revit.doc
        data = request.data if isinstance(request.data, dict) else {}
        from_node = data.get('from')
        to_node   = data.get('to')
        if not from_node or not to_node:
            return {"error": "'from' and 'to' node names are required"}
        from_coords = sm.get_grid_node(from_node)
        to_coords   = sm.get_grid_node(to_node)
        if from_coords is None:
            return {"error": "Node '{0}' not found. Call /grid/setup first.".format(from_node)}
        if to_coords is None:
            return {"error": "Node '{0}' not found. Call /grid/setup first.".format(to_node)}
        result = builders.create_wall_single(doc, from_coords, to_coords, data.get('height', 3000))
        if result.get("success"):
            result["from_node"] = from_node
            result["to_node"]   = to_node
        return result

    @api.route('/opening/create', methods=["POST"])
    def create_opening(request, doc=None):
        doc = doc or revit.doc
        data = request.data if isinstance(request.data, dict) else {}
        wall_client_id   = data.get('wall_client_id')
        family_type_name = data.get('family_type_name')
        if not wall_client_id:
            return {"error": "wall_client_id is required"}
        if not family_type_name:
            return {"error": "family_type_name is required"}
        return builders.create_opening(
            doc, wall_client_id, family_type_name,
            data.get('offset_mm', 1000), data.get('sill_height_mm', 0)
        )


register_routes()
