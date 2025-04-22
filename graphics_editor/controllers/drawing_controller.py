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

# Importações relativas dentro do pacote
from ..state_manager import EditorStateManager, DrawingMode
from ..models.point import Point
from ..models.line import Line
from ..models.polygon import Polygon
from ..models.bezier_curve import BezierCurve  # Add BezierCurve

# Alias para tipos de dados dos modelos
DataObject = Union[Point, Line, Polygon, BezierCurve]  # Add BezierCurve
# Tuple of actual types for isinstance checks
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve)


class DrawingController(QObject):
    """Controla a lógica de desenho interativo na cena."""

    # Sinal emitido quando um objeto está pronto para ser adicionado à cena (APÓS finalização)
    object_ready_to_add = pyqtSignal(object)
    # Sinal para exibir mensagens na status bar
    status_message_requested = pyqtSignal(str, int)  # message, timeout (0=persistent)

    def __init__(
        self,
        scene: QGraphicsScene,
        state_manager: EditorStateManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager

        # --- Estado Interno do Desenho ---
        self._current_line_start: Optional[Point] = None
        self._current_polygon_points: List[Point] = []
        self._current_polygon_is_open: bool = False
        self._current_polygon_is_filled: bool = False
        self._current_bezier_points: List[Point] = []  # State for Bezier

        # --- Itens Gráficos Temporários (Pré-visualização) ---
        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path: Optional[QGraphicsPathItem] = None
        self._temp_bezier_path: Optional[QGraphicsPathItem] = (
            None  # Preview for Bezier control polygon
        )
        self._temp_item_pen = QPen(
            Qt.gray, 1, Qt.DashLine
        )  # Pen for line/poly preview edge
        self._temp_bezier_control_pen = QPen(
            Qt.darkCyan, 1, Qt.DotLine
        )  # Pen for Bezier control poly preview

        # Conectar ao sinal de mudança de modo para cancelar desenhos
        self._state_manager.drawing_mode_changed.connect(self._on_mode_changed)

    def _on_mode_changed(self, mode: DrawingMode):
        """Cancela qualquer desenho em progresso se o modo mudar."""
        # Only cancel if changing *away* from a drawing mode that has state
        drawing_modes_with_state = [
            DrawingMode.LINE,
            DrawingMode.POLYGON,
            DrawingMode.BEZIER,
        ]
        if (
            self._state_manager.drawing_mode() in drawing_modes_with_state
            and mode not in drawing_modes_with_state
        ):
            self.cancel_current_drawing()
        elif (
            self._state_manager.drawing_mode() != mode
        ):  # Clear state if changing between drawing modes too
            self.cancel_current_drawing()

    def handle_scene_left_click(self, scene_pos: QPointF):
        """Processa clique esquerdo para iniciar/continuar/finalizar desenho."""
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()
        current_point_data = Point(scene_pos.x(), scene_pos.y(), color=color)

        if mode == DrawingMode.POINT:
            self.object_ready_to_add.emit(current_point_data)

        elif mode == DrawingMode.LINE:
            if self._current_line_start is None:
                self._current_line_start = current_point_data
                self._update_line_preview(scene_pos)
                self.status_message_requested.emit(
                    "Linha: Clique no ponto final.", 0
                )  # Persistent status
            else:
                if (
                    current_point_data.get_coords()
                    == self._current_line_start.get_coords()
                ):
                    self.status_message_requested.emit(
                        "Ponto final igual ao inicial. Clique em outro lugar.", 2000
                    )
                    return  # Don't finish, wait for different point
                line_data = Line(
                    self._current_line_start, current_point_data, color=color
                )
                self.object_ready_to_add.emit(line_data)
                self._finish_current_drawing(commit=True)  # Resets state

        elif mode == DrawingMode.POLYGON:
            if not self._current_polygon_points:  # First point
                if not self._ask_polygon_type_and_fill():
                    return  # User cancelled dialog
                # Provide initial guidance
                pt_type = "vértices"
                end_action = "Botão direito para finalizar."
                self.status_message_requested.emit(
                    f"Polígono: Clique nos {pt_type}. {end_action}", 0
                )

            # Avoid consecutive duplicate points
            if (
                self._current_polygon_points
                and current_point_data.get_coords()
                == self._current_polygon_points[-1].get_coords()
            ):
                self.status_message_requested.emit("Ponto duplicado ignorado.", 1500)
                return

            self._current_polygon_points.append(current_point_data)
            self._update_polygon_preview(scene_pos)
            # Update status maybe? "X points added"

        elif mode == DrawingMode.BEZIER:
            self._current_bezier_points.append(current_point_data)
            self._update_bezier_preview(scene_pos)  # Update control polygon preview
            self._update_bezier_status_message()  # Update status bar guidance

    def _update_bezier_status_message(self):
        """Provides user guidance for drawing Bezier curves via status bar."""
        num_pts = len(self._current_bezier_points)
        status = f"Bézier: Ponto {num_pts} adicionado."
        min_finish_pts = 4
        can_finish = False

        if num_pts < min_finish_pts:
            pts_needed = min_finish_pts - num_pts
            status += f" Adicione mais {pts_needed} ponto(s) para o 1º segmento."
        else:
            # Check if current point count allows finishing (4, 7, 10, ...)
            if (num_pts - min_finish_pts) % 3 == 0:
                can_finish = True
                num_segments = (num_pts - 1) // 3
                status += f" Segmento {num_segments} completo."
                pts_needed_next = 3
                status += f" Adicione mais {pts_needed_next} para o próximo segmento."
            else:
                # Calculate points needed for the current segment
                pts_in_current_segment = (num_pts - 1) % 3
                pts_needed_current = 3 - pts_in_current_segment
                current_segment_index = (num_pts - 1) // 3 + 1
                status += f" Adicione mais {pts_needed_current} ponto(s) para completar o segmento {current_segment_index}."

        # Finishing guidance
        if can_finish:
            status += " Clique direito para finalizar."
        elif num_pts >= 1:  # Check if we have points but cannot finish yet
            # Calculate points needed to reach the *next* valid finishing count
            current_segment_group = (num_pts - 1) // 3
            next_finish_count = 4 + 3 * current_segment_group
            if (
                num_pts < next_finish_count
            ):  # Points needed to finish *current* segment group
                pts_to_next_finish = next_finish_count - num_pts
                status += (
                    f" (Precisa de mais {pts_to_next_finish} para poder finalizar)."
                )
            # If num_pts == next_finish_count, can_finish should be true already

        self.status_message_requested.emit(status, 0)  # Persistent message

    def handle_scene_right_click(self, scene_pos: QPointF):
        """Processa clique direito para finalizar polígono ou Bézier."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.POLYGON or mode == DrawingMode.BEZIER:
            self._finish_current_drawing(commit=True)

    def handle_scene_mouse_move(self, scene_pos: QPointF):
        """Processa movimento do mouse para pré-visualização."""
        mode = self._state_manager.drawing_mode()
        # Update preview only if in the corresponding mode and drawing has started
        if mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif mode == DrawingMode.POLYGON and self._current_polygon_points:
            self._update_polygon_preview(scene_pos)
        elif mode == DrawingMode.BEZIER and self._current_bezier_points:
            self._update_bezier_preview(scene_pos)

    def cancel_current_drawing(self):
        """Força o cancelamento do desenho atual e limpa o estado."""
        self._finish_current_drawing(commit=False)

    def _ask_polygon_type_and_fill(self) -> bool:
        """Pergunta ao usuário sobre o tipo (aberto/fechado) e preenchimento do polígono."""
        # Using QMessageBox directly here for simplicity. Ideally, signal Editor to show dialog.
        parent_widget = None  # No easy access to main window here

        type_reply = QMessageBox.question(
            parent_widget,
            "Tipo de Polígono",
            "Deseja criar uma Polilinha (ABERTA)?\n\n"
            "- Sim: Polilinha (>= 2 pontos).\n"
            "- Não: Polígono Fechado (>= 3 pontos).\n\n"
            "(Clique com o botão direito para finalizar)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # Default button
        )
        # If user closes the dialog or presses Esc, result might be different
        if type_reply not in [QMessageBox.Yes, QMessageBox.No]:
            return False  # Treat as cancellation

        self._current_polygon_is_open = type_reply == QMessageBox.Yes
        self._current_polygon_is_filled = False  # Default

        # Ask for fill only if creating a closed polygon
        if not self._current_polygon_is_open:
            fill_reply = QMessageBox.question(
                parent_widget,
                "Preenchimento",
                "Deseja preencher o polígono fechado?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,  # Default button
            )
            if fill_reply not in [QMessageBox.Yes, QMessageBox.No]:
                return False  # Treat as cancellation
            self._current_polygon_is_filled = fill_reply == QMessageBox.Yes

        return True  # Configuration successful

    def _update_line_preview(self, current_pos: QPointF):
        """Atualiza ou cria a linha de pré-visualização."""
        if not self._current_line_start:
            return
        start_qpos = self._current_line_start.to_qpointf()
        line = QLineF(start_qpos, current_pos)

        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(line)
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)  # Ensure preview is on top
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(line)

    def _update_polygon_preview(self, current_pos: QPointF):
        """Atualiza ou cria o caminho de pré-visualização do polígono."""
        if not self._current_polygon_points:
            return

        path = QPainterPath()
        path.moveTo(self._current_polygon_points[0].to_qpointf())
        for point_data in self._current_polygon_points[1:]:
            path.lineTo(point_data.to_qpointf())
        # Draw line to current cursor position for visual feedback
        path.lineTo(current_pos)
        # Don't automatically close the preview path here, keeps visual distinction

        if self._temp_polygon_path is None:
            self._temp_polygon_path = QGraphicsPathItem(path)
            self._temp_polygon_path.setPen(self._temp_item_pen)
            self._temp_polygon_path.setZValue(1000)
            self._scene.addItem(self._temp_polygon_path)
        else:
            self._temp_polygon_path.setPath(path)

    def _update_bezier_preview(self, current_pos: QPointF):
        """Atualiza ou cria o caminho de pré-visualização da curva de Bézier (mostra polígono de controle)."""
        if not self._current_bezier_points:
            return

        path = QPainterPath()
        path.moveTo(self._current_bezier_points[0].to_qpointf())
        for point_data in self._current_bezier_points[1:]:
            path.lineTo(point_data.to_qpointf())
        # Draw dashed line from last control point to cursor
        path.lineTo(current_pos)

        if self._temp_bezier_path is None:
            self._temp_bezier_path = QGraphicsPathItem(path)
            # Use a distinct pen for the control polygon preview
            self._temp_bezier_path.setPen(self._temp_bezier_control_pen)
            self._temp_bezier_path.setZValue(
                999
            )  # Slightly behind other temp items if needed
            self._scene.addItem(self._temp_bezier_path)
        else:
            self._temp_bezier_path.setPath(path)

        # Optional: Draw the actual curve preview dynamically if enough points exist
        # This can be computationally more expensive during mouse move.
        # Example (simplified, needs refinement):
        # if len(self._current_bezier_points) >= 4 and (len(self._current_bezier_points)-1)%3 == 0:
        #     # Create temporary BezierCurve object and sample it
        #     temp_curve = BezierCurve(self._current_bezier_points, color=Qt.gray)
        #     sampled_points = temp_curve.sample_curve(10) # Lower sample count for preview
        #     curve_path = QPainterPath()
        #     curve_path.moveTo(sampled_points[0])
        #     for pt in sampled_points[1:]: curve_path.lineTo(pt)
        #     # Need another QGraphicsPathItem for the curve itself...

    def _finish_current_drawing(self, commit: bool = True) -> None:
        """Finaliza ou cancela a operação de desenho atual (linha/polígono/bezier)."""
        drawing_finished_or_cancelled = False
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()

        # --- Line ---
        if mode == DrawingMode.LINE and self._current_line_start:
            # Line is committed on the second click (handled in handle_scene_left_click).
            # This function only resets the state if commit=false (cancel) or after commit=true.
            self._current_line_start = None  # Reset state
            drawing_finished_or_cancelled = True  # State is cleared

        # --- Polygon ---
        elif mode == DrawingMode.POLYGON and self._current_polygon_points:
            min_points_needed = 2 if self._current_polygon_is_open else 3
            can_commit = len(self._current_polygon_points) >= min_points_needed

            if commit and can_commit:
                # Create final Polygon object
                polygon_data = Polygon(
                    self._current_polygon_points.copy(),  # Use copy of list
                    is_open=self._current_polygon_is_open,
                    color=color,
                    is_filled=self._current_polygon_is_filled,
                )
                self.object_ready_to_add.emit(polygon_data)
            elif commit and not can_commit:
                # User tried to finish without enough points
                QMessageBox.warning(
                    None,
                    "Pontos Insuficientes",
                    f"Polígono {'aberto' if self._current_polygon_is_open else 'fechado'} "
                    f"requer {min_points_needed} pontos (você tem {len(self._current_polygon_points)}). "
                    "Continue clicando ou cancele mudando de modo.",
                )
                return  # Don't reset state, allow adding more points

            # Reset state only if committed successfully or cancelled explicitly
            if (commit and can_commit) or not commit:
                self._current_polygon_points = []
                self._current_polygon_is_open = False
                self._current_polygon_is_filled = False
                drawing_finished_or_cancelled = True

        # --- Bezier ---
        elif mode == DrawingMode.BEZIER and self._current_bezier_points:
            num_pts = len(self._current_bezier_points)
            # Valid count check: 4, 7, 10, ... (i.e., 3*N + 1 where N>=1)
            is_valid_count = num_pts >= 4 and (num_pts - 4) % 3 == 0
            can_commit = is_valid_count

            if commit and can_commit:
                # Create final BezierCurve object
                bezier_data = BezierCurve(
                    self._current_bezier_points.copy(), color=color  # Use copy of list
                )
                self.object_ready_to_add.emit(bezier_data)
            elif commit and not can_commit:
                # User tried to finish with invalid number of points
                pts_needed = -1
                if num_pts < 4:
                    pts_needed = 4 - num_pts
                else:
                    pts_needed = 3 - (
                        (num_pts - 1) % 3
                    )  # Points needed to complete current segment

                msg = f"Não é possível finalizar a curva de Bézier. "
                if pts_needed > 0:
                    msg += f"Precisa de mais {pts_needed} ponto(s) para completar o último segmento (total {num_pts + pts_needed})."
                else:
                    msg += f"Número inválido de pontos ({num_pts}). Use 4, 7, 10, ..."
                QMessageBox.warning(
                    None,
                    "Pontos Inválidos",
                    msg + "\nContinue clicando ou cancele mudando de modo.",
                )
                return  # Don't reset state

            # Reset state only if committed successfully or cancelled explicitly
            if (commit and can_commit) or not commit:
                self._current_bezier_points = []
                drawing_finished_or_cancelled = True

        # --- Cleanup ---
        if drawing_finished_or_cancelled:
            self._remove_temp_items()
            # Reset status bar message unless another persistent message was set
            if self.status_message_requested:
                # Check if current message is persistent (timeout 0) before resetting
                # This requires knowing the current message, complex without more state.
                # Simple approach: always reset to "Pronto." after drawing finishes/cancels.
                self.status_message_requested.emit("Pronto.", 1000)

    def _remove_temp_items(self) -> None:
        """Remove itens gráficos temporários da cena."""
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
