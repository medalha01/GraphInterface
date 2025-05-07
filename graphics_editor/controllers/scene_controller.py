# graphics_editor/controllers/scene_controller.py
import math
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsItem,
    QMessageBox,
    QGraphicsPathItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF, QPainterPath

from ..models import Point, Line, Polygon, BezierCurve
from ..models import __all__ as model_names_list

_models_module = __import__("graphics_editor.models", fromlist=model_names_list)
DATA_OBJECT_TYPES = tuple(getattr(_models_module, name) for name in model_names_list)

from ..state_manager import EditorStateManager, LineClippingAlgorithm
from ..utils import clipping as clp

DataObject = Union[Point, Line, Polygon, BezierCurve]

# Keys for QGraphicsItem data
SC_ORIGINAL_OBJECT_KEY = Qt.UserRole + 1  # Stores the original DataObject instance
SC_CURRENT_REPRESENTATION_KEY = 0  # Stores the current visual DataObject (e.g., a clipped version or Polygon for Bezier)
SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY = (
    Qt.UserRole + 2
)  # Flag: True if item is a Polygon representing a clipped Bezier


class SceneController(QObject):
    scene_modified = pyqtSignal(bool)  # True if requires saving

    def __init__(
        self,
        scene: QGraphicsScene,
        state_manager: EditorStateManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager
        # Map: id(original_DataObject) -> QGraphicsItem
        self._id_to_item_map: Dict[int, QGraphicsItem] = {}

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
        return (
            clp.cohen_sutherland
            if algo == LineClippingAlgorithm.COHEN_SUTHERLAND
            else clp.liang_barsky
        )

    def _is_bezier_fully_inside(
        self, bezier: BezierCurve, clip_rect_tuple: clp.ClipRect
    ) -> bool:
        if not bezier.points:
            return False
        for cp_model in bezier.points:
            if clp.clip_point(cp_model.get_coords(), clip_rect_tuple) is None:
                return False
        return True

    def _clip_data_object(
        self, original_data_object: DataObject
    ) -> Tuple[Optional[DataObject], bool]:
        """
        Clips the DataObject.
        Returns: (clipped_display_object_or_None, needs_item_replacement)
        'needs_item_replacement' is True if the visual representation type changes (e.g., Bezier -> Polygon).
        """
        clipped_display_object: Optional[DataObject] = None
        needs_item_replacement = False
        clip_rect_tuple = self._clip_rect_tuple
        line_clipper = self._clipper_func

        try:
            if isinstance(original_data_object, Point):
                clipped_coords = clp.clip_point(
                    original_data_object.get_coords(), clip_rect_tuple
                )
                if clipped_coords:
                    clipped_display_object = Point(
                        clipped_coords[0], clipped_coords[1], original_data_object.color
                    )
            elif isinstance(original_data_object, Line):
                clipped_segment_coords = line_clipper(
                    original_data_object.start.get_coords(),
                    original_data_object.end.get_coords(),
                    clip_rect_tuple,
                )
                if clipped_segment_coords:
                    p1_coords, p2_coords = clipped_segment_coords
                    start_pt = Point(
                        p1_coords[0], p1_coords[1], original_data_object.color
                    )
                    end_pt = Point(
                        p2_coords[0], p2_coords[1], original_data_object.color
                    )
                    clipped_display_object = Line(
                        start_pt, end_pt, original_data_object.color
                    )
            elif isinstance(original_data_object, Polygon):
                is_fully_inside = True
                for p_coord in original_data_object.get_coords():
                    if clp.clip_point(p_coord, clip_rect_tuple) is None:
                        is_fully_inside = False
                        break

                if is_fully_inside and not original_data_object.is_open:
                    clipped_display_object = original_data_object  # No change
                else:
                    clipped_vertices_coords = clp.sutherland_hodgman(
                        original_data_object.get_coords(), clip_rect_tuple
                    )
                    min_points = 2 if original_data_object.is_open else 3
                    if len(clipped_vertices_coords) >= min_points:
                        clipped_points_models = [
                            Point(x, y, original_data_object.color)
                            for x, y in clipped_vertices_coords
                        ]
                        clipped_display_object = Polygon(
                            clipped_points_models,
                            is_open=original_data_object.is_open,
                            color=original_data_object.color,
                            is_filled=original_data_object.is_filled,
                        )
                        # Replacement not strictly needed if it's still a Polygon, but geometry changed.
                        # The 'needs_replacement' flag primarily for type changes.
                    # else: clipped_display_object remains None

            elif isinstance(original_data_object, BezierCurve):
                if self._is_bezier_fully_inside(original_data_object, clip_rect_tuple):
                    clipped_display_object = original_data_object  # No change
                else:  # Bezier needs clipping, represent as polyline
                    sampled_qpoints = original_data_object.sample_curve(
                        self.bezier_clipping_samples
                    )
                    if len(sampled_qpoints) < 2:
                        clipped_display_object = None
                    else:
                        raw_polyline_coords: List[Tuple[float, float]] = [
                            (qp.x(), qp.y()) for qp in sampled_qpoints
                        ]
                        clipped_sh_coords = clp.sutherland_hodgman(
                            raw_polyline_coords, clip_rect_tuple
                        )

                        if len(clipped_sh_coords) >= 2:
                            clipped_points_models = [
                                Point(x, y, original_data_object.color)
                                for x, y in clipped_sh_coords
                            ]
                            # This is now a Polygon visually
                            clipped_display_object = Polygon(
                                clipped_points_models,
                                is_open=True,
                                color=original_data_object.color,
                                is_filled=False,
                            )
                            needs_item_replacement = (
                                True  # Type changed from Bezier to Polygon for display
                            )
                        # else: clipped_display_object remains None

            return clipped_display_object, needs_item_replacement

        except Exception as e:
            print(
                f"Error during clipping of {type(original_data_object).__name__}: {e}"
            )
            return None, False

    def add_object(
        self, original_data_object: DataObject, mark_modified: bool = True
    ) -> Optional[QGraphicsItem]:
        if not isinstance(original_data_object, DATA_OBJECT_TYPES):
            print(
                f"Warning: Attempted to add unsupported object type {type(original_data_object)}"
            )
            return None

        item_id = id(original_data_object)
        if item_id in self._id_to_item_map:
            print(
                f"Warning: Object with id {item_id} already in scene. Re-adding not supported this way."
            )
            # Potentially update it instead, or disallow. For now, return existing.
            return self._id_to_item_map[item_id]

        display_data_object, item_type_changed_on_clip = self._clip_data_object(
            original_data_object
        )

        if display_data_object:
            try:
                graphics_item = display_data_object.create_graphics_item()
                graphics_item.setData(SC_ORIGINAL_OBJECT_KEY, original_data_object)
                graphics_item.setData(
                    SC_CURRENT_REPRESENTATION_KEY, display_data_object
                )
                if isinstance(original_data_object, BezierCurve) and isinstance(
                    display_data_object, Polygon
                ):
                    graphics_item.setData(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, True)
                else:
                    graphics_item.setData(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, False)

                self._scene.addItem(graphics_item)
                self._id_to_item_map[item_id] = graphics_item
                if mark_modified:
                    self.scene_modified.emit(True)
                return graphics_item
            except Exception as e:
                QMessageBox.critical(
                    None,
                    "Erro ao Adicionar Item",
                    f"Não foi possível criar item gráfico para {type(display_data_object).__name__}: {e}",
                )

        if mark_modified:  # Object was fully clipped out or failed to create
            self.scene_modified.emit(
                True
            )  # Still a modification if an attempt was made
        return None

    def remove_data_objects(
        self, data_objects_to_remove: List[DataObject], mark_modified: bool = True
    ) -> int:
        removed_count = 0
        for data_obj in data_objects_to_remove:
            item_id = id(data_obj)
            graphics_item = self._id_to_item_map.pop(item_id, None)
            if graphics_item and graphics_item.scene():
                self._scene.removeItem(graphics_item)
                removed_count += 1

        if removed_count > 0 and mark_modified:
            self.scene_modified.emit(True)
        return removed_count

    def clear_scene(self, mark_modified: bool = True):
        items_to_remove = list(self._id_to_item_map.values())
        for item in items_to_remove:
            if item and item.scene():
                self._scene.removeItem(item)

        cleared_count = len(self._id_to_item_map)
        self._id_to_item_map.clear()

        if cleared_count > 0 and mark_modified:
            self.scene_modified.emit(True)

    def update_object_item(
        self, original_modified_data_object: DataObject, mark_modified: bool = True
    ):
        if not isinstance(original_modified_data_object, DATA_OBJECT_TYPES):
            print(
                f"Warning: update_object_item called with invalid type {type(original_modified_data_object)}"
            )
            return

        item_id = id(original_modified_data_object)
        current_graphics_item = self._id_to_item_map.get(item_id)

        if not current_graphics_item or not current_graphics_item.scene():
            print(
                f"Warning: Graphics item for original object id {item_id} not found or not in scene during update."
            )
            # Object might have been fully clipped out previously and removed. Try to re-add.
            new_item = self.add_object(original_modified_data_object, mark_modified)
            if new_item and mark_modified:
                self.scene_modified.emit(True)
            return

        new_display_data_object, needs_item_replacement = self._clip_data_object(
            original_modified_data_object
        )

        try:
            if new_display_data_object is None:  # Fully clipped out now
                self._scene.removeItem(current_graphics_item)
                del self._id_to_item_map[item_id]
                if mark_modified:
                    self.scene_modified.emit(True)

            elif needs_item_replacement or type(
                current_graphics_item.data(SC_CURRENT_REPRESENTATION_KEY)
            ) != type(new_display_data_object):
                self._scene.removeItem(current_graphics_item)  # Remove old item

                new_graphics_item = new_display_data_object.create_graphics_item()
                new_graphics_item.setData(
                    SC_ORIGINAL_OBJECT_KEY, original_modified_data_object
                )
                new_graphics_item.setData(
                    SC_CURRENT_REPRESENTATION_KEY, new_display_data_object
                )
                if isinstance(
                    original_modified_data_object, BezierCurve
                ) and isinstance(new_display_data_object, Polygon):
                    new_graphics_item.setData(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, True)
                else:
                    new_graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, False
                    )

                self._scene.addItem(new_graphics_item)
                self._id_to_item_map[item_id] = (
                    new_graphics_item  # Update map to new item
                )
                if mark_modified:
                    self.scene_modified.emit(True)

            else:  # Update existing item in-place
                current_graphics_item.prepareGeometryChange()
                current_graphics_item.setData(
                    SC_CURRENT_REPRESENTATION_KEY, new_display_data_object
                )
                # Flag for clipped Bezier might change if it's no longer clipped to a polygon or vice-versa
                if isinstance(
                    original_modified_data_object, BezierCurve
                ) and isinstance(new_display_data_object, Polygon):
                    current_graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, True
                    )
                elif not (
                    isinstance(original_modified_data_object, BezierCurve)
                    and isinstance(new_display_data_object, Polygon)
                ):  # ensure flag is false if not this case
                    current_graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, False
                    )

                self._update_graphics_item_geometry(
                    current_graphics_item, new_display_data_object
                )
                self._apply_style_to_item(
                    current_graphics_item, new_display_data_object
                )
                current_graphics_item.update()
                if mark_modified:
                    self.scene_modified.emit(True)

        except Exception as e:
            QMessageBox.critical(
                None,
                "Erro ao Atualizar Item",
                f"Falha ao atualizar item {type(current_graphics_item).__name__} pós-modificação: {e}",
            )

    def _update_graphics_item_geometry(
        self, item: QGraphicsItem, display_data: DataObject
    ):
        # display_data is the current visual representation
        try:
            if isinstance(display_data, Point) and isinstance(
                item, QGraphicsEllipseItem
            ):
                size, offset = (
                    display_data.GRAPHICS_SIZE,
                    display_data.GRAPHICS_SIZE / 2.0,
                )
                new_rect = QRectF(
                    display_data.x - offset, display_data.y - offset, size, size
                )
                if item.rect() != new_rect:
                    item.setRect(new_rect)
            elif isinstance(display_data, Line) and isinstance(item, QGraphicsLineItem):
                new_line = QLineF(
                    display_data.start.to_qpointf(), display_data.end.to_qpointf()
                )
                if item.line() != new_line:
                    item.setLine(new_line)
            elif isinstance(
                display_data, Polygon
            ):  # Could be QGraphicsPolygonItem or QGraphicsPathItem
                if (
                    item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY)
                    or display_data.is_open
                ):  # Represent as PathItem
                    if isinstance(item, QGraphicsPathItem):
                        new_path = QPainterPath()
                        if display_data.points and len(display_data.points) > 0:
                            new_path.moveTo(display_data.points[0].to_qpointf())
                            for p_model in display_data.points[1:]:
                                new_path.lineTo(p_model.to_qpointf())
                        if item.path() != new_path:
                            item.setPath(new_path)
                    else:
                        print(
                            f"Type mismatch: item is {type(item)} but Polygon data suggests QGraphicsPathItem"
                        )
                else:  # Closed, non-Bezier-derived Polygon -> QGraphicsPolygonItem
                    if isinstance(item, QGraphicsPolygonItem):
                        new_polygon_qf = QPolygonF(
                            [p.to_qpointf() for p in display_data.points]
                        )
                        if item.polygon() != new_polygon_qf:
                            item.setPolygon(new_polygon_qf)
                    else:
                        print(
                            f"Type mismatch: item is {type(item)} but Polygon data suggests QGraphicsPolygonItem"
                        )
            elif isinstance(display_data, BezierCurve) and isinstance(
                item, QGraphicsPathItem
            ):
                new_path = QPainterPath()
                if display_data.points:
                    new_path.moveTo(display_data.points[0].to_qpointf())
                    num_segments = display_data.get_num_segments()
                    for i in range(num_segments):
                        p1_idx, p2_idx, p3_idx = 3 * i + 1, 3 * i + 2, 3 * i + 3
                        if p3_idx < len(display_data.points):
                            ctrl1 = display_data.points[p1_idx].to_qpointf()
                            ctrl2 = display_data.points[p2_idx].to_qpointf()
                            endpt = display_data.points[p3_idx].to_qpointf()
                            new_path.cubicTo(ctrl1, ctrl2, endpt)
                if item.path() != new_path:
                    item.setPath(new_path)
        except Exception as e:
            print(
                f"ERROR in _update_graphics_item_geometry for {type(display_data)}/{type(item)}: {e}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, display_data: DataObject):
        if not hasattr(display_data, "color"):
            return
        color = (
            display_data.color
            if isinstance(display_data.color, QColor) and display_data.color.isValid()
            else QColor(Qt.black)
        )
        pen = QPen(Qt.NoPen)
        brush = QBrush(Qt.NoBrush)

        original_data_object = item.data(SC_ORIGINAL_OBJECT_KEY)
        is_clipped_bezier_as_poly = (
            item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY) is True
        )

        if isinstance(display_data, Point):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(display_data, Line):
            pen = QPen(color, display_data.GRAPHICS_WIDTH, Qt.SolidLine)
        elif isinstance(display_data, Polygon):  # This display_data is a Polygon
            pen = QPen(color, Polygon.GRAPHICS_BORDER_WIDTH)  # Use Polygon's constant
            if (
                display_data.is_open or is_clipped_bezier_as_poly
            ):  # Open polygons (polylines) or clipped Beziers are dashed
                pen.setStyle(Qt.DashLine)
            else:  # Closed, non-Bezier-derived polygon
                pen.setStyle(Qt.SolidLine)
                if display_data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color)
                    fill_color.setAlphaF(Polygon.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
        elif isinstance(
            display_data, BezierCurve
        ):  # This display_data is a BezierCurve
            pen = QPen(color, BezierCurve.GRAPHICS_WIDTH, Qt.SolidLine)
            pen.setJoinStyle(Qt.RoundJoin)
            pen.setCapStyle(Qt.RoundCap)

        if hasattr(item, "setPen") and item.pen() != pen:
            item.setPen(pen)
        if hasattr(item, "setBrush") and item.brush() != brush:
            item.setBrush(brush)

    def get_item_for_original_object_id(
        self, original_object_id: int
    ) -> Optional[QGraphicsItem]:
        return self._id_to_item_map.get(original_object_id)

    def get_original_object_for_item(self, item: QGraphicsItem) -> Optional[DataObject]:
        data = item.data(SC_ORIGINAL_OBJECT_KEY)
        if isinstance(data, DATA_OBJECT_TYPES):
            return data
        return None

    def get_current_representation_for_item(
        self, item: QGraphicsItem
    ) -> Optional[DataObject]:
        data = item.data(SC_CURRENT_REPRESENTATION_KEY)  # This is data(0)
        if isinstance(data, DATA_OBJECT_TYPES):
            return data
        return None

    def get_all_original_data_objects(self) -> List[DataObject]:
        objects = []
        for item in self._id_to_item_map.values():
            original_obj = item.data(SC_ORIGINAL_OBJECT_KEY)
            if original_obj:
                objects.append(original_obj)
        return objects

    def get_selected_data_objects(self) -> List[DataObject]:
        selected_original_objects = []
        for item in self._scene.selectedItems():
            # Ensure it's not the viewport rect or other special items
            original_obj = item.data(SC_ORIGINAL_OBJECT_KEY)
            if isinstance(original_obj, DATA_OBJECT_TYPES):
                selected_original_objects.append(original_obj)
        return selected_original_objects
