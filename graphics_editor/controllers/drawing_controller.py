# graphics_editor/controllers/drawing_controller.py
from PyQt5.QtCore import Qt
from PyQt5.QtCore import QObject, pyqtSignal, QPointF, Qt
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

# Alias para tipos de dados dos modelos
DataObject = Union[Point, Line, Polygon]


class DrawingController(QObject):
    """Controla a lógica de desenho interativo na cena."""

    # Sinal emitido quando um objeto está pronto para ser adicionado à cena (APÓS finalização)
    object_ready_to_add = pyqtSignal(object)
    # Sinal para exibir mensagens na status bar
    status_message_requested = pyqtSignal(str, int)

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

        # --- Itens Gráficos Temporários (Pré-visualização) ---
        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path: Optional[QGraphicsPathItem] = None
        self._temp_item_pen = QPen(Qt.gray, 1, Qt.DashLine)

        # Conectar ao sinal de mudança de modo para cancelar desenhos
        self._state_manager.drawing_mode_changed.connect(self._on_mode_changed)

    def _on_mode_changed(self, mode: DrawingMode):
        """Cancela qualquer desenho em progresso se o modo mudar."""
        if mode not in [DrawingMode.LINE, DrawingMode.POLYGON]:
            self.cancel_current_drawing()

    def handle_scene_left_click(self, scene_pos: QPointF):
        """Processa clique esquerdo para iniciar/continuar/finalizar desenho."""
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()

        if mode == DrawingMode.POINT:
            point_data = Point(scene_pos.x(), scene_pos.y(), color=color)
            self.object_ready_to_add.emit(
                point_data
            )  # Ponto é adicionado imediatamente

        elif mode == DrawingMode.LINE:
            current_point_data = Point(scene_pos.x(), scene_pos.y(), color=color)
            if self._current_line_start is None:
                # Inicia linha
                self._current_line_start = current_point_data
                self._update_line_preview(scene_pos)
            else:
                # Finaliza linha
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
                self.object_ready_to_add.emit(line_data)  # Emite linha completa
                self._finish_current_drawing(commit=True)

        elif mode == DrawingMode.POLYGON:
            current_point_data = Point(scene_pos.x(), scene_pos.y(), color=color)
            if not self._current_polygon_points:
                # Primeiro ponto do polígono: pergunta tipo e preenchimento
                if not self._ask_polygon_type_and_fill():
                    return  # Usuário cancelou ou fechou a caixa de diálogo

            # Evita pontos duplicados consecutivos
            if (
                self._current_polygon_points
                and current_point_data.get_coords()
                == self._current_polygon_points[-1].get_coords()
            ):
                self.status_message_requested.emit("Ponto duplicado ignorado.", 1500)
                return

            self._current_polygon_points.append(current_point_data)
            self._update_polygon_preview(scene_pos)

    def handle_scene_right_click(self, scene_pos: QPointF):
        """Processa clique direito para finalizar polígono."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.POLYGON:
            self._finish_current_drawing(commit=True)

    def handle_scene_mouse_move(self, scene_pos: QPointF):
        """Processa movimento do mouse para pré-visualização."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif mode == DrawingMode.POLYGON and self._current_polygon_points:
            self._update_polygon_preview(scene_pos)

    def cancel_current_drawing(self):
        """Força o cancelamento do desenho atual."""
        self._finish_current_drawing(commit=False)

    def _ask_polygon_type_and_fill(self) -> bool:
        """Pergunta ao usuário sobre o tipo (aberto/fechado) e preenchimento do polígono."""
        # Precisamos de um widget pai para o QMessageBox, mas o controlador não tem um.
        # A solução ideal é o controlador emitir um sinal requisitando o diálogo,
        # e o Editor (que é um QWidget) o exibe.
        # Por simplicidade aqui, vamos usar None como pai, o que pode não ser ideal.
        # TODO: Refatorar para usar sinal/slot com Editor para exibir QMessageBox.

        parent_widget = None  # Idealmente seria o GraphicsEditor

        type_reply = QMessageBox.question(
            parent_widget,  # Usando None pode não funcionar corretamente em todos os OS/cenários
            "Tipo de Polígono",
            "Deseja criar uma Polilinha (ABERTA)?\n\n"
            "- Sim: Polilinha (>= 2 pontos).\n"
            "- Não: Polígono Fechado (>= 3 pontos).\n\n"
            "(Clique com o botão direito para finalizar)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        # Se o usuário fechar a caixa, o resultado pode não ser Yes ou No.
        if type_reply not in [QMessageBox.Yes, QMessageBox.No]:
            return False  # Indica cancelamento

        self._current_polygon_is_open = type_reply == QMessageBox.Yes
        self._current_polygon_is_filled = False

        if not self._current_polygon_is_open:
            fill_reply = QMessageBox.question(
                parent_widget,
                "Preenchimento",
                "Deseja preencher o polígono fechado?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if fill_reply not in [QMessageBox.Yes, QMessageBox.No]:
                return False  # Indica cancelamento
            self._current_polygon_is_filled = fill_reply == QMessageBox.Yes

        return True  # Configuração feita com sucesso

    def _update_line_preview(self, current_pos: QPointF):
        """Atualiza ou cria a linha de pré-visualização."""
        if not self._current_line_start:
            return
        start_qpos = self._current_line_start.to_qpointf()

        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(
                start_qpos.x(), start_qpos.y(), current_pos.x(), current_pos.y()
            )
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)  # Fica por cima
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(
                start_qpos.x(), start_qpos.y(), current_pos.x(), current_pos.y()
            )

    def _update_polygon_preview(self, current_pos: QPointF):
        """Atualiza ou cria o caminho de pré-visualização do polígono."""
        if not self._current_polygon_points:
            return

        path = QPainterPath()
        path.moveTo(self._current_polygon_points[0].to_qpointf())
        for point_data in self._current_polygon_points[1:]:
            path.lineTo(point_data.to_qpointf())
        path.lineTo(current_pos)  # Linha até o cursor

        if self._temp_polygon_path is None:
            self._temp_polygon_path = QGraphicsPathItem()
            self._temp_polygon_path.setPen(self._temp_item_pen)
            self._temp_polygon_path.setZValue(1000)
            self._scene.addItem(self._temp_polygon_path)

        self._temp_polygon_path.setPath(path)

    def _finish_current_drawing(self, commit: bool = True) -> None:
        """Finaliza ou cancela a operação de desenho atual (linha/polígono)."""
        drawing_finished_or_cancelled = False
        mode = self._state_manager.drawing_mode()  # Pega modo atual

        if mode == DrawingMode.LINE and self._current_line_start:
            # Commit da linha é feito no segundo clique, aqui só cancela o estado
            self._current_line_start = None
            drawing_finished_or_cancelled = True

        elif mode == DrawingMode.POLYGON and self._current_polygon_points:
            min_points_needed = 2 if self._current_polygon_is_open else 3
            can_commit = len(self._current_polygon_points) >= min_points_needed

            if commit and can_commit:
                # Cria o objeto Polygon final e emite o sinal
                polygon_data = Polygon(
                    self._current_polygon_points.copy(),
                    is_open=self._current_polygon_is_open,
                    color=self._state_manager.draw_color(),  # Pega cor atual
                    is_filled=self._current_polygon_is_filled,
                )
                self.object_ready_to_add.emit(polygon_data)  # Emite polígono completo
            elif commit and not can_commit:
                # Tentou finalizar sem pontos suficientes
                # TODO: Usar sinal para pedir ao Editor para mostrar QMessageBox
                QMessageBox.warning(
                    None,  # Idealmente seria o GraphicsEditor
                    "Pontos Insuficientes",
                    f"Não é possível finalizar o polígono {'aberto' if self._current_polygon_is_open else 'fechado'}. "
                    f"Requer {min_points_needed} pontos (você tem {len(self._current_polygon_points)}). "
                    "Continue clicando ou cancele mudando de modo.",
                )
                return  # Não reseta, permite continuar adicionando pontos

            # Reseta estado do polígono (se commit bem sucedido ou cancelamento)
            # Só reseta se commit=True e can_commit=True, ou se commit=False
            if (commit and can_commit) or not commit:
                self._current_polygon_points = []
                self._current_polygon_is_open = False
                self._current_polygon_is_filled = False
                drawing_finished_or_cancelled = True

        if drawing_finished_or_cancelled:
            self._remove_temp_items()

    def _remove_temp_items(self) -> None:
        """Remove itens gráficos temporários da cena."""
        if self._temp_line_item and self._temp_line_item.scene():
            self._scene.removeItem(self._temp_line_item)
        self._temp_line_item = None
        if self._temp_polygon_path and self._temp_polygon_path.scene():
            self._scene.removeItem(self._temp_polygon_path)
        self._temp_polygon_path = None
