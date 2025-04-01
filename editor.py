# editor.py
import sys
from enum import Enum, auto
from typing import List, Optional, Tuple

from PyQt5.QtWidgets import (QApplication, QMainWindow, QGraphicsScene,
                             QToolBar, QAction, QActionGroup, QDialog,
                             QMessageBox, QGraphicsView, QGraphicsLineItem,
                             QGraphicsPathItem, QInputDialog, QGraphicsEllipseItem,
                             QGraphicsPolygonItem, QColorDialog, QPushButton, QGraphicsItem)
from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QSize
from PyQt5.QtGui import QPainterPath, QPen, QColor, QPolygonF, QIcon, QPixmap

from view import GraphicsView
from models.point import Point
from models.line import Line
from models.polygon import Polygon
from models.coordinates_input import CoordinateInputDialog
from controllers.transformation_controller import TransformationController


class DrawingMode(Enum):
    POINT = auto()
    LINE = auto()
    POLYGON = auto()
    SELECT = auto()
    PAN = auto()

class GraphicsEditor(QMainWindow):
    """Janela principal da aplicação para o editor gráfico."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Editor Gráfico (com Transformações e Cores)")
        self.resize(1000, 750)

        # --- Estado Interno ---
        self._drawing_mode: DrawingMode = DrawingMode.SELECT
        self._current_line_start: Optional[Point] = None
        self._current_polygon_points: List[Point] = []
        self._current_polygon_is_open: bool = False
        self._current_draw_color: QColor = QColor(Qt.black)

        # --- Itens de Pré-visualização ---
        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path: Optional[QGraphicsPathItem] = None
        self._temp_item_pen = QPen(Qt.gray, 1, Qt.DashLine)

        # --- Componentes Principais ---
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-5000, -5000, 10000, 10000)
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

        # --- Controller ---
        self._transformation_controller = TransformationController(self)

        # --- Configuração ---
        self._setup_toolbar()
        self._connect_signals()
        self._update_view_interaction()
        self.show()

    def _setup_toolbar(self) -> None:
        """Cria e configura a barra de ferramentas principal."""
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.LeftToolBarArea, toolbar)

        # --- Ações de Modo ---
        self._mode_action_group = QActionGroup(self)
        self._mode_action_group.setExclusive(True)
        modes = [
            ("Selecionar", DrawingMode.SELECT, "Selecionar itens (Padrão)", "icons/select.png"),
            ("Mover Vista", DrawingMode.PAN, "Mover a vista (Ferramenta Mão)", "icons/pan.png"),
            ("Ponto", DrawingMode.POINT, "Desenhar um ponto único", "icons/point.png"),
            ("Linha", DrawingMode.LINE, "Desenhar uma linha (2 cliques)", "icons/line.png"),
            ("Polígono", DrawingMode.POLYGON, "Desenhar um polígono (múltiplos cliques, botão direito para finalizar)", "icons/polygon.png"),
        ]
        for name, mode, tip, icon_path in modes:
            action = QAction(QIcon(icon_path), name, self)
            action.setToolTip(tip); action.setCheckable(True); action.setData(mode)
            action.triggered.connect(self._on_mode_action_triggered)
            toolbar.addAction(action); self._mode_action_group.addAction(action)
            if mode == self._drawing_mode: action.setChecked(True)

        toolbar.addSeparator()

        # --- Seleção de Cor ---
        self.color_action = QAction(self._create_color_icon(self._current_draw_color), "Cor Desenho", self)
        self.color_action.setToolTip("Selecionar cor para novos objetos")
        self.color_action.triggered.connect(self._select_drawing_color)
        toolbar.addAction(self.color_action)

        toolbar.addSeparator()

        # --- Entrada de Coordenadas ---
        manual_coord_action = QAction(QIcon("icons/coords.png"), "Coordenadas Manuais", self)
        manual_coord_action.setToolTip("Adicionar forma via diálogo de coordenadas")
        manual_coord_action.triggered.connect(self._open_coordinate_input_dialog)
        toolbar.addAction(manual_coord_action)

        toolbar.addSeparator()

        # --- Ação de Transformação ---
        transform_action = QAction(QIcon("icons/transform.png"), "Transformar Objeto", self)
        transform_action.setToolTip("Aplicar translação, escala ou rotação ao objeto selecionado")
        transform_action.triggered.connect(self._open_transformation_dialog)
        toolbar.addAction(transform_action)

    def _create_color_icon(self, color: QColor, size: int = 16) -> QIcon:
        """Cria um QIcon com um retângulo de cor sólida."""
        pixmap = QPixmap(size, size)
        pixmap.fill(color)
        return QIcon(pixmap)

    def _connect_signals(self) -> None:
        """Conecta sinais da view e do controller."""
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(self._delete_selected_items)

        self._transformation_controller.object_transformed.connect(self._handle_object_transformed)

    def _select_drawing_color(self):
        """Abre um diálogo de cores para selecionar a cor de desenho."""
        new_color = QColorDialog.getColor(self._current_draw_color, self, "Selecionar Cor de Desenho")
        if new_color.isValid():
            self._current_draw_color = new_color
            self.color_action.setIcon(self._create_color_icon(self._current_draw_color))

    def _on_mode_action_triggered(self) -> None:
        checked_action = self._mode_action_group.checkedAction()
        if checked_action: self._set_drawing_mode(checked_action.data())

    def _set_drawing_mode(self, mode: DrawingMode) -> None:
        if mode == self._drawing_mode: return
        self._finish_current_drawing(commit=False)
        self._drawing_mode = mode
        self._update_view_interaction()
        for action in self._mode_action_group.actions():
             if action.data() == mode:
                 action.setChecked(True)
                 break

    def _update_view_interaction(self) -> None:
        """Atualiza o cursor e o modo de arrasto baseado no modo de desenho."""
        if self._drawing_mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
            self._view.setCursor(Qt.ArrowCursor)
        elif self._drawing_mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
            self._view.setCursor(Qt.OpenHandCursor)
        else:
            self._view.set_drag_mode(QGraphicsView.NoDrag)
            self._view.setCursor(Qt.CrossCursor)

    def _remove_temp_items(self) -> None:
        """Remove itens temporários de pré-visualização da cena."""
        if self._temp_line_item and self._temp_line_item.scene():
            self._scene.removeItem(self._temp_line_item)
        self._temp_line_item = None

        if self._temp_polygon_path and self._temp_polygon_path.scene():
            self._scene.removeItem(self._temp_polygon_path)
        self._temp_polygon_path = None

    def _handle_scene_left_click(self, scene_pos: QPointF) -> None:
        """Trata cliques esquerdos na cena baseado no modo de desenho atual."""
        x, y = scene_pos.x(), scene_pos.y()
        current_point_data = Point(x, y, color=self._current_draw_color)

        if self._drawing_mode == DrawingMode.POINT:
            graphics_item = current_point_data.create_graphics_item()
            self._scene.addItem(graphics_item)

        elif self._drawing_mode == DrawingMode.LINE:
            if self._current_line_start is None:
                self._current_line_start = current_point_data
                self._update_line_preview(scene_pos)
            else:
                line_data = Line(self._current_line_start, current_point_data, color=self._current_draw_color)
                graphics_item = line_data.create_graphics_item()
                self._scene.addItem(graphics_item)
                self._current_line_start = None
                self._remove_temp_items()

        elif self._drawing_mode == DrawingMode.POLYGON:
            if not self._current_polygon_points:
                 reply = QMessageBox.question(
                    self, 'Tipo de Polígono',
                    'Deseja criar um polígono aberto (linha tracejada)?',
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                 )
                 self._current_polygon_is_open = (reply == QMessageBox.Yes)

            self._current_polygon_points.append(current_point_data)
            self._update_polygon_preview(scene_pos)

    def _handle_scene_right_click(self, scene_pos: QPointF) -> None:
        """Trata cliques direitos, primariamente para finalizar o desenho de polígonos."""
        if self._drawing_mode == DrawingMode.POLYGON:
            self._finish_current_drawing(commit=True)

    def _handle_scene_mouse_move(self, scene_pos: QPointF) -> None:
        """Trata movimento do mouse para pré-visualizações de desenho."""
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
             self._update_polygon_preview(scene_pos)

    def _update_line_preview(self, current_pos: QPointF):
        """Atualiza a pré-visualização temporária da linha."""
        if not self._current_line_start: return

        start_qpos = self._current_line_start.to_qpointf()
        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(start_qpos.x(), start_qpos.y(),
                                                    current_pos.x(), current_pos.y())
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(start_qpos.x(), start_qpos.y(),
                                         current_pos.x(), current_pos.y())

    def _update_polygon_preview(self, current_pos: QPointF):
         """Atualiza a pré-visualização temporária do caminho do polígono."""
         if not self._current_polygon_points: return

         path = QPainterPath()
         start_qpos = self._current_polygon_points[0].to_qpointf()
         path.moveTo(start_qpos)

         for point_data in self._current_polygon_points[1:]:
             path.lineTo(point_data.to_qpointf())

         path.lineTo(current_pos)

         if not self._current_polygon_is_open and len(self._current_polygon_points) >= 1:
              path.lineTo(start_qpos)

         if self._temp_polygon_path is None:
             self._temp_polygon_path = QGraphicsPathItem()
             self._temp_polygon_path.setPen(self._temp_item_pen)
             self._temp_polygon_path.setZValue(1000)
             self._scene.addItem(self._temp_polygon_path)

         self._temp_polygon_path.setPath(path)

    def _finish_current_drawing(self, commit: bool = True) -> None:
        """Finaliza ou cancela a operação de desenho atual."""
        drawing_finished = False
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
             self._current_line_start = None
             drawing_finished = True

        if self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            if commit and len(self._current_polygon_points) >= 3:
                polygon_data = Polygon(
                    self._current_polygon_points.copy(),
                    self._current_polygon_is_open,
                    color=self._current_draw_color
                )
                graphics_item = polygon_data.create_graphics_item()
                self._scene.addItem(graphics_item)
            self._current_polygon_points = []
            self._current_polygon_is_open = False
            drawing_finished = True

        if drawing_finished:
            self._remove_temp_items()

    def _delete_selected_items(self) -> None:
        """Exclui todos os itens atualmente selecionados da cena."""
        selected = self._scene.selectedItems()
        if not selected: return

        reply = QMessageBox.question(self, "Confirmar Exclusão",
                                     f"Tem certeza que deseja excluir {len(selected)} item(ns) selecionado(s)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            for item in selected:
                if item.scene():
                    self._scene.removeItem(item)

    def _open_coordinate_input_dialog(self) -> None:
        """Abre um diálogo para adicionar formas via entrada manual de coordenadas."""
        dialog_mode = 'point'
        active_mode = self._drawing_mode

        if active_mode == DrawingMode.LINE: dialog_mode = 'line'
        elif active_mode == DrawingMode.POLYGON: dialog_mode = 'polygon'
        elif active_mode in [DrawingMode.SELECT, DrawingMode.PAN]:
            items = ("Ponto", "Linha", "Polígono")
            item, ok = QInputDialog.getItem(self, "Selecionar Forma",
                                             "Qual forma deseja adicionar manualmente?", items, 0, False)
            if ok and item:
                 mode_map = {"Ponto": 'point', "Linha": 'line', "Polígono": 'polygon'}
                 dialog_mode = mode_map.get(item, 'point')
            else:
                return

        self._finish_current_drawing(commit=False)

        dialog = CoordinateInputDialog(self, mode=dialog_mode)
        dialog.set_initial_color(self._current_draw_color)

        if dialog.exec_() == QDialog.Accepted:
            result_data = dialog.get_coordinates()
            if result_data:
                try:
                    if dialog_mode == 'polygon':
                        coords, is_open, color = result_data
                    elif dialog_mode in ['point', 'line']:
                         coords, color = result_data
                         is_open = False
                    else:
                        raise ValueError(f"Modo de diálogo inesperado: {dialog_mode}")

                    if not color or not color.isValid():
                        color = QColor(Qt.black)

                    self._add_item_from_coordinates(coords, is_open=is_open, color=color, dialog_mode_str=dialog_mode)

                except (ValueError, TypeError, IndexError) as e:
                     QMessageBox.warning(self, "Erro ao Processar Coordenadas", f"Dados do diálogo inválidos ou insuficientes: {e}")


    def _add_item_from_coordinates(self, coords: List[Tuple[float, float]],
                                 is_open: bool = False,
                                 color: QColor = QColor(Qt.black),
                                 dialog_mode_str: str = 'point') -> None:
        """Adiciona um item gráfico baseado nos dados de coordenadas e cor."""
        try:
            if dialog_mode_str == 'point':
                if not coords: raise ValueError("Coordenadas do ponto ausentes.")
                point_data = Point(coords[0][0], coords[0][1], color=color)
                self._scene.addItem(point_data.create_graphics_item())

            elif dialog_mode_str == 'line':
                if len(coords) < 2: raise ValueError("Coordenadas da linha insuficientes (requer 2 pontos).")
                start_point_data = Point(coords[0][0], coords[0][1], color=color)
                end_point_data = Point(coords[1][0], coords[1][1], color=color)
                line_data = Line(start_point_data, end_point_data, color=color)
                self._scene.addItem(line_data.create_graphics_item())

            elif dialog_mode_str == 'polygon':
                if len(coords) < 3: raise ValueError("Coordenadas do polígono insuficientes (requer 3 pontos).")
                polygon_points_data = [Point(x, y, color=color) for x, y in coords]
                polygon_data = Polygon(polygon_points_data, is_open, color=color)
                self._scene.addItem(polygon_data.create_graphics_item())

            else:
                raise ValueError(f"Modo de criação desconhecido: {dialog_mode_str}")

        except (IndexError, ValueError, TypeError) as e:
             QMessageBox.warning(self, "Erro ao Adicionar Item", f"Não foi possível criar o item a partir das coordenadas: {e}")

    def _open_transformation_dialog(self) -> None:
        """Inicia o processo de transformação para o objeto selecionado."""
        selected_items = self._scene.selectedItems()

        if len(selected_items) != 1:
            QMessageBox.warning(self, "Seleção Inválida",
                                "Por favor, selecione exatamente um objeto para transformar.")
            return

        graphics_item = selected_items[0]
        data_object = graphics_item.data(0)

        if data_object is None:
            QMessageBox.critical(self, "Erro Interno",
                                 "Não foi possível encontrar os dados associados ao objeto selecionado.")
            return

        self._transformation_controller.request_transformation(data_object)


    def _handle_object_transformed(self, data_object: object) -> None:
        """
        Slot chamado pelo TransformationController após o objeto de dados ser modificado.
        Atualiza o QGraphicsItem correspondente na cena.
        """
        graphics_item = self._find_graphics_item_for_object(data_object)

        if not graphics_item:
            print(f"Aviso: Não foi possível encontrar o item gráfico para o objeto de dados atualizado: {data_object}")
            return

        try:
            needs_update = False

            if isinstance(data_object, Point) and isinstance(graphics_item, QGraphicsEllipseItem):
                size = 6.0; offset = size / 2.0
                new_rect = QRectF(data_object.x - offset, data_object.y - offset, size, size)
                if graphics_item.rect() != new_rect:
                    graphics_item.setRect(new_rect)
                    needs_update = True


            elif isinstance(data_object, Line) and isinstance(graphics_item, QGraphicsLineItem):
                new_line = QLineF(data_object.start.to_qpointf(), data_object.end.to_qpointf())
                if graphics_item.line() != new_line:
                    graphics_item.setLine(new_line)
                    needs_update = True


            elif isinstance(data_object, Polygon) and isinstance(graphics_item, QGraphicsPolygonItem):
                new_polygon_qf = QPolygonF()
                for point_data in data_object.points:
                    new_polygon_qf.append(point_data.to_qpointf())

                if graphics_item.polygon() != new_polygon_qf:
                    graphics_item.setPolygon(new_polygon_qf)
                    needs_update = True

            else:
                print(f"Aviso: Tipos incompatíveis de objeto de dados e item gráfico durante a atualização: {type(data_object)}, {type(graphics_item)}")

            if needs_update:
                graphics_item.update()

        except Exception as e:
             QMessageBox.critical(self, "Erro ao Atualizar Gráfico", f"Falha ao atualizar item gráfico após transformação: {e}")


    def _find_graphics_item_for_object(self, data_obj: object) -> Optional[QGraphicsItem]:
        """Encontra o QGraphicsItem associado ao objeto de dados fornecido usando setData."""
        if data_obj is None: return None
        for item in self._scene.items():
            item_data = item.data(0)
            if item_data is data_obj:
                return item
        return None

    def closeEvent(self, event: 'QCloseEvent') -> None:
        """Trata o evento de fechamento da janela principal, garantindo a limpeza."""
        self._finish_current_drawing(commit=False)
        super().closeEvent(event)

def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    editor = GraphicsEditor()
    sys.exit(app.exec_())

if __name__ == "__main__":
    import os
    icon_dir = "icons"
    os.makedirs(icon_dir, exist_ok=True)
    dummy_icons = ["select.png", "pan.png", "point.png", "line.png", "polygon.png", "coords.png", "transform.png", "add.png"] # Added add.png
    for icon_name in dummy_icons:
        icon_path = os.path.join(icon_dir, icon_name)
        if not os.path.exists(icon_path):
             try:
                  from PIL import Image
                  img = Image.new('RGBA', (24, 24), (0,0,0,0))
                  img.save(icon_path)
             except ImportError:
                  print(f"Pillow não instalado, não é possível criar ícone dummy: {icon_path}")
                  with open(icon_path, 'w') as f: pass

    main()