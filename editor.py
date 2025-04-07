# editor.py
import sys
import os
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Union

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QGraphicsScene,
    QToolBar,
    QAction,
    QActionGroup,
    QDialog,
    QMessageBox,
    QGraphicsView,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QInputDialog,
    QGraphicsEllipseItem,
    QGraphicsPolygonItem,
    QColorDialog,
    QPushButton,
    QGraphicsItem,
    QFileDialog,
    QMenu,
    QMenuBar,
    QLabel,
    QStatusBar,
)  # Added QLabel, QStatusBar
from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QSize, QLineF, QRectF
from PyQt5.QtGui import (
    QPainterPath,
    QPen,
    QColor,
    QPolygonF,
    QIcon,
    QPixmap,
    QCloseEvent,
    QBrush,
)

from view import GraphicsView
from models.point import Point
from models.line import Line
from models.polygon import Polygon
from models.coordinates_input import CoordinateInputDialog
from controllers.transformation_controller import TransformationController
from io_handler import IOHandler
from object_manager import ObjectManager

DataObject = Union[Point, Line, Polygon]


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
        self.setWindowTitle("Editor Gráfico (Rotação da Window)")  # Updated title
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
        self._view = GraphicsView(
            self._scene, self
        )  # GraphicsView now handles rotation
        self.setCentralWidget(self._view)

        # --- Controller e Handlers ---
        self._transformation_controller = TransformationController(self)
        self._io_handler = IOHandler(self)
        self._object_manager = ObjectManager()

        # --- Configuração ---
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()  # Add status bar
        self._connect_signals()
        self._update_view_interaction()  # Call initial update
        self.show()
        self._update_status_bar()  # Update status bar initially

    # --- UI Setup Methods (_setup_menu_bar, _setup_toolbar - mostly ) ---
    def _setup_menu_bar(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&Arquivo")
        clear_action = QAction(QIcon("icons/clear.png"), "&Limpar Cena", self)
        clear_action.setToolTip("Limpar todos os objetos da cena")
        clear_action.triggered.connect(self._clear_scene)
        file_menu.addAction(clear_action)
        file_menu.addSeparator()
        load_obj_action = QAction(QIcon("icons/open.png"), "Carregar &OBJ...", self)
        load_obj_action.setToolTip("Carregar geometria de um arquivo Wavefront OBJ")
        load_obj_action.triggered.connect(self._prompt_load_obj)
        file_menu.addAction(load_obj_action)
        save_obj_action = QAction(QIcon("icons/save.png"), "&Salvar como OBJ...", self)
        save_obj_action.setToolTip("Salvar a cena atual em um arquivo Wavefront OBJ")
        save_obj_action.triggered.connect(self._prompt_save_obj)
        file_menu.addAction(save_obj_action)
        file_menu.addSeparator()
        exit_action = QAction(QIcon("icons/exit.png"), "&Sair", self)
        exit_action.setToolTip("Fechar a aplicação")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        # Add View Menu (Optional but good place for Reset View)
        view_menu = menubar.addMenu("&Vista")
        reset_view_action = QAction("Resetar Vista", self)
        reset_view_action.setToolTip("Resetar zoom, pan e rotação da vista")
        reset_view_action.triggered.connect(self._reset_view)
        view_menu.addAction(reset_view_action)

    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        self._mode_action_group = QActionGroup(self)
        self._mode_action_group.setExclusive(True)
        modes = [
            (
                "Selecionar",
                DrawingMode.SELECT,
                "Selecionar itens (Padrão)",
                "icons/select.png",
            ),
            (
                "Mover Vista",
                DrawingMode.PAN,
                "Mover a vista (Ferramenta Mão)",
                "icons/pan.png",
            ),
            ("Ponto", DrawingMode.POINT, "Desenhar um ponto único", "icons/point.png"),
            (
                "Linha",
                DrawingMode.LINE,
                "Desenhar uma linha (2 cliques)",
                "icons/line.png",
            ),
            (
                "Polígono",
                DrawingMode.POLYGON,
                "Desenhar um polígono (múltiplos cliques, botão direito para finalizar)",
                "icons/polygon.png",
            ),
        ]
        for name, mode, tip, icon_path in modes:
            action = QAction(QIcon(icon_path), name, self)
            action.setToolTip(tip)
            action.setCheckable(True)
            action.setData(mode)
            action.triggered.connect(self._on_mode_action_triggered)
            toolbar.addAction(action)
            self._mode_action_group.addAction(action)
            if mode == self._drawing_mode:
                action.setChecked(True)
        toolbar.addSeparator()
        self.color_action = QAction(
            self._create_color_icon(self._current_draw_color), "Cor Desenho", self
        )
        self.color_action.setToolTip("Selecionar cor para novos objetos")
        self.color_action.triggered.connect(self._select_drawing_color)
        toolbar.addAction(self.color_action)
        toolbar.addSeparator()
        manual_coord_action = QAction(
            QIcon("icons/coords.png"), "Coordenadas Manuais", self
        )
        manual_coord_action.setToolTip("Adicionar forma via diálogo de coordenadas")
        manual_coord_action.triggered.connect(self._open_coordinate_input_dialog)
        toolbar.addAction(manual_coord_action)
        toolbar.addSeparator()
        transform_action = QAction(
            QIcon("icons/transform.png"), "Transformar Objeto", self
        )
        transform_action.setToolTip(
            "Aplicar translação, escala ou rotação ao objeto selecionado"
        )
        transform_action.triggered.connect(self._open_transformation_dialog)
        toolbar.addAction(transform_action)

    def _setup_status_bar(self) -> None:
        """Configura a barra de status para mostrar informações."""
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)
        # Rótulo para o modo atual
        self._status_mode_label = QLabel("Modo: Selecionar")
        self._status_bar.addPermanentWidget(self._status_mode_label)
        # Rótulo para a rotação da window
        self._status_rotation_label = QLabel("Rotação View: 0.0°")
        self._status_bar.addPermanentWidget(self._status_rotation_label)
        # Rótulo para coordenadas do mouse (opcional)
        # self._status_coords_label = QLabel("Mouse: (0, 0)")
        # self._status_bar.addWidget(self._status_coords_label) # addWidget para temporário

    def _update_status_bar(self) -> None:
        """Atualiza as informações na barra de status."""
        mode_text = f"Modo: {self._drawing_mode.name.capitalize()}"
        self._status_mode_label.setText(mode_text)

        rotation_angle = self._view.get_rotation_angle()  # Pega o ângulo da view
        rotation_text = f"Rotação View: {rotation_angle:.1f}°"
        self._status_rotation_label.setText(rotation_text)

        # Atualizar coordenadas do mouse se o rótulo existir
        # scene_pos = self._view.mapToScene(self._view.mapFromGlobal(QCursor.pos())) # Exemplo
        # coords_text = f"Mouse: ({scene_pos.x():.1f}, {scene_pos.y():.1f})"
        # if hasattr(self, '_status_coords_label'): self._status_coords_label.setText(coords_text)

    # --- Signal Connections ---
    def _connect_signals(self) -> None:
        """Conecta sinais da view, controller e UI."""
        # Sinais da View para o Editor
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(
            self._handle_scene_mouse_move
        )  # Para preview e coords
        self._view.delete_requested.connect(self._delete_selected_items)
        # Conecta o sinal de rotação da view à atualização da status bar
        self._view.rotation_changed.connect(self._update_status_bar)

        # Sinais do Controller para o Editor
        self._transformation_controller.object_transformed.connect(
            self._handle_object_transformed
        )

        # Conectar movimento do mouse na view para atualizar coordenadas na status bar (opcional)
        # self._view.scene_mouse_moved.connect(self._update_mouse_coords_status)

    # --- Core Logic Methods (_create_color_icon, _select_drawing_color, etc. - ) ---
    def _create_color_icon(self, color: QColor, size: int = 16) -> QIcon:
        pixmap = QPixmap(size, size)
        pixmap.fill(color)
        return QIcon(pixmap)

    def _select_drawing_color(self):
        new_color = QColorDialog.getColor(
            self._current_draw_color, self, "Selecionar Cor de Desenho"
        )
        if new_color.isValid():
            self._current_draw_color = new_color
            self.color_action.setIcon(self._create_color_icon(self._current_draw_color))

    def _on_mode_action_triggered(self) -> None:
        checked_action = self._mode_action_group.checkedAction()
        if checked_action:
            self._set_drawing_mode(checked_action.data())

    def _set_drawing_mode(self, mode: DrawingMode) -> None:
        if mode == self._drawing_mode:
            return
        self._finish_current_drawing(commit=False)
        self._drawing_mode = mode
        self._update_view_interaction()  # Atualiza a view (cursor, drag mode)
        self._update_status_bar()  # Atualiza a status bar
        # Atualiza qual botão da toolbar está checado
        for action in self._mode_action_group.actions():
            if action.data() == mode:
                action.setChecked(True)
                break

    def _update_view_interaction(self) -> None:
        """Atualiza o cursor e o modo de arrasto da view baseado no modo de desenho."""
        # Delega a definição do modo de arrasto para a view
        if self._drawing_mode == DrawingMode.SELECT:
            self._view.setDragMode(QGraphicsView.RubberBandDrag)
            self._view.setCursor(Qt.ArrowCursor)  # Cursor padrão para seleção
        elif self._drawing_mode == DrawingMode.PAN:
            self._view.setDragMode(QGraphicsView.ScrollHandDrag)
            # A view já define o cursor OpenHand/ClosedHand internamente
        else:  # Drawing modes (POINT, LINE, POLYGON)
            self._view.setDragMode(QGraphicsView.NoDrag)
            self._view.setCursor(Qt.CrossCursor)  # Cursor de desenho

    def _remove_temp_items(self) -> None:
        if self._temp_line_item and self._temp_line_item.scene():
            self._scene.removeItem(self._temp_line_item)
            self._temp_line_item = None
        if self._temp_polygon_path and self._temp_polygon_path.scene():
            self._scene.removeItem(self._temp_polygon_path)
            self._temp_polygon_path = None

    # --- Drawing Handlers (_handle_scene_left_click, etc. - ) ---
    # A LÓGICA AQUI NÃO MUDA, pois as coordenadas recebidas de scene_pos
    # já são coordenadas de MUNDO corretas, independentemente da rotação da view.
    def _handle_scene_left_click(self, scene_pos: QPointF) -> None:
        x, y = scene_pos.x(), scene_pos.y()
        current_point_data = Point(x, y, color=self._current_draw_color)
        if self._drawing_mode == DrawingMode.POINT:
            self._scene.addItem(current_point_data.create_graphics_item())
        elif self._drawing_mode == DrawingMode.LINE:
            if self._current_line_start is None:
                self._current_line_start = current_point_data
                self._update_line_preview(scene_pos)
            else:
                line_data = Line(
                    self._current_line_start,
                    current_point_data,
                    color=self._current_draw_color,
                )
                self._scene.addItem(line_data.create_graphics_item())
                self._current_line_start = None
                self._remove_temp_items()
        elif self._drawing_mode == DrawingMode.POLYGON:
            if not self._current_polygon_points:
                reply = QMessageBox.question(
                    self,
                    "Tipo de Polígono",
                    "Deseja criar um polígono aberto (linha tracejada)?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                self._current_polygon_is_open = reply == QMessageBox.Yes
            self._current_polygon_points.append(current_point_data)
            self._update_polygon_preview(scene_pos)

    def _handle_scene_right_click(self, scene_pos: QPointF) -> None:
        if self._drawing_mode == DrawingMode.POLYGON:
            self._finish_current_drawing(commit=True)

    def _handle_scene_mouse_move(self, scene_pos: QPointF) -> None:
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            self._update_polygon_preview(scene_pos)
        # Atualizar coordenadas na status bar (se implementado)
        # self._update_mouse_coords_status(scene_pos)

    # def _update_mouse_coords_status(self, scene_pos: QPointF):
    #      """Atualiza o rótulo de coordenadas do mouse na barra de status."""
    #      coords_text = f"Mouse: ({scene_pos.x():.1f}, {scene_pos.y():.1f})"
    #      if hasattr(self, '_status_coords_label'): self._status_coords_label.setText(coords_text)

    def _update_line_preview(self, current_pos: QPointF):
        if not self._current_line_start:
            return
        start_qpos = self._current_line_start.to_qpointf()
        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(
                start_qpos.x(), start_qpos.y(), current_pos.x(), current_pos.y()
            )
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(
                start_qpos.x(), start_qpos.y(), current_pos.x(), current_pos.y()
            )

    def _update_polygon_preview(self, current_pos: QPointF):
        if not self._current_polygon_points:
            return
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
        drawing_finished = False
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            self._current_line_start = None
            drawing_finished = True
        if self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            min_points_needed = 2 if self._current_polygon_is_open else 3
            if commit and len(self._current_polygon_points) >= min_points_needed:
                polygon_data = Polygon(
                    self._current_polygon_points.copy(),
                    self._current_polygon_is_open,
                    color=self._current_draw_color,
                )
                self._scene.addItem(polygon_data.create_graphics_item())
            self._current_polygon_points = []
            self._current_polygon_is_open = False
            drawing_finished = True
        if drawing_finished:
            self._remove_temp_items()

    # --- Scene/Object Management (_delete_selected_items, _clear_scene - ) ---
    def _delete_selected_items(self) -> None:
        selected = self._scene.selectedItems()
        if not selected:
            return
        reply = QMessageBox.question(
            self,
            "Confirmar Exclusão",
            f"Tem certeza que deseja excluir {len(selected)} item(ns) selecionado(s)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            [self._scene.removeItem(item) for item in selected if item.scene()]
            self._scene.update()

    def _clear_scene(self) -> None:
        reply = QMessageBox.question(
            self,
            "Confirmar Limpeza",
            "Tem certeza que deseja limpar toda a cena? Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._finish_current_drawing(commit=False)
            self._scene.clear()
            self._scene.update()
        self._reset_view()  # Também reseta a vista ao limpar

    def _reset_view(self) -> None:
        """Reseta a transformação da view (zoom, pan, rotação)."""
        if hasattr(self._view, "reset_view"):
            self._view.reset_view()
        else:  # Fallback simples se reset_view não existir
            self._view.setTransform(QTransform())  # Reseta matrix
            self._view.centerOn(0, 0)
        self._update_status_bar()

    # --- Coordinate Input / Object Transformation ( logic) ---
    def _open_coordinate_input_dialog(self) -> None:
        dialog_mode = "point"
        active_mode = self._drawing_mode
        if active_mode == DrawingMode.LINE:
            dialog_mode = "line"
        elif active_mode == DrawingMode.POLYGON:
            dialog_mode = "polygon"
        elif active_mode in [DrawingMode.SELECT, DrawingMode.PAN]:
            items = ("Ponto", "Linha", "Polígono")
            item, ok = QInputDialog.getItem(
                self,
                "Selecionar Forma",
                "Qual forma deseja adicionar manualmente?",
                items,
                0,
                False,
            )
            if ok and item:
                mode_map = {"Ponto": "point", "Linha": "line", "Polígono": "polygon"}
                dialog_mode = mode_map.get(item, "point")
            else:
                return
        self._finish_current_drawing(commit=False)
        dialog = CoordinateInputDialog(self, mode=dialog_mode)
        dialog.set_initial_color(self._current_draw_color)
        if dialog.exec_() == QDialog.Accepted:
            result_data = dialog.get_coordinates()
            if result_data:
                try:
                    if dialog_mode == "polygon":
                        coords, is_open, color = result_data
                    elif dialog_mode in ["point", "line"]:
                        coords, color = result_data
                        is_open = False
                    else:
                        raise ValueError(f"Modo de diálogo inesperado: {dialog_mode}")
                    if not color or not color.isValid():
                        color = QColor(Qt.black)
                    self._add_item_from_coordinates(
                        coords,
                        is_open=is_open,
                        color=color,
                        dialog_mode_str=dialog_mode,
                    )
                except (ValueError, TypeError, IndexError) as e:
                    QMessageBox.warning(
                        self,
                        "Erro ao Processar Coordenadas",
                        f"Dados do diálogo inválidos ou insuficientes: {e}",
                    )

    def _add_item_from_coordinates(
        self,
        coords: List[Tuple[float, float]],
        is_open: bool = False,
        color: QColor = QColor(Qt.black),
        dialog_mode_str: str = "point",
    ) -> None:
        try:
            if dialog_mode_str == "point":
                if not coords:
                    raise ValueError("Coordenadas do ponto ausentes.")
                    point_data = Point(coords[0][0], coords[0][1], color=color)
                    self._scene.addItem(point_data.create_graphics_item())
            elif dialog_mode_str == "line":
                if len(coords) < 2:
                    raise ValueError("Coordenadas da linha insuficientes.")
                    start_point_data = Point(coords[0][0], coords[0][1], color=color)
                    end_point_data = Point(coords[1][0], coords[1][1], color=color)
                    line_data = Line(start_point_data, end_point_data, color=color)
                    self._scene.addItem(line_data.create_graphics_item())
            elif dialog_mode_str == "polygon":
                min_points = 2 if is_open else 3
                if len(coords) < min_points:
                    raise ValueError(
                        f"Coordenadas do polígono insuficientes ({min_points})."
                    )
                    polygon_points_data = [Point(x, y, color=color) for x, y in coords]
                    polygon_data = Polygon(polygon_points_data, is_open, color=color)
                    self._scene.addItem(polygon_data.create_graphics_item())
            else:
                raise ValueError(f"Modo de criação desconhecido: {dialog_mode_str}")
        except (IndexError, ValueError, TypeError) as e:
            QMessageBox.warning(
                self, "Erro ao Adicionar Item", f"Não foi possível criar o item: {e}"
            )

    def _open_transformation_dialog(self) -> None:
        selected_items = self._scene.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(
                self, "Seleção Inválida", "Selecione UM objeto para transformar."
            )
            return
        graphics_item = selected_items[0]
        data_object = graphics_item.data(0)
        if data_object is None:
            QMessageBox.critical(
                self, "Erro Interno", "Dados do objeto não encontrados."
            )
            return
        self._transformation_controller.request_transformation(data_object)

    # --- UPDATED _handle_object_transformed to ensure style consistency ---
    def _handle_object_transformed(self, data_object: DataObject) -> None:
        graphics_item = self._find_graphics_item_for_object(data_object)
        if not graphics_item:
            print(f"Aviso: Item gráfico não encontrado para {data_object}")
            return
        try:
            needs_update = False
            # Update geometry and style based on transformed data_object
            if isinstance(data_object, Point) and isinstance(
                graphics_item, QGraphicsEllipseItem
            ):
                size = 6.0
                offset = size / 2.0
                new_rect = QRectF(
                    data_object.x - offset, data_object.y - offset, size, size
                )
                new_pen = QPen(data_object.color, 1)
                new_brush = QBrush(data_object.color)
                if graphics_item.rect() != new_rect:
                    graphics_item.setRect(new_rect)
                    needs_update = True
                if graphics_item.pen() != new_pen or graphics_item.brush() != new_brush:
                    graphics_item.setPen(new_pen)
                    graphics_item.setBrush(new_brush)
                    needs_update = True
            elif isinstance(data_object, Line) and isinstance(
                graphics_item, QGraphicsLineItem
            ):
                new_line = QLineF(
                    data_object.start.to_qpointf(), data_object.end.to_qpointf()
                )
                new_pen = QPen(data_object.color, 2)
                if graphics_item.line() != new_line:
                    graphics_item.setLine(new_line)
                    needs_update = True
                if graphics_item.pen() != new_pen:
                    graphics_item.setPen(new_pen)
                    needs_update = True
            elif isinstance(data_object, Polygon) and isinstance(
                graphics_item, QGraphicsPolygonItem
            ):
                new_polygon_qf = QPolygonF()
                [new_polygon_qf.append(p.to_qpointf()) for p in data_object.points]
                new_pen = QPen(data_object.color, 2)
                new_brush = QBrush()
                if data_object.is_open:
                    new_pen.setStyle(Qt.DashLine)
                    new_brush.setStyle(Qt.NoBrush)
                else:
                    new_pen.setStyle(Qt.SolidLine)
                    new_brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(data_object.color)
                    fill_color.setAlphaF(0.35)
                    new_brush.setColor(fill_color)
                if graphics_item.polygon() != new_polygon_qf:
                    graphics_item.setPolygon(new_polygon_qf)
                    needs_update = True
                if graphics_item.pen() != new_pen or graphics_item.brush() != new_brush:
                    graphics_item.setPen(new_pen)
                    graphics_item.setBrush(new_brush)
                    needs_update = True
            else:
                print(
                    f"Aviso: Tipos incompatíveis: {type(data_object)}, {type(graphics_item)}"
                )
            if needs_update:
                graphics_item.update()
                self._scene.update()
        except Exception as e:
            QMessageBox.critical(
                self, "Erro ao Atualizar Gráfico", f"Falha ao atualizar item: {e}"
            )

    def _find_graphics_item_for_object(
        self, data_obj: DataObject
    ) -> Optional[QGraphicsItem]:
        if data_obj is None:
            return None
        for item in self._scene.items():
            if item.data(0) is data_obj:
                return item
        return None

    # --- OBJ Import/Export Methods (, use IOHandler/ObjectManager) ---
    def _prompt_load_obj(self) -> None:
        obj_filepath = self._io_handler.prompt_load_obj()
        if not obj_filepath:
            return
        reply = QMessageBox.question(
            self,
            "Confirmar",
            "Limpar cena atual e carregar arquivo?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.No:
            return
        read_result = self._io_handler.read_obj_lines(obj_filepath)
        if read_result is None:
            return
        obj_lines, mtl_filename_relative = read_result
        material_colors: Dict[str, QColor] = {}
        mtl_warnings: List[str] = []
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            mtl_filepath = os.path.normpath(
                os.path.join(obj_dir, mtl_filename_relative)
            )
            if os.path.exists(mtl_filepath):
                material_colors, mtl_warnings = self._io_handler.read_mtl_file(
                    mtl_filepath
                )
            else:
                mtl_warnings.append(
                    f"Arquivo MTL '{mtl_filename_relative}' não encontrado."
                )
        parsed_objects, obj_warnings = self._object_manager.parse_obj_data(
            obj_lines, material_colors, self._current_draw_color
        )
        all_warnings = mtl_warnings + obj_warnings
        self._finish_current_drawing(commit=False)
        self._scene.clear()
        if not parsed_objects and not all_warnings:
            QMessageBox.information(
                self,
                "Info",
                f"Nenhum objeto válido encontrado em '{os.path.basename(obj_filepath)}'.",
            )
            return
        creation_errors = []
        for data_obj in parsed_objects:
            try:
                graphics_item = (
                    data_obj.create_graphics_item()
                )  # Should use data_obj.color
                # Ensure style consistency after creation (might be redundant)
                if isinstance(graphics_item, QGraphicsEllipseItem):
                    graphics_item.setPen(QPen(data_obj.color, 1))
                    graphics_item.setBrush(QBrush(data_obj.color))
                elif isinstance(graphics_item, QGraphicsLineItem):
                    graphics_item.setPen(QPen(data_obj.color, 2))
                elif isinstance(graphics_item, QGraphicsPolygonItem):
                    pen = QPen(data_obj.color, 2)
                    brush = QBrush()
                    if data_obj.is_open:
                        pen.setStyle(Qt.DashLine)
                        brush.setStyle(Qt.NoBrush)
                    else:
                        pen.setStyle(Qt.SolidLine)
                        brush.setStyle(Qt.SolidPattern)
                        fill_color = QColor(data_obj.color)
                        fill_color.setAlphaF(0.35)
                        brush.setColor(fill_color)
                    graphics_item.setPen(pen)
                    graphics_item.setBrush(brush)
                self._scene.addItem(graphics_item)
            except Exception as e:
                creation_errors.append(f"Erro criando {type(data_obj).__name__}: {e}")
        self._scene.update()
        all_warnings.extend(creation_errors)
        if all_warnings:
            formatted_warnings = "- " + "\n- ".join(all_warnings)
            QMessageBox.warning(
                self,
                "Carregado com Avisos",
                f"Arquivo '{os.path.basename(obj_filepath)}' carregado.\n\nAvisos:\n{formatted_warnings}",
            )
        else:
            QMessageBox.information(
                self,
                "Sucesso",
                f"Arquivo OBJ '{os.path.basename(obj_filepath)}' carregado.",
            )
        self._reset_view()  # Reset view after loading

    def _prompt_save_obj(self) -> None:
        scene_data_objects: List[DataObject] = [
            item.data(0)
            for item in self._scene.items()
            if isinstance(item.data(0), (Point, Line, Polygon))
        ]
        if not scene_data_objects:
            QMessageBox.information(self, "Nada para Salvar", "A cena está vazia.")
            return
        base_filepath = self._io_handler.prompt_save_obj("scene.obj")
        if not base_filepath:
            return
        mtl_filename = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, warnings_gen = self._object_manager.generate_obj_data(
            scene_data_objects, mtl_filename
        )
        if obj_lines is None:
            msg = "Falha ao gerar dados OBJ."
            formatted_warnings = ""
            if warnings_gen:
                formatted_warnings = "\n\nAvisos:\n- " + "\n- ".join(warnings_gen)
                msg += formatted_warnings
            QMessageBox.warning(self, "Erro Geração OBJ", msg)
            return
        success = self._io_handler.write_obj_and_mtl(
            base_filepath, obj_lines, mtl_lines or []
        )
        if success:
            obj_filename_saved = os.path.basename(base_filepath + ".obj")
            msg = f"Cena salva como '{obj_filename_saved}'"
            formatted_warnings = ""
            if mtl_lines:
                msg += f" e '{mtl_filename}'"
                msg += "."
            if warnings_gen:
                formatted_warnings = "\n\nAvisos:\n- " + "\n- ".join(warnings_gen)
                QMessageBox.warning(
                    self, "Salvo com Avisos", f"{msg}{formatted_warnings}"
                )
            else:
                QMessageBox.information(self, "Sucesso", msg)

    # --- Close Event () ---
    def closeEvent(self, event: QCloseEvent) -> None:
        self._finish_current_drawing(commit=False)
        super().closeEvent(event)


# --- Main Function () ---
def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    editor = GraphicsEditor()
    sys.exit(app.exec_())


# --- Dummy Icon Creation () ---
if __name__ == "__main__":
    import os

    icon_dir = "icons"
    os.makedirs(icon_dir, exist_ok=True)
    dummy_icons = [
        "select.png",
        "pan.png",
        "point.png",
        "line.png",
        "polygon.png",
        "coords.png",
        "transform.png",
        "add.png",
        "clear.png",
        "open.png",
        "save.png",
        "exit.png",
    ]
    for icon_name in dummy_icons:
        icon_path = os.path.join(icon_dir, icon_name)
        if not os.path.exists(icon_path):
            try:
                from PIL import Image, ImageDraw

                img = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
                draw = ImageDraw.Draw(img)
                draw.rectangle([(2, 2), (21, 21)], outline="gray", width=1)
                draw.text((4, 4), icon_name[:2], fill="black")
                img.save(icon_path)
                print(f"Criado ícone dummy: {icon_path}")
            except ImportError:
                print(
                    f"Pillow não instalado, não é possível criar ícone dummy: {icon_path}"
                )
                open(icon_path, "w").close()
            except Exception as e:
                print(f"Erro ao criar ícone dummy {icon_path}: {e}")
                open(icon_path, "w").close()
    main()
