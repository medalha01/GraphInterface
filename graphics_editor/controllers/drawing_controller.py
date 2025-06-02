# graphics_editor/controllers/drawing_controller.py
from PyQt5.QtCore import QObject, pyqtSignal, QPointF, QLineF, Qt
from PyQt5.QtGui import QPainterPath, QPen, QColor, QPolygonF
from PyQt5.QtWidgets import (
    QGraphicsScene, QGraphicsLineItem, QGraphicsPathItem, QMessageBox,
)
from typing import List, Optional, Tuple, Union

from ..state_manager import EditorStateManager, DrawingMode
from ..models.point import Point
from ..models.line import Line
from ..models.polygon import Polygon
from ..models.bezier_curve import BezierCurve
from ..models.bspline_curve import BSplineCurve # Adicionado

# Define DataObject para incluir BSplineCurve
DataObject2D = Union[Point, Line, Polygon, BezierCurve, BSplineCurve]


class DrawingController(QObject):
    """
    Controlador responsável pelo processo de desenho de objetos 2D na cena.
    Gerencia o estado do desenho interativo (cliques do mouse), visualização prévia
    e finalização dos objetos 2D.
    """

    object_ready_to_add = pyqtSignal(object) # Emite DataObject2D
    status_message_requested = pyqtSignal(str, int) # (mensagem, timeout_ms)
    polygon_properties_query_requested = pyqtSignal() # Para GraphicsEditor mostrar diálogo

    def __init__(
        self,
        scene: QGraphicsScene,
        state_manager: EditorStateManager,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager

        # Estado para desenho de linha
        self._current_line_start: Optional[Point] = None
        # Estado para desenho de polígono
        self._current_polygon_points: List[Point] = []
        self._current_polygon_is_open: bool = False
        self._current_polygon_is_filled: bool = False
        self._pending_first_polygon_point: Optional[Point] = None # Para consulta de propriedades
        # Estado para desenho de Bézier
        self._current_bezier_points: List[Point] = []
        # Estado para desenho de B-spline
        self._current_bspline_points: List[Point] = []


        # Itens temporários para visualização prévia
        self._temp_item_color = QColor(128, 128, 128, 150) # Cinza translúcido para preview
        self._temp_item_pen = QPen(self._temp_item_color, 2, Qt.DashLine) # Linha tracejada
        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path_item: Optional[QGraphicsPathItem] = None # Renomeado para clareza
        self._temp_bezier_path_item: Optional[QGraphicsPathItem] = None # Renomeado
        self._temp_bspline_path_item: Optional[QGraphicsPathItem] = None # Novo

        self._state_manager.drawing_mode_changed.connect(self.cancel_current_drawing)


    def set_pending_polygon_properties(
        self, is_open: bool, is_filled: bool, cancelled: bool = False
    ):
        """Define propriedades do polígono pendente após consulta ao usuário."""
        if cancelled or self._pending_first_polygon_point is None:
            self.status_message_requested.emit("Desenho de polígono cancelado.", 2000)
            self._finish_current_drawing(commit=False) # Reseta estado do polígono
            return

        self._current_polygon_is_open = is_open
        self._current_polygon_is_filled = is_filled
        
        first_point_data = self._pending_first_polygon_point
        self._pending_first_polygon_point = None # Limpa após uso

        self._current_polygon_points.append(first_point_data)
        self._update_polygon_preview(first_point_data.to_qpointf()) # Mostra preview com o 1º ponto

        pt_type = "vértices da polilinha" if self._current_polygon_is_open else "vértices do polígono"
        self.status_message_requested.emit(f"Polígono: Clique nos {pt_type}. Botão direito para finalizar.", 0)

    def handle_scene_left_click(self, scene_pos: QPointF):
        """Manipula clique esquerdo na cena para desenho 2D."""
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()
        current_point_model = Point(scene_pos.x(), scene_pos.y(), color=color)

        if mode == DrawingMode.POINT:
            self.object_ready_to_add.emit(current_point_model)
        elif mode == DrawingMode.LINE:
            self._handle_line_click(current_point_model, color)
        elif mode == DrawingMode.POLYGON:
            self._handle_polygon_click(current_point_model)
        elif mode == DrawingMode.BEZIER:
            self._handle_bezier_click(current_point_model)
        elif mode == DrawingMode.BSPLINE:
            self._handle_bspline_click(current_point_model)


    def _handle_line_click(self, point_model: Point, color: QColor):
        if self._current_line_start is None: # Primeiro clique para a linha
            self._current_line_start = point_model
            self._update_line_preview(point_model.to_qpointf()) # Inicia preview
            self.status_message_requested.emit("Linha: Clique no ponto final.", 0)
        else: # Segundo clique, finaliza a linha
            if point_model.get_coords() == self._current_line_start.get_coords():
                self.status_message_requested.emit("Ponto final igual ao inicial. Clique em outro lugar.", 2000)
                return
            line_data = Line(self._current_line_start, point_model, color=color)
            self.object_ready_to_add.emit(line_data)
            self._finish_current_drawing(commit=True)

    def _handle_polygon_click(self, point_model: Point):
        if not self._current_polygon_points and self._pending_first_polygon_point is None:
            # Primeiro clique para o polígono, consulta propriedades
            self._pending_first_polygon_point = point_model
            self.polygon_properties_query_requested.emit()
            return # Aguarda propriedades

        # Se propriedades já foram definidas (ou é o segundo+ ponto)
        if self._current_polygon_points and point_model.get_coords() == self._current_polygon_points[-1].get_coords():
            self.status_message_requested.emit("Ponto duplicado ignorado.", 1500)
            return

        if self._pending_first_polygon_point is not None: # Usuário clicou antes de diálogo de props fechar
            self.status_message_requested.emit("Aguardando definição de tipo de polígono.", 2000)
            return

        self._current_polygon_points.append(point_model)
        self._update_polygon_preview(point_model.to_qpointf())
        num_pts = len(self._current_polygon_points)
        pt_type = "vértices da polilinha" if self._current_polygon_is_open else "vértices do polígono"
        self.status_message_requested.emit(f"Polígono: {num_pts} {pt_type} adicionado(s). Botão direito para finalizar.",0)


    def _handle_bezier_click(self, point_model: Point):
        self._current_bezier_points.append(point_model)
        self._update_bezier_preview(point_model.to_qpointf())
        self._update_bezier_status_message()

    def _handle_bspline_click(self, point_model: Point):
        self._current_bspline_points.append(point_model)
        self._update_bspline_preview(point_model.to_qpointf()) # Passa o último ponto clicado
        self._update_bspline_status_message()


    def _update_bezier_status_message(self):
        num_pts = len(self._current_bezier_points)
        status = f"Bézier: {num_pts} ponto(s) de controle."
        # Lógica para indicar quantos pontos faltam para completar um segmento
        # Um segmento precisa de 4 pontos. Segmentos C0 compartilham o último/primeiro ponto.
        # Curva com k segmentos tem 3k+1 pontos.
        if num_pts < 4:
            status += f" Adicione mais {4 - num_pts} para o 1º segmento."
        elif (num_pts - 1) % 3 == 0: # Completa um ou mais segmentos
            num_segments = (num_pts - 1) // 3
            status += f" {num_segments} segmento(s) completo(s). Adicione +3 para próximo, ou finalize."
        else: # Em meio a um segmento
            pts_in_current = (num_pts -1) % 3
            needed_for_current = 3 - pts_in_current
            status += f" Adicione mais {needed_for_current} para completar segmento atual."
        status += " Botão direito para finalizar."
        self.status_message_requested.emit(status, 0)

    def _update_bspline_status_message(self):
        num_pts = len(self._current_bspline_points)
        min_pts_for_default_degree = BSplineCurve.DEFAULT_DEGREE + 1
        if num_pts == 0:
            status = f"B-spline: Clique para adicionar pontos de controle (mín {min_pts_for_default_degree} para grau {BSplineCurve.DEFAULT_DEGREE})."
        elif num_pts < min_pts_for_default_degree:
            status = f"B-spline: {num_pts} ponto(s). Adicione mais {min_pts_for_default_degree - num_pts} para grau {BSplineCurve.DEFAULT_DEGREE}."
        else:
            status = f"B-spline: {num_pts} ponto(s) de controle."
        status += " Botão direito para finalizar."
        self.status_message_requested.emit(status, 0)


    def handle_scene_right_click(self, scene_pos: QPointF):
        """Finaliza desenho de Polígono, Bézier ou B-spline."""
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.POLYGON, DrawingMode.BEZIER, DrawingMode.BSPLINE]:
            self._finish_current_drawing(commit=True)

    def handle_scene_mouse_move(self, scene_pos: QPointF):
        """Atualiza preview durante movimento do mouse."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif mode == DrawingMode.POLYGON and self._current_polygon_points:
            self._update_polygon_preview(scene_pos)
        elif mode == DrawingMode.BEZIER and self._current_bezier_points:
            self._update_bezier_preview(scene_pos)
        elif mode == DrawingMode.BSPLINE and self._current_bspline_points:
            self._update_bspline_preview(scene_pos)


    def cancel_current_drawing(self):
        """Cancela o desenho 2D atual."""
        self._finish_current_drawing(commit=False)

    def _update_line_preview(self, current_pos: QPointF):
        if not self._current_line_start: return
        line = QLineF(self._current_line_start.to_qpointf(), current_pos)
        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(line)
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000) # Garante que fica por cima
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(line)

    def _update_polygon_preview(self, current_pos: QPointF):
        if not self._current_polygon_points: return
        path = QPainterPath(self._current_polygon_points[0].to_qpointf())
        for point_model in self._current_polygon_points[1:]:
            path.lineTo(point_model.to_qpointf())
        path.lineTo(current_pos) # Linha até o cursor
        
        if not self._current_polygon_is_open: # Se for fechado, simula fechar com o primeiro ponto
            path.lineTo(self._current_polygon_points[0].to_qpointf())

        if self._temp_polygon_path_item is None:
            self._temp_polygon_path_item = QGraphicsPathItem(path)
            self._temp_polygon_path_item.setPen(self._temp_item_pen)
            self._temp_polygon_path_item.setZValue(1000)
            self._scene.addItem(self._temp_polygon_path_item)
        else:
            self._temp_polygon_path_item.setPath(path)

    def _update_bezier_preview(self, current_pos: QPointF):
        # Para Bézier, o preview pode ser apenas o polígono de controle
        if not self._current_bezier_points: return
        
        path = QPainterPath(self._current_bezier_points[0].to_qpointf())
        # Desenha linhas entre os pontos de controle já clicados
        for point_model in self._current_bezier_points[1:]:
            path.lineTo(point_model.to_qpointf())
        # Linha até a posição atual do mouse
        path.lineTo(current_pos) 

        if self._temp_bezier_path_item is None:
            self._temp_bezier_path_item = QGraphicsPathItem(path)
            self._temp_bezier_path_item.setPen(self._temp_item_pen)
            self._temp_bezier_path_item.setZValue(1000)
            self._scene.addItem(self._temp_bezier_path_item)
        else:
            self._temp_bezier_path_item.setPath(path)

    def _update_bspline_preview(self, current_pos: QPointF):
        if not self._current_bspline_points: return

        # Cria uma lista temporária de pontos incluindo a posição atual do mouse
        temp_control_points = self._current_bspline_points + [Point(current_pos.x(), current_pos.y())]
        
        if len(temp_control_points) < 2: # Não pode desenhar curva ou linha
            if self._temp_bspline_path_item: # Limpa preview anterior se houver
                self._scene.removeItem(self._temp_bspline_path_item)
                self._temp_bspline_path_item = None
            return

        try:
            # Tenta criar uma B-spline temporária para preview
            # O grau pode ser ajustado para preview se houver poucos pontos
            preview_degree = min(BSplineCurve.DEFAULT_DEGREE, len(temp_control_points) - 1)
            if preview_degree < 1: preview_degree = 1 # Mínimo grau 1 (polilinha)

            temp_bspline = BSplineCurve(temp_control_points, degree=preview_degree, color=self._temp_item_color)
            preview_graphics_item = temp_bspline.create_graphics_item() # Retorna QGraphicsPathItem
            
            if self._temp_bspline_path_item is None:
                self._temp_bspline_path_item = preview_graphics_item
                self._temp_bspline_path_item.setPen(self._temp_item_pen) # Garante estilo de preview
                self._temp_bspline_path_item.setZValue(1000)
                self._scene.addItem(self._temp_bspline_path_item)
            else:
                self._temp_bspline_path_item.setPath(preview_graphics_item.path())
        except ValueError: # Se não for possível criar B-spline (e.g. poucos pontos para o grau)
            # Fallback: desenha apenas o polígono de controle como preview
            path = QPainterPath(temp_control_points[0].to_qpointf())
            for point_model in temp_control_points[1:]:
                path.lineTo(point_model.to_qpointf())
            
            if self._temp_bspline_path_item is None:
                self._temp_bspline_path_item = QGraphicsPathItem(path)
                self._temp_bspline_path_item.setPen(self._temp_item_pen)
                self._temp_bspline_path_item.setZValue(1000)
                self._scene.addItem(self._temp_bspline_path_item)
            else:
                self._temp_bspline_path_item.setPath(path)


    def _finish_current_drawing(self, commit: bool = True):
        """Finaliza o desenho 2D atual, opcionalmente criando o objeto."""
        mode = self._state_manager.drawing_mode()
        color = self._state_manager.draw_color()
        drawing_was_active = False # Flag para saber se algo foi resetado

        # Sempre limpa estado de polígono pendente
        self._pending_first_polygon_point = None

        if mode == DrawingMode.LINE:
            if self._current_line_start: drawing_was_active = True
            # Linha é finalizada no segundo clique esquerdo, aqui apenas reseta se commit=False (cancelar)
            if not commit: self._current_line_start = None
        
        elif mode == DrawingMode.POLYGON:
            if self._current_polygon_points: drawing_was_active = True
            min_pts = 2 if self._current_polygon_is_open else 3
            can_commit = len(self._current_polygon_points) >= min_pts
            if commit and can_commit:
                poly_data = Polygon(self._current_polygon_points.copy(),
                                    is_open=self._current_polygon_is_open,
                                    color=color, is_filled=self._current_polygon_is_filled)
                self.object_ready_to_add.emit(poly_data)
            elif commit and not can_commit:
                QMessageBox.warning(None, "Pontos Insuficientes",
                                    f"Polígono {'aberto' if self._current_polygon_is_open else 'fechado'} "
                                    f"requer {min_pts} pontos (tem {len(self._current_polygon_points)}). Desenho não finalizado.")
                return # Não reseta, permite continuar desenhando

            if (commit and can_commit) or not commit: # Resetar se commit válido ou cancelamento
                self._current_polygon_points = []
                self._current_polygon_is_open = False
                self._current_polygon_is_filled = False
        
        elif mode == DrawingMode.BEZIER:
            if self._current_bezier_points: drawing_was_active = True
            num_pts = len(self._current_bezier_points)
            can_commit = num_pts >= 4 and (num_pts - 1) % 3 == 0
            if commit and can_commit:
                bezier_data = BezierCurve(self._current_bezier_points.copy(), color=color)
                self.object_ready_to_add.emit(bezier_data)
            elif commit and not can_commit:
                # Lógica de mensagem de erro para Bézier pode ser mais detalhada
                QMessageBox.warning(None, "Pontos Inválidos para Bézier",
                                    f"Número de pontos ({num_pts}) inválido. Use 4, 7, 10,... Desenho não finalizado.")
                return
            if (commit and can_commit) or not commit:
                self._current_bezier_points = []

        elif mode == DrawingMode.BSPLINE:
            if self._current_bspline_points: drawing_was_active = True
            num_pts = len(self._current_bspline_points)
            # B-spline precisa de pelo menos grau+1 pontos. Para grau padrão 3, são 4 pontos.
            # Para grau 1 (polilinha), são 2 pontos.
            min_pts_for_default_degree = BSplineCurve.DEFAULT_DEGREE + 1
            can_commit = num_pts >= min_pts_for_default_degree 
            if commit and can_commit:
                bspline_data = BSplineCurve(self._current_bspline_points.copy(), color=color, degree=BSplineCurve.DEFAULT_DEGREE)
                self.object_ready_to_add.emit(bspline_data)
            elif commit and not can_commit:
                 QMessageBox.warning(None, "Pontos Insuficientes para B-spline",
                                    f"B-spline (grau {BSplineCurve.DEFAULT_DEGREE}) requer pelo menos {min_pts_for_default_degree} "
                                    f"pontos de controle (tem {num_pts}). Desenho não finalizado.")
                 return # Não reseta, permite continuar
            if (commit and can_commit) or not commit:
                self._current_bspline_points = []


        if drawing_was_active or not commit: # Se algo estava ativo ou é um cancelamento explícito
            self._remove_temp_items()
            self.status_message_requested.emit("Pronto.", 1000)
            # Garante reset de todos os estados de desenho 2D
            self._current_line_start = None
            self._current_polygon_points = []
            self._current_polygon_is_open = False
            self._current_polygon_is_filled = False
            self._current_bezier_points = []
            self._current_bspline_points = []
            self._pending_first_polygon_point = None


    def _remove_temp_items(self) -> None:
        """Remove todos os itens de preview temporários da cena."""
        temp_items = [self._temp_line_item, self._temp_polygon_path_item, 
                      self._temp_bezier_path_item, self._temp_bspline_path_item]
        for item in temp_items:
            if item and item.scene():
                self._scene.removeItem(item)
        self._temp_line_item = None
        self._temp_polygon_path_item = None
        self._temp_bezier_path_item = None
        self._temp_bspline_path_item = None