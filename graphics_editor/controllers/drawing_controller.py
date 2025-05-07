# graphics_editor/controllers/drawing_controller.py
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject, pyqtSignal, QPointF, Qt, QLineF
from PyQt5.QtGui import QPainterPath, QPen, QColor, QPolygonF
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QMessageBox,
)
from typing import List, Optional, Tuple, Union

from ..state_manager import EditorStateManager, DrawingMode
from ..models.point import Point
from ..models.line import Line
from ..models.polygon import Polygon
from ..models.bezier_curve import BezierCurve

DataObject = Union[Point, Line, Polygon, BezierCurve]
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve)


class DrawingController(QObject):
    object_ready_to_add = pyqtSignal(object)
    status_message_requested = pyqtSignal(str, int)
    polygon_properties_query_requested = (
        pyqtSignal()
    )  # For GraphicsEditor to show dialog

    def __init__(
        self,
        scene: QGraphicsScene,
        state_manager: EditorStateManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager

        self._current_line_start: Optional[Point] = None
        self._current_polygon_points: List[Point] = []
        self._current_polygon_is_open: bool = False
        self._current_polygon_is_filled: bool = False
        self._current_bezier_points: List[Point] = []

        self._pending_first_polygon_point: Optional[Point] = (
            None  # For polygon properties query
        )

        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path: Optional[QGraphicsPathItem] = None
        self._temp_bezier_path: Optional[QGraphicsPathItem] = None
        self._temp_item_pen = QPen(Qt.gray, 1, Qt.DashLine)
        self._temp_bezier_control_pen = QPen(Qt.darkCyan, 1, Qt.DotLine)

        self._state_manager.drawing_mode_changed.connect(self._on_mode_changed)

    def _on_mode_changed(self, mode: DrawingMode):
        # Always cancel current drawing if mode changes, to ensure clean state
        self.cancel_current_drawing()

    def set_pending_polygon_properties(
        self, is_open: bool, is_filled: bool, cancelled: bool = False
    ):
        """Called by GraphicsEditor after user provides polygon type/fill info."""
        if cancelled or self._pending_first_polygon_point is None:
            self.status_message_requested.emit("Desenho de polígono cancelado.", 2000)
            # Use _finish_current_drawing to reset pending point and other states
            self._finish_current_drawing(commit=False)
            return

        self._current_polygon_is_open = is_open
        self._current_polygon_is_filled = is_filled

        first_point_data = self._pending_first_polygon_point
        self._pending_first_polygon_point = None  # Clear after use

        self._current_polygon_points.append(first_point_data)
        self._update_polygon_preview(first_point_data.to_qpointf())

        pt_type = (
            "vértices da polilinha"
            if self._current_polygon_is_open
            else "vértices do polígono"
        )
        end_action = "Botão direito para finalizar."
        self.status_message_requested.emit(
            f"Polígono: Clique nos {pt_type}. {end_action}", 0
        )

    def handle_scene_left_click(self, scene_pos: QPointF):
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()
        current_point_data = Point(scene_pos.x(), scene_pos.y(), color=color)

        if mode == DrawingMode.POINT:
            self.object_ready_to_add.emit(current_point_data)

        elif mode == DrawingMode.LINE:
            if self._current_line_start is None:
                self._current_line_start = current_point_data
                self._update_line_preview(scene_pos)
                self.status_message_requested.emit("Linha: Clique no ponto final.", 0)
            else:
                if (
                    current_point_data.get_coords()
                    == self._current_line_start.get_coords()
                ):
                    self.status_message_requested.emit(
                        "Ponto final igual ao inicial. Clique em outro lugar.", 2000
                    )
                    return
                line_data = Line(
                    self._current_line_start, current_point_data, color=color
                )
                self.object_ready_to_add.emit(line_data)
                self._finish_current_drawing(commit=True)

        elif mode == DrawingMode.POLYGON:
            if (
                not self._current_polygon_points  # No points *in current drawing* yet
                and self._pending_first_polygon_point
                is None  # And no point is pending properties
            ):
                self._pending_first_polygon_point = current_point_data
                self.polygon_properties_query_requested.emit()
                # Do not proceed; wait for properties from editor
                return

            # If properties were just set, _pending_first_polygon_point is now None,
            # and _current_polygon_points contains the first point. This click is for the second point.

            if (  # Avoid duplicate consecutive points
                self._current_polygon_points
                and current_point_data.get_coords()
                == self._current_polygon_points[-1].get_coords()
            ):
                self.status_message_requested.emit("Ponto duplicado ignorado.", 1500)
                return

            if self._pending_first_polygon_point is not None:
                # This case implies user clicked again before properties dialog finished.
                # It's unlikely if UI is modal, but good to have a guard.
                self.status_message_requested.emit(
                    "Aguardando definição de tipo de polígono.", 2000
                )
                return

            self._current_polygon_points.append(current_point_data)
            self._update_polygon_preview(scene_pos)
            num_pts_current = len(self._current_polygon_points)
            pt_type = (
                "vértices da polilinha"
                if self._current_polygon_is_open
                else "vértices do polígono"
            )
            self.status_message_requested.emit(
                f"Polígono: {num_pts_current} {pt_type} adicionado(s). Botão direito para finalizar.",
                0,
            )

        elif mode == DrawingMode.BEZIER:
            self._current_bezier_points.append(current_point_data)
            self._update_bezier_preview(scene_pos)
            self._update_bezier_status_message()

    def _update_bezier_status_message(self):
        num_pts = len(self._current_bezier_points)
        status = f"Bézier: Ponto {num_pts} adicionado."
        min_finish_pts = 4
        can_finish = False

        if num_pts < min_finish_pts:
            pts_needed = min_finish_pts - num_pts
            status += f" Adicione mais {pts_needed} ponto(s) para o 1º segmento."
        else:
            if (num_pts - min_finish_pts) % 3 == 0:
                can_finish = True
                num_segments = (num_pts - 1) // 3
                status += f" Segmento {num_segments} completo."
                pts_needed_next = 3
                status += f" Adicione mais {pts_needed_next} para o próximo segmento, ou clique direito para finalizar."
            else:
                pts_in_current_segment = (num_pts - 1) % 3
                pts_needed_current = 3 - pts_in_current_segment
                current_segment_index = (num_pts - 1) // 3 + 1
                status += f" Adicione mais {pts_needed_current} ponto(s) para completar o segmento {current_segment_index}."

        if not can_finish and num_pts >= 1:
            current_segment_group = (num_pts - 1) // 3
            next_finish_count = 4 + 3 * current_segment_group
            if num_pts < next_finish_count:
                pts_to_next_finish = next_finish_count - num_pts
                if pts_to_next_finish > 0 and (num_pts - min_finish_pts) % 3 != 0:
                    status += (
                        f" (Precisa de mais {pts_to_next_finish} para poder finalizar)."
                    )

        self.status_message_requested.emit(status, 0)

    def handle_scene_right_click(self, scene_pos: QPointF):
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.POLYGON or mode == DrawingMode.BEZIER:
            self._finish_current_drawing(commit=True)

    def handle_scene_mouse_move(self, scene_pos: QPointF):
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif mode == DrawingMode.POLYGON and self._current_polygon_points:
            self._update_polygon_preview(scene_pos)
        elif mode == DrawingMode.BEZIER and self._current_bezier_points:
            self._update_bezier_preview(scene_pos)

    def cancel_current_drawing(self):
        self._finish_current_drawing(commit=False)

    def _update_line_preview(self, current_pos: QPointF):
        if not self._current_line_start:
            return
        start_qpos = self._current_line_start.to_qpointf()
        line = QLineF(start_qpos, current_pos)
        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(line)
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(line)

    def _update_polygon_preview(self, current_pos: QPointF):
        if not self._current_polygon_points:
            return
        path = QPainterPath()
        path.moveTo(self._current_polygon_points[0].to_qpointf())
        for point_data in self._current_polygon_points[1:]:
            path.lineTo(point_data.to_qpointf())
        path.lineTo(current_pos)
        if self._temp_polygon_path is None:
            self._temp_polygon_path = QGraphicsPathItem(path)
            self._temp_polygon_path.setPen(self._temp_item_pen)
            self._temp_polygon_path.setZValue(1000)
            self._scene.addItem(self._temp_polygon_path)
        else:
            self._temp_polygon_path.setPath(path)

    def _update_bezier_preview(self, current_pos: QPointF):
        if not self._current_bezier_points:
            return
        path = QPainterPath()
        path.moveTo(self._current_bezier_points[0].to_qpointf())
        for point_data in self._current_bezier_points[1:]:
            path.lineTo(point_data.to_qpointf())
        path.lineTo(current_pos)
        if self._temp_bezier_path is None:
            self._temp_bezier_path = QGraphicsPathItem(path)
            self._temp_bezier_path.setPen(self._temp_bezier_control_pen)
            self._temp_bezier_path.setZValue(999)
            self._scene.addItem(self._temp_bezier_path)
        else:
            self._temp_bezier_path.setPath(path)

    def _finish_current_drawing(self, commit: bool = True) -> None:
        drawing_finished_or_cancelled = False  # Will be set true if state is reset
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()

        # Always clear pending point on finish/cancel, regardless of mode
        self._pending_first_polygon_point = None

        if mode == DrawingMode.LINE:
            if self._current_line_start:  # If a line drawing was in progress
                # If commit is false (cancel), or if commit is true (already handled by left click)
                # just reset state.
                self._current_line_start = None
                drawing_finished_or_cancelled = True

        elif mode == DrawingMode.POLYGON:
            if self._current_polygon_points:  # If a polygon drawing was in progress
                min_points_needed = 2 if self._current_polygon_is_open else 3
                can_commit_polygon = (
                    len(self._current_polygon_points) >= min_points_needed
                )

                if commit and can_commit_polygon:
                    polygon_data = Polygon(
                        self._current_polygon_points.copy(),
                        is_open=self._current_polygon_is_open,
                        color=color,
                        is_filled=self._current_polygon_is_filled,
                    )
                    self.object_ready_to_add.emit(polygon_data)
                elif commit and not can_commit_polygon:
                    QMessageBox.warning(
                        None,
                        "Pontos Insuficientes",
                        f"Polígono {'aberto' if self._current_polygon_is_open else 'fechado'} "
                        f"requer {min_points_needed} pontos (você tem {len(self._current_polygon_points)}). "
                        "Desenho não finalizado.",
                    )
                    # Do not reset state yet, let user add more points or cancel explicitly
                    # The temp items will remain for them to see.
                    # However, if the intention is to cancel on invalid commit, then set drawing_finished_or_cancelled = True
                    # For now, let's treat invalid commit as "still drawing"
                    return  # Early exit, do not clear state below

                # Reset state if committed successfully OR if explicitly cancelled (commit=False)
                if (commit and can_commit_polygon) or not commit:
                    self._current_polygon_points = []
                    self._current_polygon_is_open = False
                    self._current_polygon_is_filled = False
                    drawing_finished_or_cancelled = True
            elif (
                not commit and self._pending_first_polygon_point is None
            ):  # Cancelled before even 1st point after properties
                drawing_finished_or_cancelled = True

        elif mode == DrawingMode.BEZIER:
            if self._current_bezier_points:  # If a Bezier drawing was in progress
                num_pts = len(self._current_bezier_points)
                is_valid_count = num_pts >= 4 and (num_pts - 4) % 3 == 0
                can_commit_bezier = is_valid_count

                if commit and can_commit_bezier:
                    bezier_data = BezierCurve(
                        self._current_bezier_points.copy(), color=color
                    )
                    self.object_ready_to_add.emit(bezier_data)
                elif commit and not can_commit_bezier:
                    pts_needed = -1
                    if num_pts < 4:
                        pts_needed = 4 - num_pts
                    else:  # num_pts > 4 but not a multiple of 3 + 1
                        pts_needed = 3 - ((num_pts - 1) % 3)
                        if (
                            pts_needed == 3
                        ):  # This means it's one short of a full segment
                            pts_needed = 3 - ((num_pts - 4) % 3)

                    msg = f"Não é possível finalizar a curva de Bézier. "
                    if (
                        pts_needed > 0 and pts_needed < 3
                    ):  # Only show if 1 or 2 points are needed for next segment
                        msg += f"Precisa de mais {pts_needed} ponto(s)."
                    else:  # Generic message for other invalid counts
                        msg += (
                            f"Número inválido de pontos ({num_pts}). Use 4, 7, 10, ... "
                        )
                        msg += "Desenho não finalizado."
                    QMessageBox.warning(None, "Pontos Inválidos", msg)
                    # Similar to polygon, treat invalid commit as "still drawing"
                    return  # Early exit

                # Reset state if committed successfully OR if explicitly cancelled
                if (commit and can_commit_bezier) or not commit:
                    self._current_bezier_points = []
                    drawing_finished_or_cancelled = True
            elif (
                not commit
            ):  # Cancelled (e.g. mode change) when no points were even there
                drawing_finished_or_cancelled = True

        if drawing_finished_or_cancelled:
            self._remove_temp_items()
            self.status_message_requested.emit("Pronto.", 1000)
            # Ensure all drawing state variables are reset
            self._current_line_start = None
            self._current_polygon_points = []
            self._current_polygon_is_open = False
            self._current_polygon_is_filled = False
            self._current_bezier_points = []
            self._pending_first_polygon_point = None

    def _remove_temp_items(self) -> None:
        items_to_remove = [
            self._temp_line_item,
            self._temp_polygon_path,
            self._temp_bezier_path,
        ]
        for item in items_to_remove:
            if item and item.scene():
                self._scene.removeItem(item)
        self._temp_line_item = None
        self._temp_polygon_path = None
        self._temp_bezier_path = None
