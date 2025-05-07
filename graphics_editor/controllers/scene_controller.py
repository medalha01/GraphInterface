# graphics_editor/controllers/scene_controller.py
import math
from typing import List, Tuple, Dict, Union, Optional
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsItem, QMessageBox, QGraphicsPathItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPolygonItem
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRectF, QLineF
from PyQt5.QtGui import QColor, QPen, QBrush, QPolygonF, QPainterPath

# Import necessary components
from ..models import Point, Line, Polygon, BezierCurve, __all__ as ModelNames
from ..state_manager import EditorStateManager, LineClippingAlgorithm
from ..utils import clipping as clp

# Alias for DataObject types
DataObject = Union[Point, Line, Polygon, BezierCurve]
DATA_OBJECT_TYPES = tuple(__import__('graphics_editor.models', fromlist=ModelNames).__dict__[name] for name in ModelNames)


class SceneController(QObject):
    """
    Manages the QGraphicsScene content, mapping DataObjects to QGraphicsItems,
    handling clipping, adding, removing, and updating items.
    """
    # Signal emitted when the scene content is modified (add, remove, clear, update)
    # The boolean indicates if the modification should potentially trigger an 'unsaved changes' state.
    scene_modified = pyqtSignal(bool)

    def __init__(self, scene: QGraphicsScene, state_manager: EditorStateManager, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager
        self._data_object_to_item_map: Dict[DataObject, QGraphicsItem] = {}

        # Store clipping configuration locally, updated via signals
        self._clip_rect_tuple: clp.ClipRect = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()

        # Configuration (can be passed in __init__ or fetched from config later)
        # TODO: Fetch from a config/settings manager or pass via constructor
        self.bezier_clipping_samples = 20

        # Connect to state changes relevant to clipping
        self._state_manager.clip_rect_changed.connect(self._update_clipper_state)
        self._state_manager.line_clipper_changed.connect(self._update_clipper_state)

    # --- Internal State Updaters ---

    def _update_clipper_state(self):
        """Updates internal clipping parameters when state manager signals change."""
        self._clip_rect_tuple = self._get_clip_rect_tuple()
        self._clipper_func = self._get_clipper_function()
        # Optional: Re-clip all items if viewport changes dynamically? Complex.

    def _get_clip_rect_tuple(self) -> clp.ClipRect:
        """Gets the clipping rectangle tuple from the state manager."""
        rect = self._state_manager.clip_rect() # Already normalized
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _get_clipper_function(self):
        """Gets the appropriate line clipping function based on state."""
        algo = self._state_manager.selected_line_clipper()
        return clp.cohen_sutherland if algo == LineClippingAlgorithm.COHEN_SUTHERLAND else clp.liang_barsky

    # --- Clipping Logic ---

    def _clip_data_object(self, data_object: DataObject) -> Tuple[Optional[DataObject], bool]:
        """
        Clips a DataObject against the current viewport.
        Returns (clipped_object, needs_replacement).
        """
        clipped_result: Optional[DataObject] = None
        needs_replacement = False
        clip_rect = self._clip_rect_tuple
        line_clipper = self._clipper_func

        try:
            if isinstance(data_object, Point):
                clipped_coords = clp.clip_point(data_object.get_coords(), clip_rect)
                if clipped_coords:
                    clipped_result = Point(clipped_coords[0], clipped_coords[1], data_object.color)
            elif isinstance(data_object, Line):
                clipped_segment = line_clipper(data_object.start.get_coords(), data_object.end.get_coords(), clip_rect)
                if clipped_segment:
                    p1, p2 = clipped_segment
                    start_pt = Point(p1[0], p1[1], data_object.color)
                    end_pt = Point(p2[0], p2[1], data_object.color)
                    clipped_result = Line(start_pt, end_pt, data_object.color)
            elif isinstance(data_object, Polygon):
                clipped_vertices_coords = clp.sutherland_hodgman(data_object.get_coords(), clip_rect)
                min_points = 2 if data_object.is_open else 3
                if len(clipped_vertices_coords) >= min_points:
                    clipped_points = [Point(x, y, data_object.color) for x, y in clipped_vertices_coords]
                    clipped_result = Polygon(
                        clipped_points, is_open=data_object.is_open,
                        color=data_object.color, is_filled=data_object.is_filled
                    )
            elif isinstance(data_object, BezierCurve):
                sampled_points = data_object.sample_curve(self.bezier_clipping_samples)
                if len(sampled_points) < 2: return None, False

                clipped_polyline_points: List[Point] = []
                for i in range(len(sampled_points) - 1):
                     p1 = (sampled_points[i].x(), sampled_points[i].y())
                     p2 = (sampled_points[i+1].x(), sampled_points[i+1].y())
                     clipped_segment = line_clipper(p1, p2, clip_rect)
                     if clipped_segment:
                          start_pt = Point(clipped_segment[0][0], clipped_segment[0][1], data_object.color)
                          end_pt = Point(clipped_segment[1][0], clipped_segment[1][1], data_object.color)
                          # Add points, avoiding duplicates for connected segments inside
                          if not clipped_polyline_points or not (
                              math.isclose(clipped_polyline_points[-1].x, start_pt.x) and
                              math.isclose(clipped_polyline_points[-1].y, start_pt.y)):
                               clipped_polyline_points.append(start_pt)
                          if not (math.isclose(start_pt.x, end_pt.x) and math.isclose(start_pt.y, end_pt.y)):
                              clipped_polyline_points.append(end_pt)

                if len(clipped_polyline_points) >= 2:
                     # Result is an open Polygon
                     clipped_result = Polygon(clipped_polyline_points, is_open=True, color=data_object.color)
                     needs_replacement = True # Type changed

            return clipped_result, needs_replacement

        except Exception as e:
            print(f"Error during clipping of {type(data_object).__name__}: {e}")
            return None, False

    # --- Scene Modification Methods ---

    def add_object(self, data_object: DataObject, mark_modified: bool = True):
        """Clips a DataObject and adds its graphical representation to the scene and map."""
        if not isinstance(data_object, DATA_OBJECT_TYPES):
            print(f"Warning: Attempted to add unsupported object type {type(data_object)}")
            return

        clipped_data_object, _ = self._clip_data_object(data_object) # Ignore replacement flag for new objects

        if clipped_data_object:
            try:
                graphics_item = clipped_data_object.create_graphics_item()
                graphics_item.setData(0, clipped_data_object) # Associate clipped data
                self._scene.addItem(graphics_item)
                self._data_object_to_item_map[clipped_data_object] = graphics_item
                if mark_modified:
                    self.scene_modified.emit(True) # Signal modification
            except Exception as e:
                 # Use a more informative error message if possible
                 QMessageBox.critical(None, "Erro ao Adicionar Item",
                     f"Não foi possível criar item gráfico para {type(clipped_data_object).__name__}: {e}")


    def remove_items(self, items_to_remove: List[QGraphicsItem], mark_modified: bool = True) -> int:
        """Removes specified QGraphicsItems from the scene and the lookup map."""
        items_removed_count = 0
        for item in items_to_remove:
            if item and item.scene(): # Check if item exists and is in the scene
                data_obj = self.get_object_for_item(item)
                # Remove from map first
                if data_obj is not None and data_obj in self._data_object_to_item_map:
                    del self._data_object_to_item_map[data_obj]
                # Remove from scene
                self._scene.removeItem(item)
                items_removed_count += 1

        if items_removed_count > 0 and mark_modified:
            self.scene_modified.emit(True) # Signal modification

        return items_removed_count

    def clear_scene(self, mark_modified: bool = True):
        """Removes all managed items from the scene and clears the map."""
        # Get items from map values before clearing
        items_to_remove = list(self._data_object_to_item_map.values())
        for item in items_to_remove:
            if item and item.scene():
                self._scene.removeItem(item)

        cleared_count = len(self._data_object_to_item_map)
        self._data_object_to_item_map.clear()

        if cleared_count > 0 and mark_modified:
             self.scene_modified.emit(True) # Signal modification

    def update_object_item(self, modified_data_object: DataObject, mark_modified: bool = True):
        """
        Handles updates to an object after modification (e.g., transformation).
        Re-clips the object and updates or replaces the corresponding QGraphicsItem.
        """
        if not isinstance(modified_data_object, DATA_OBJECT_TYPES):
            print(f"Warning: update_object_item called with invalid type {type(modified_data_object)}")
            return

        # Find the graphics item associated with the *original* (pre-modification) object identity
        # This assumes the `modified_data_object` reference is still the same instance that was transformed.
        graphics_item = self.get_item_for_object(modified_data_object)

        if not graphics_item or not graphics_item.scene():
            # Item might have been deleted concurrently
            # Or the object reference changed unexpectedly (less likely if modified in-place)
            print(f"Warning: Graphics item for {modified_data_object} not found or not in scene during update.")
            # If the data object *instance* changed, the map lookup will fail.
            # Need a way to handle this if objects are recreated instead of modified in-place.
            return

        # Re-clip the *already modified* data object
        clipped_data_object, needs_replacement = self._clip_data_object(modified_data_object)

        try:
            if clipped_data_object is None:
                # Object is now completely outside the viewport
                self.remove_items([graphics_item], mark_modified=mark_modified) # Remove from scene and map
            elif needs_replacement:
                # Type changed during clipping (e.g., Bezier -> Polygon)
                # Remove old item/map entry
                if modified_data_object in self._data_object_to_item_map:
                    del self._data_object_to_item_map[modified_data_object]
                self._scene.removeItem(graphics_item)
                # Add the new clipped object (creates item, adds to scene/map)
                self.add_object(clipped_data_object, mark_modified=mark_modified)
            else:
                # Object clipped (or not) but type remains the same - update in place
                graphics_item.prepareGeometryChange()

                # Check if clipping returned a *new* object instance (even if same type)
                if clipped_data_object is not modified_data_object:
                    # Update map: remove old key, add new key pointing to the same item
                    if modified_data_object in self._data_object_to_item_map:
                        del self._data_object_to_item_map[modified_data_object]
                    self._data_object_to_item_map[clipped_data_object] = graphics_item
                    # Update the item's associated data pointer
                    graphics_item.setData(0, clipped_data_object)

                # Update item's visual representation based on the (potentially new) clipped data
                self._update_graphics_item_geometry(graphics_item, clipped_data_object)
                self._apply_style_to_item(graphics_item, clipped_data_object)
                graphics_item.update() # Request redraw
                if mark_modified:
                    self.scene_modified.emit(True) # Signal modification

        except Exception as e:
             QMessageBox.critical(None, "Erro ao Atualizar Item",
                 f"Falha ao atualizar item {type(graphics_item).__name__} pós-modificação: {e}")

    # --- Internal Graphics Item Updates ---

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        """Updates the geometry of a QGraphicsItem based on its DataObject."""
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
                 # Handle Polygon data associated with a PathItem (e.g., clipped Bezier)
                 new_path = QPainterPath()
                 if data.points: new_path.addPolygon(QPolygonF([p.to_qpointf() for p in data.points]))
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
        """Applies the style (pen, brush) from the DataObject to the QGraphicsItem."""
        if not hasattr(data, "color"): return
        color = data.color if isinstance(data.color, QColor) and data.color.isValid() else QColor(Qt.black)
        pen = QPen(Qt.NoPen) # Default
        brush = QBrush(Qt.NoBrush) # Default

        # Determine style based on data type
        if isinstance(data, Point):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(data, Line):
            pen = QPen(color, data.GRAPHICS_WIDTH, Qt.SolidLine)
        elif isinstance(data, Polygon):
            pen = QPen(color, data.GRAPHICS_BORDER_WIDTH)
            if data.is_open: pen.setStyle(Qt.DashLine)
            else: # Closed
                pen.setStyle(Qt.SolidLine)
                if data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color); fill_color.setAlphaF(data.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
        elif isinstance(data, BezierCurve):
            pen = QPen(color, data.GRAPHICS_WIDTH, Qt.SolidLine)

        # Apply if supported and different from current
        if hasattr(item, "setPen") and item.pen() != pen: item.setPen(pen)
        if hasattr(item, "setBrush") and item.brush() != brush: item.setBrush(brush)


    # --- Lookup and Access Methods ---

    def get_item_for_object(self, data_object: DataObject) -> Optional[QGraphicsItem]:
        """Retrieves the QGraphicsItem associated with a DataObject."""
        return self._data_object_to_item_map.get(data_object)

    def get_object_for_item(self, item: QGraphicsItem) -> Optional[DataObject]:
        """Retrieves the DataObject associated with a QGraphicsItem."""
        # Check if the item is in our map's values first for efficiency?
        # Or rely solely on item.data(0)
        data = item.data(0)
        if isinstance(data, DATA_OBJECT_TYPES):
            # Verify it's actually in our map (consistency check)
            # if data in self._data_object_to_item_map and self._data_object_to_item_map[data] is item:
            #     return data
            # else:
            #     print(f"Warning: Item {item} has data {data} but mismatch/missing in map.")
            #     return None # Or return data anyway? Let's return data for now.
             return data
        return None

    def get_all_data_objects(self) -> List[DataObject]:
        """Returns a list of all DataObjects currently managed."""
        return list(self._data_object_to_item_map.keys())

    def get_selected_data_objects(self) -> List[DataObject]:
        """Returns a list of DataObjects corresponding to selected QGraphicsItems."""
        selected_objects = []
        for item in self._scene.selectedItems():
            data_obj = self.get_object_for_item(item)
            if data_obj:
                selected_objects.append(data_obj)
        return selected_objects
