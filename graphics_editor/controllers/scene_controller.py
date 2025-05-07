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
SC_CURRENT_REPRESENTATION_KEY = (
    Qt.UserRole + 3
)  # Stores the current visual DataObject (e.g., a clipped version or Polygon for Bezier)
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
        self.bezier_clipping_samples_per_segment = 20  # Default, can be overridden

        self._state_manager.clip_rect_changed.connect(
            self._on_clipping_parameters_changed
        )
        self._state_manager.line_clipper_changed.connect(
            self._on_clipping_parameters_changed
        )

    def _on_clipping_parameters_changed(
        self, *args
    ):  # Accept potential QRectF or Algorithm from signal
        """Updates internal clipping state and refreshes all objects."""
        self._clip_rect_tuple = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()
        self.refresh_all_object_clipping()

    def refresh_all_object_clipping(self):
        """Re-clips and updates all managed QGraphicsItems in the scene."""
        original_objects_to_refresh = []
        # Iterate over a copy of keys, as _id_to_item_map might change
        # if items are removed/replaced during update_object_item.
        for item_id in list(self._id_to_item_map.keys()):
            item = self._id_to_item_map.get(item_id)
            if item:
                original_obj = item.data(SC_ORIGINAL_OBJECT_KEY)
                if original_obj:
                    original_objects_to_refresh.append(original_obj)

        for original_data_object in original_objects_to_refresh:
            # mark_modified=False: Re-clipping due to viewport/clipper change
            # should not inherently mark the document as having unsaved changes.
            # However, if an object is now fully clipped (removed) or becomes visible (added),
            # update_object_item will emit scene_modified internally if appropriate.
            self.update_object_item(original_data_object, mark_modified=False)

        self._scene.update()

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
        # A more robust check would sample the curve, but control points give a good heuristic.
        # For perfect check, one might need to verify bounding box of curve segments.
        return True

    def _clip_data_object(
        self, original_data_object: DataObject
    ) -> Tuple[Optional[DataObject], bool]:
        """
        Clips the DataObject.
        Returns: (clipped_display_object_or_None, bezier_type_changed_on_clip)
        'bezier_type_changed_on_clip' is True if a Bezier's visual representation type changes (e.g., Bezier -> Polygon or vice-versa).
        """
        clipped_display_object: Optional[DataObject] = None
        bezier_type_changed_on_clip = (
            False  # Specifically for Bezier <-> Polygon display type changes
        )
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
                # Check if all original vertices are inside (quick accept for non-open polygons)
                is_fully_inside = True
                if not original_data_object.is_open:  # Only for closed polygons
                    for p_coord in original_data_object.get_coords():
                        if clp.clip_point(p_coord, clip_rect_tuple) is None:
                            is_fully_inside = False
                            break
                else:  # Open polygons (polylines) always go through SH
                    is_fully_inside = False

                if (
                    is_fully_inside and not original_data_object.is_open
                ):  # Quick accept for closed, fully inside
                    clipped_display_object = original_data_object
                else:
                    clipped_vertices_coords = clp.sutherland_hodgman(
                        original_data_object.get_coords(), clip_rect_tuple
                    )
                    # For open polygons (polylines), min 2 points. For closed, min 3.
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
            elif isinstance(original_data_object, BezierCurve):
                # Heuristic: if all control points are inside, assume Bezier is fully inside.
                # For more accuracy, one could check the convex hull of the Bezier or sample it.
                if self._is_bezier_fully_inside(original_data_object, clip_rect_tuple):
                    clipped_display_object = original_data_object  # No change
                    # Check if the *previous* display object was a Polygon (clipped Bezier)
                    # This logic is tricky here, better handled in update_object_item
                else:  # Bezier needs clipping, represent as polyline (open Polygon)
                    sampled_qpoints = original_data_object.sample_curve(
                        self.bezier_clipping_samples_per_segment
                    )
                    if len(sampled_qpoints) < 2:
                        clipped_display_object = None
                    else:
                        raw_polyline_coords: List[Tuple[float, float]] = [
                            (qp.x(), qp.y()) for qp in sampled_qpoints
                        ]
                        # Sutherland-Hodgman for the polyline approximation
                        clipped_sh_coords = clp.sutherland_hodgman(
                            raw_polyline_coords, clip_rect_tuple
                        )

                        if len(clipped_sh_coords) >= 2:
                            clipped_points_models = [
                                Point(x, y, original_data_object.color)
                                for x, y in clipped_sh_coords
                            ]
                            clipped_display_object = (
                                Polygon(  # Displayed as an open polygon
                                    clipped_points_models,
                                    is_open=True,
                                    color=original_data_object.color,
                                    is_filled=False,
                                )
                            )
                            bezier_type_changed_on_clip = True

            # If original was Bezier and now it's displayed as Bezier again (was previously Polygon)
            if isinstance(original_data_object, BezierCurve) and isinstance(
                clipped_display_object, BezierCurve
            ):
                # This implies it might have been a Polygon before, now it's Bezier again.
                # This situation also implies a type change for display.
                # We need to know the *previous* display type. This is hard here.
                # Let update_object_item handle this determination.
                # For now, bezier_type_changed_on_clip is true if it *became* a Polygon.
                pass

            return clipped_display_object, bezier_type_changed_on_clip

        except Exception as e:
            print(
                f"Error during clipping of {type(original_data_object).__name__}: {e}"
            )
            return None, False

    def _get_required_qgraphicsitem_type(
        self, display_data_object: DataObject
    ) -> Optional[type]:
        """Determines the QGraphicsItem class needed to represent the display_data_object."""
        if isinstance(display_data_object, Point):
            return QGraphicsEllipseItem
        elif isinstance(display_data_object, Line):
            return QGraphicsLineItem
        elif isinstance(display_data_object, Polygon):
            # Open Polygons (polylines) and Polygons that represent clipped Beziers
            # are typically drawn as QGraphicsPathItem for dashed lines or complex paths.
            # Closed, filled/unfilled polygons can be QGraphicsPolygonItem.
            if display_data_object.is_open:
                return QGraphicsPathItem
            else:  # Closed polygon
                return QGraphicsPolygonItem
        elif isinstance(display_data_object, BezierCurve):
            return QGraphicsPathItem
        return None

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
            return self._id_to_item_map[item_id]

        display_data_object, _ = (
            self._clip_data_object(  # bezier_type_changed flag not critical for new add
                original_data_object
            )
        )

        if display_data_object:
            try:
                graphics_item = display_data_object.create_graphics_item()
                graphics_item.setData(SC_ORIGINAL_OBJECT_KEY, original_data_object)
                graphics_item.setData(
                    SC_CURRENT_REPRESENTATION_KEY, display_data_object
                )
                if isinstance(original_data_object, BezierCurve) and isinstance(
                    display_data_object, Polygon  # i.e. it's a clipped Bezier
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

        # If object was fully clipped out or failed to create graphic
        if mark_modified and display_data_object is None:
            self.scene_modified.emit(True)
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

        if (
            cleared_count > 0 and mark_modified
        ):  # Only emit if something was actually cleared
            self.scene_modified.emit(True)
        elif mark_modified and cleared_count == 0:  # Explicitly clearing an empty scene
            self.scene_modified.emit(False)  # No effective change that requires saving

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

        new_display_data_object, bezier_type_changed_on_clip = self._clip_data_object(
            original_modified_data_object
        )

        if not current_graphics_item or not current_graphics_item.scene():
            # Object might have been fully clipped out previously and removed, or never added.
            # Try to re-add if it's now visible.
            if new_display_data_object:  # Only add if it's visible now
                new_item = self.add_object(original_modified_data_object, mark_modified)
                # add_object handles scene_modified signal
            elif (
                mark_modified
            ):  # Was not in scene, and still not visible (fully clipped)
                # If an object was modified but remains fully clipped, it's still a modification to data
                self.scene_modified.emit(True)
            return

        try:
            if new_display_data_object is None:  # Fully clipped out now
                if current_graphics_item and current_graphics_item.scene():
                    self._scene.removeItem(current_graphics_item)
                if item_id in self._id_to_item_map:
                    del self._id_to_item_map[item_id]
                if mark_modified:
                    self.scene_modified.emit(True)
            else:
                required_new_item_type = self._get_required_qgraphicsitem_type(
                    new_display_data_object
                )

                needs_replacement = False
                if not isinstance(current_graphics_item, required_new_item_type):
                    needs_replacement = True

                # If the original was Bezier and its display form changed (to Polygon or back to Bezier from Polygon)
                # This check is subtle: bezier_type_changed_on_clip is true if IT BECAME a Polygon.
                # If it was a Polygon (representing Bezier) and now it's Bezier again, that's also a type change.
                # The isinstance check above should largely cover this if _get_required_qgraphicsitem_type is correct.
                # Let's consider if the *previous display type* differs from *new display type*
                previous_display_object = current_graphics_item.data(
                    SC_CURRENT_REPRESENTATION_KEY
                )
                if type(previous_display_object) != type(new_display_data_object):
                    needs_replacement = True
                if (
                    isinstance(original_modified_data_object, BezierCurve)
                    and bezier_type_changed_on_clip
                ):
                    needs_replacement = True  # Bezier became Polygon
                if (
                    isinstance(previous_display_object, Polygon)
                    and previous_display_object.data(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY
                    )
                    and isinstance(new_display_data_object, BezierCurve)
                ):
                    needs_replacement = (
                        True  # Was Polygon (from Bezier), now Bezier again
                    )

                if needs_replacement:
                    if current_graphics_item.scene():
                        self._scene.removeItem(current_graphics_item)

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
                        new_graphics_item.setData(
                            SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, True
                        )
                    else:
                        new_graphics_item.setData(
                            SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, False
                        )

                    self._scene.addItem(new_graphics_item)
                    self._id_to_item_map[item_id] = new_graphics_item
                    if mark_modified:
                        self.scene_modified.emit(True)
                else:  # Update existing item in-place
                    current_graphics_item.prepareGeometryChange()
                    current_graphics_item.setData(
                        SC_CURRENT_REPRESENTATION_KEY, new_display_data_object
                    )
                    if isinstance(
                        original_modified_data_object, BezierCurve
                    ) and isinstance(new_display_data_object, Polygon):
                        current_graphics_item.setData(
                            SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, True
                        )
                    else:
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
            elif isinstance(display_data, Polygon):
                # If it's an open polygon (polyline) or a polygon representing a clipped Bezier,
                # it should be a QGraphicsPathItem.
                if display_data.is_open or item.data(
                    SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY
                ):
                    if isinstance(item, QGraphicsPathItem):
                        new_path = QPainterPath()
                        if display_data.points and len(display_data.points) > 0:
                            new_path.moveTo(display_data.points[0].to_qpointf())
                            for p_model in display_data.points[1:]:
                                new_path.lineTo(p_model.to_qpointf())
                        if item.path() != new_path:
                            item.setPath(new_path)
                    # else: type mismatch, should have been replaced by update_object_item
                else:  # Closed, non-Bezier-derived Polygon -> QGraphicsPolygonItem
                    if isinstance(item, QGraphicsPolygonItem):
                        new_polygon_qf = QPolygonF(
                            [p.to_qpointf() for p in display_data.points]
                        )
                        if item.polygon() != new_polygon_qf:
                            item.setPolygon(new_polygon_qf)
                    # else: type mismatch
            elif isinstance(display_data, BezierCurve) and isinstance(
                item, QGraphicsPathItem
            ):  # This is a true Bezier display, not a clipped one as Polygon
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
        if not hasattr(display_data, "color"):  # Should not happen for our DataObjects
            return
        color = (
            display_data.color
            if isinstance(display_data.color, QColor) and display_data.color.isValid()
            else QColor(Qt.black)
        )
        pen = QPen(Qt.NoPen)
        brush = QBrush(Qt.NoBrush)

        is_polygon_from_clipped_bezier = (
            item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY) is True
        )

        if isinstance(display_data, Point):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(display_data, Line):
            pen = QPen(color, display_data.GRAPHICS_WIDTH, Qt.SolidLine)
        elif isinstance(display_data, Polygon):
            pen = QPen(color, Polygon.GRAPHICS_BORDER_WIDTH)
            if display_data.is_open or is_polygon_from_clipped_bezier:
                pen.setStyle(Qt.DashLine)
            else:  # Closed, non-Bezier-derived polygon
                pen.setStyle(Qt.SolidLine)
                if display_data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color)
                    fill_color.setAlphaF(Polygon.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
        elif isinstance(display_data, BezierCurve):
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
        # Ensure it's not a special item like viewport_rect by checking for SC_ORIGINAL_OBJECT_KEY
        data = item.data(SC_ORIGINAL_OBJECT_KEY)
        if isinstance(data, DATA_OBJECT_TYPES):
            return data
        return None

    def get_current_representation_for_item(
        self, item: QGraphicsItem
    ) -> Optional[DataObject]:
        data = item.data(SC_CURRENT_REPRESENTATION_KEY)
        if isinstance(data, DATA_OBJECT_TYPES):
            return data
        return None

    def get_all_original_data_objects(self) -> List[DataObject]:
        objects = []
        for item in self._id_to_item_map.values():
            original_obj = item.data(SC_ORIGINAL_OBJECT_KEY)
            if original_obj and isinstance(
                original_obj, DATA_OBJECT_TYPES
            ):  # Ensure it's a valid data object
                objects.append(original_obj)
        return objects

    def get_selected_data_objects(self) -> List[DataObject]:
        selected_original_objects = []
        for item in self._scene.selectedItems():
            original_obj = item.data(SC_ORIGINAL_OBJECT_KEY)
            if isinstance(original_obj, DATA_OBJECT_TYPES):
                selected_original_objects.append(original_obj)
        return selected_original_objects
