# graphics_editor/controllers/scene_controller.py
import math
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QMessageBox, QGraphicsPathItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPolygonItem
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF, QPainterPath

from ..models import Point, Line, Polygon, BezierCurve
# Correct way to import all model names for DATA_OBJECT_TYPES tuple creation
from ..models import __all__ as model_names_list # Get the list of names
# Dynamically create DATA_OBJECT_TYPES
# This assumes your models.__init__.py correctly populates __all__
# and that models are in graphics_editor.models
_models_module = __import__('graphics_editor.models', fromlist=model_names_list)
DATA_OBJECT_TYPES = tuple(getattr(_models_module, name) for name in model_names_list)


from ..state_manager import EditorStateManager, LineClippingAlgorithm
from ..utils import clipping as clp

DataObject = Union[Point, Line, Polygon, BezierCurve]


class SceneController(QObject):
    scene_modified = pyqtSignal(bool)

    def __init__(self, scene: QGraphicsScene, state_manager: EditorStateManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager
        self._data_object_to_item_map: Dict[DataObject, QGraphicsItem] = {}

        self._clip_rect_tuple: clp.ClipRect = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()
        self.bezier_clipping_samples = 20

        self._state_manager.clip_rect_changed.connect(self._update_clipper_state)
        self._state_manager.line_clipper_changed.connect(self._update_clipper_state)

    def _update_clipper_state(self):
        self._clip_rect_tuple = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()

    def _get_clip_rect_tuple(self) -> clp.ClipRect:
        rect = self._state_manager.clip_rect()
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _get_clipper_function(self):
        algo = self._state_manager.selected_line_clipper()
        return clp.cohen_sutherland if algo == LineClippingAlgorithm.COHEN_SUTHERLAND else clp.liang_barsky

    def _is_bezier_fully_inside(self, bezier: BezierCurve, clip_rect_tuple: clp.ClipRect) -> bool:
        if not bezier.points:
            return False
        for cp_model in bezier.points:
            if clp.clip_point(cp_model.get_coords(), clip_rect_tuple) is None:
                return False 
        return True 

    def _clip_data_object(self, data_object: DataObject) -> Tuple[Optional[DataObject], bool]:
        clipped_result: Optional[DataObject] = None
        needs_replacement = False 
        clip_rect_tuple = self._clip_rect_tuple 
        line_clipper = self._clipper_func

        try:
            if isinstance(data_object, Point):
                clipped_coords = clp.clip_point(data_object.get_coords(), clip_rect_tuple)
                if clipped_coords:
                    clipped_result = Point(clipped_coords[0], clipped_coords[1], data_object.color)
            elif isinstance(data_object, Line):
                clipped_segment_coords = line_clipper(data_object.start.get_coords(), data_object.end.get_coords(), clip_rect_tuple)
                if clipped_segment_coords:
                    p1_coords, p2_coords = clipped_segment_coords
                    start_pt = Point(p1_coords[0], p1_coords[1], data_object.color)
                    end_pt = Point(p2_coords[0], p2_coords[1], data_object.color)
                    clipped_result = Line(start_pt, end_pt, data_object.color)
            elif isinstance(data_object, Polygon):
                is_fully_inside = True
                for p_coord in data_object.get_coords():
                    if clp.clip_point(p_coord, clip_rect_tuple) is None:
                        is_fully_inside = False
                        break
                
                if is_fully_inside and not data_object.is_open: 
                    clipped_result = data_object 
                    needs_replacement = False
                else:
                    clipped_vertices_coords = clp.sutherland_hodgman(data_object.get_coords(), clip_rect_tuple)
                    min_points = 2 if data_object.is_open else 3
                    if len(clipped_vertices_coords) >= min_points:
                        clipped_points_models = [Point(x, y, data_object.color) for x, y in clipped_vertices_coords]
                        clipped_result = Polygon(
                            clipped_points_models, is_open=data_object.is_open,
                            color=data_object.color, is_filled=data_object.is_filled
                        )
                        if len(clipped_points_models) != len(data_object.points):
                            needs_replacement = True 
            
            elif isinstance(data_object, BezierCurve):
                if self._is_bezier_fully_inside(data_object, clip_rect_tuple):
                    clipped_result = data_object 
                    needs_replacement = False
                else:
                    sampled_qpoints = data_object.sample_curve(self.bezier_clipping_samples)
                    if len(sampled_qpoints) < 2: 
                        clipped_result = None
                        needs_replacement = True 
                    else:
                        raw_polyline_coords: List[Tuple[float, float]] = [
                            (qp.x(), qp.y()) for qp in sampled_qpoints
                        ]
                        clipped_sh_coords = clp.sutherland_hodgman(raw_polyline_coords, clip_rect_tuple)

                        if len(clipped_sh_coords) >= 2:
                            clipped_points_models = [
                                Point(x, y, data_object.color) for x, y in clipped_sh_coords
                            ]
                            clipped_result = Polygon(
                                clipped_points_models,
                                is_open=True,
                                color=data_object.color,
                                is_filled=False
                            )
                            needs_replacement = True  
                        else: 
                            clipped_result = None
                            needs_replacement = True 
            
            return clipped_result, needs_replacement

        except Exception as e:
            print(f"Error during clipping of {type(data_object).__name__}: {e}")
            return None, False 

    def add_object(self, data_object: DataObject, mark_modified: bool = True):
        if not isinstance(data_object, DATA_OBJECT_TYPES):
            print(f"Warning: Attempted to add unsupported object type {type(data_object)}")
            return

        clipped_data_object, _ = self._clip_data_object(data_object) 

        if clipped_data_object:
            try:
                graphics_item = clipped_data_object.create_graphics_item()
                graphics_item.setData(0, clipped_data_object) 
                self._scene.addItem(graphics_item)
                self._data_object_to_item_map[clipped_data_object] = graphics_item
                if mark_modified:
                    self.scene_modified.emit(True) 
            except Exception as e:
                 QMessageBox.critical(None, "Erro ao Adicionar Item",
                     f"Não foi possível criar item gráfico para {type(clipped_data_object).__name__}: {e}")

    def remove_items(self, items_to_remove: List[QGraphicsItem], mark_modified: bool = True) -> int:
        items_removed_count = 0
        for item in items_to_remove:
            if item and item.scene(): 
                data_obj = self.get_object_for_item(item) # FIXED: Added get_object_for_item method
                if data_obj is not None and data_obj in self._data_object_to_item_map:
                    del self._data_object_to_item_map[data_obj]
                self._scene.removeItem(item)
                items_removed_count += 1

        if items_removed_count > 0 and mark_modified:
            self.scene_modified.emit(True) 

        return items_removed_count

    def clear_scene(self, mark_modified: bool = True):
        items_to_remove = list(self._data_object_to_item_map.values())
        for item in items_to_remove:
            if item and item.scene():
                self._scene.removeItem(item)

        cleared_count = len(self._data_object_to_item_map)
        self._data_object_to_item_map.clear()

        if cleared_count > 0 and mark_modified:
             self.scene_modified.emit(True) 

    def update_object_item(self, modified_data_object: DataObject, mark_modified: bool = True):
        if not isinstance(modified_data_object, DATA_OBJECT_TYPES):
            print(f"Warning: update_object_item called with invalid type {type(modified_data_object)}")
            return

        graphics_item = self.get_item_for_object(modified_data_object) # FIXED: Added get_item_for_object method

        if not graphics_item or not graphics_item.scene():
            print(f"Warning: Graphics item for {modified_data_object} not found or not in scene during update.")
            return

        clipped_data_object, needs_replacement = self._clip_data_object(modified_data_object)

        try:
            if clipped_data_object is None:
                self.remove_items([graphics_item], mark_modified=mark_modified) 
            elif needs_replacement:
                if modified_data_object in self._data_object_to_item_map:
                    del self._data_object_to_item_map[modified_data_object]
                self._scene.removeItem(graphics_item)
                self.add_object(clipped_data_object, mark_modified=mark_modified)
            else:
                graphics_item.prepareGeometryChange()
                if clipped_data_object is not modified_data_object:
                    if modified_data_object in self._data_object_to_item_map:
                        del self._data_object_to_item_map[modified_data_object]
                    self._data_object_to_item_map[clipped_data_object] = graphics_item
                    graphics_item.setData(0, clipped_data_object)

                self._update_graphics_item_geometry(graphics_item, clipped_data_object)
                self._apply_style_to_item(graphics_item, clipped_data_object)
                graphics_item.update() 
                if mark_modified:
                    self.scene_modified.emit(True) 

        except Exception as e:
             QMessageBox.critical(None, "Erro ao Atualizar Item",
                 f"Falha ao atualizar item {type(graphics_item).__name__} pós-modificação: {e}")

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        try:
            if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
                size, offset = data.GRAPHICS_SIZE, data.GRAPHICS_SIZE / 2.0
                new_rect = QRectF(data.x - offset, data.y - offset, size, size)
                if item.rect() != new_rect: item.setRect(new_rect)
            elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
                new_line = QLineF(data.start.to_qpointf(), data.end.to_qpointf())
                if item.line() != new_line: item.setLine(new_line)
            elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
                new_polygon_qf = QPolygonF([p.to_qpointf() for p in data.points])
                if item.polygon() != new_polygon_qf: item.setPolygon(new_polygon_qf)
            elif isinstance(data, Polygon) and isinstance(item, QGraphicsPathItem):
                 new_path = QPainterPath()
                 if data.points and len(data.points) > 0: 
                     new_path.moveTo(data.points[0].to_qpointf())
                     for p_model in data.points[1:]:
                         new_path.lineTo(p_model.to_qpointf())
                 if item.path() != new_path: item.setPath(new_path)
            elif isinstance(data, BezierCurve) and isinstance(item, QGraphicsPathItem):
                 new_path = QPainterPath()
                 if data.points:
                      new_path.moveTo(data.points[0].to_qpointf())
                      num_segments = data.get_num_segments()
                      for i in range(num_segments):
                           p1_idx, p2_idx, p3_idx = 3*i + 1, 3*i + 2, 3*i + 3
                           if p3_idx < len(data.points):
                                ctrl1 = data.points[p1_idx].to_qpointf()
                                ctrl2 = data.points[p2_idx].to_qpointf()
                                endpt = data.points[p3_idx].to_qpointf()
                                new_path.cubicTo(ctrl1, ctrl2, endpt)
                 if item.path() != new_path: item.setPath(new_path)
        except Exception as e:
            print(f"ERROR in _update_graphics_item_geometry for {type(data)}/{type(item)}: {e}")

    def _apply_style_to_item(self, item: QGraphicsItem, data: DataObject):
        if not hasattr(data, "color"): return
        color = data.color if isinstance(data.color, QColor) and data.color.isValid() else QColor(Qt.black)
        pen = QPen(Qt.NoPen) 
        brush = QBrush(Qt.NoBrush) 

        if isinstance(data, Point):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(data, Line):
            pen = QPen(color, data.GRAPHICS_WIDTH, Qt.SolidLine)
        elif isinstance(data, Polygon):
            pen = QPen(color, data.GRAPHICS_BORDER_WIDTH)
            if data.is_open: pen.setStyle(Qt.DashLine)
            else: 
                pen.setStyle(Qt.SolidLine)
                if data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color); fill_color.setAlphaF(data.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
        elif isinstance(data, BezierCurve):
            pen = QPen(color, data.GRAPHICS_WIDTH, Qt.SolidLine)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setCapStyle(Qt.RoundCap)

        if hasattr(item, "setPen") and item.pen() != pen: item.setPen(pen)
        if hasattr(item, "setBrush") and item.brush() != brush: item.setBrush(brush)

    # --- ADDED LOOKUP METHODS ---
    def get_item_for_object(self, data_object: DataObject) -> Optional[QGraphicsItem]:
        """Retrieves the QGraphicsItem associated with a DataObject."""
        return self._data_object_to_item_map.get(data_object)

    def get_object_for_item(self, item: QGraphicsItem) -> Optional[DataObject]:
        """Retrieves the DataObject associated with a QGraphicsItem."""
        data = item.data(0)
        if isinstance(data, DATA_OBJECT_TYPES):
            # Optional: Consistency check if the item is indeed the one in the map for this data object
            # if data in self._data_object_to_item_map and self._data_object_to_item_map[data] is item:
            #     return data
            # else: # Mismatch or item not directly managed by this controller via the map (e.g. temp items)
            #     # For items managed by this controller, data(0) should be the key in the map.
            #     # print(f"Warning: Item data found, but map consistency check failed or item not in map values for key {data}")
            #     pass # Fall through to return data if it's a valid DataObject type
            return data
        return None
    # --- END ADDED LOOKUP METHODS ---

    def get_all_data_objects(self) -> List[DataObject]:
        return list(self._data_object_to_item_map.keys())

    def get_selected_data_objects(self) -> List[DataObject]:
        selected_objects = []
        for item in self._scene.selectedItems():
            data_obj = self.get_object_for_item(item) # FIXED: Added get_object_for_item method
            if data_obj:
                selected_objects.append(data_obj)
        return selected_objects