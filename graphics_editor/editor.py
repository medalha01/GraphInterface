# graphics_editor/editor.py
import sys
import os
import numpy as np
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Union, Any

from PyQt5.QtWidgets import (
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
    QLabel,
    QStatusBar,
    QSlider,
    QApplication,
    QSizePolicy,
)
from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QSize, QLineF, QRectF, QTimer, QLocale
from PyQt5.QtGui import (
    QPainterPath,
    QPen,
    QColor,
    QPolygonF,
    QIcon,
    QPixmap,
    QCloseEvent,
    QBrush,
    QTransform,
    QPainter,
)

# Importações relativas dentro do pacote
from .view import GraphicsView
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon
from .dialogs.coordinates_input import CoordinateInputDialog
from .dialogs.transformation_dialog import TransformationDialog
from .controllers.transformation_controller import TransformationController
from .io_handler import IOHandler
from .object_manager import ObjectManager

# Alias para tipos de dados dos modelos
DataObject = Union[Point, Line, Polygon]


class DrawingMode(Enum):
    """Modos de interação disponíveis no editor."""

    POINT = auto()
    LINE = auto()
    POLYGON = auto()
    SELECT = auto()
    PAN = auto()


class GraphicsEditor(QMainWindow):
    """Janela principal da aplicação para o editor gráfico 2D."""

    # Constantes para o slider de zoom
    SLIDER_RANGE_MIN = 0
    SLIDER_RANGE_MAX = 400

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Gráfico 2D")  # Título inicial
        self.resize(1000, 750)

        # Caminho base para ícones (relativo à localização deste arquivo)
        self._icon_base_path = os.path.join(os.path.dirname(__file__), "icons")

        # --- Estado Interno ---
        self._drawing_mode: DrawingMode = DrawingMode.SELECT
        self._current_line_start: Optional[Point] = None
        self._current_polygon_points: List[Point] = []
        self._current_polygon_is_open: bool = False
        self._current_draw_color: QColor = QColor(Qt.black)
        self._unsaved_changes: bool = False
        self._current_filepath: Optional[str] = None  # Caminho do arquivo .obj atual

        # --- Itens Gráficos Temporários (Pré-visualização) ---
        self._temp_line_item: Optional[QGraphicsLineItem] = None
        self._temp_polygon_path: Optional[QGraphicsPathItem] = None
        self._temp_item_pen = QPen(Qt.gray, 1, Qt.DashLine)

        # --- Componentes Principais ---
        self._scene = QGraphicsScene(self)
        # Define uma área grande para a cena, permitindo desenho fora da vista inicial
        self._scene.setSceneRect(-10000, -10000, 20000, 20000)
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

        # --- Controladores e Gerenciadores ---
        self._transformation_controller = TransformationController(self)
        self._io_handler = IOHandler(self)
        self._object_manager = ObjectManager()

        # --- Configuração da UI ---
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._connect_signals()
        self._update_view_interaction()
        self._update_status_bar()
        # Atualiza controles da view (zoom/rotação) após a inicialização da UI
        QTimer.singleShot(0, self._update_view_controls)
        self._update_window_title()

    def _get_icon(self, name: str) -> QIcon:
        """Carrega um QIcon do diretório de ícones ou retorna um placeholder."""
        path = os.path.join(self._icon_base_path, name)
        if not os.path.exists(path):
            # print(f"Aviso: Ícone não encontrado em {path}, usando placeholder.")
            pixmap = QPixmap(24, 24)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setPen(Qt.red)
            painter.drawRect(0, 0, 23, 23)
            painter.drawText(QRectF(0, 0, 24, 24), Qt.AlignCenter, "?")
            painter.end()
            return QIcon(pixmap)
        return QIcon(path)

    def _setup_menu_bar(self) -> None:
        """Configura a barra de menus."""
        menubar = self.menuBar()

        # --- Menu Arquivo ---
        file_menu = menubar.addMenu("&Arquivo")
        self.new_action = QAction(self._get_icon("clear.png"), "&Nova Cena", self)
        self.new_action.setShortcut("Ctrl+N")
        self.new_action.setToolTip("Criar uma nova cena vazia (Ctrl+N)")
        self.new_action.triggered.connect(self._prompt_clear_scene)
        file_menu.addAction(self.new_action)

        file_menu.addSeparator()

        self.load_obj_action = QAction(
            self._get_icon("open.png"), "&Abrir OBJ...", self
        )
        self.load_obj_action.setShortcut("Ctrl+O")
        self.load_obj_action.setToolTip(
            "Carregar geometria de um arquivo Wavefront OBJ (Ctrl+O)"
        )
        self.load_obj_action.triggered.connect(self._prompt_load_obj)
        file_menu.addAction(self.load_obj_action)

        self.save_as_action = QAction(
            self._get_icon("save.png"), "Salvar &Como OBJ...", self
        )
        self.save_as_action.setShortcut("Ctrl+Shift+S")
        self.save_as_action.setToolTip(
            "Salvar a cena em um novo arquivo Wavefront OBJ (Ctrl+Shift+S)"
        )
        self.save_as_action.triggered.connect(self._prompt_save_as_obj)
        file_menu.addAction(self.save_as_action)

        file_menu.addSeparator()

        exit_action = QAction(self._get_icon("exit.png"), "&Sair", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setToolTip("Fechar a aplicação (Ctrl+Q)")
        exit_action.triggered.connect(self.close)  # Chama closeEvent
        file_menu.addAction(exit_action)

        # --- Menu Editar ---
        edit_menu = menubar.addMenu("&Editar")
        delete_action = QAction(
            QIcon.fromTheme(
                "edit-delete", self._get_icon("delete.png")
            ),  # Tenta usar ícone do tema
            "&Excluir Selecionado(s)",
            self,
        )
        delete_action.setShortcuts([Qt.Key_Delete, Qt.Key_Backspace])
        delete_action.setToolTip("Excluir os itens selecionados (Delete / Backspace)")
        delete_action.triggered.connect(self._delete_selected_items)
        edit_menu.addAction(delete_action)

        edit_menu.addSeparator()

        transform_action = QAction(
            self._get_icon("transform.png"), "&Transformar Objeto...", self
        )
        transform_action.setShortcut("Ctrl+T")
        transform_action.setToolTip(
            "Aplicar translação, escala ou rotação ao objeto selecionado (Ctrl+T)"
        )
        transform_action.triggered.connect(self._open_transformation_dialog)
        edit_menu.addAction(transform_action)

        # --- Menu Exibir ---
        view_menu = menubar.addMenu("&Exibir")
        reset_view_action = QAction("Resetar &Vista", self)
        reset_view_action.setShortcut("Ctrl+R")
        reset_view_action.setToolTip("Resetar zoom, pan e rotação da vista (Ctrl+R)")
        reset_view_action.triggered.connect(self._reset_view)
        view_menu.addAction(reset_view_action)

        view_menu.addSeparator()

    def _setup_toolbar(self) -> None:
        """Configura a barra de ferramentas principal."""
        toolbar = QToolBar("Ferramentas")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.LeftToolBarArea, toolbar)

        self._mode_action_group = QActionGroup(self)
        self._mode_action_group.setExclusive(True)

        # --- Ações de Modo ---
        modes = [
            (
                DrawingMode.SELECT,
                "Selecionar",
                "Selecionar e mover itens (S)",
                "select.png",
                "S",
            ),
            (DrawingMode.PAN, "Mover Vista", "Mover a vista (Pan) (H)", "pan.png", "H"),
            (DrawingMode.POINT, "Ponto", "Desenhar pontos (P)", "point.png", "P"),
            (DrawingMode.LINE, "Linha", "Desenhar linhas (L)", "line.png", "L"),
            (
                DrawingMode.POLYGON,
                "Polígono",
                "Desenhar polígonos/polilinhas (G)",
                "polygon.png",
                "G",
            ),
        ]
        for mode, name, tip, icon_name, shortcut in modes:
            action = QAction(self._get_icon(icon_name), name, self)
            action.setToolTip(tip)
            action.setShortcut(shortcut)
            action.setCheckable(True)
            action.setData(mode)  # Armazena o enum DrawingMode
            action.triggered.connect(self._on_mode_action_triggered)
            toolbar.addAction(action)
            self._mode_action_group.addAction(action)
            if mode == self._drawing_mode:
                action.setChecked(True)

        toolbar.addSeparator()

        # --- Ação de Cor ---
        self.color_action = QAction(
            self._create_color_icon(self._current_draw_color, 24), "Cor", self
        )
        self.color_action.setToolTip("Selecionar cor para novos objetos (C)")
        self.color_action.setShortcut("C")
        self.color_action.triggered.connect(self._select_drawing_color)
        toolbar.addAction(self.color_action)

        toolbar.addSeparator()

        # --- Ação de Coordenadas Manuais ---
        manual_coord_action = QAction(self._get_icon("coords.png"), "Coords", self)
        manual_coord_action.setToolTip("Adicionar forma via coordenadas (M)")
        manual_coord_action.setShortcut("M")
        manual_coord_action.triggered.connect(self._open_coordinate_input_dialog)
        toolbar.addAction(manual_coord_action)

        # --- Ação de Transformação (já no menu Editar, redundante?) ---
        # Mantendo na toolbar por acesso rápido
        transform_action_tb = QAction(self._get_icon("transform.png"), "Transf.", self)
        transform_action_tb.setToolTip("Aplicar transformação (Ctrl+T)")
        # Não definimos shortcut aqui para evitar conflito com menu
        transform_action_tb.triggered.connect(self._open_transformation_dialog)
        toolbar.addAction(transform_action_tb)

    def _setup_status_bar(self) -> None:
        """Configura a barra de status com informações e controles."""
        self._status_bar = QStatusBar(self)
        self.setStatusBar(self._status_bar)

        # Mensagem temporária (à esquerda)
        self._status_message_label = QLabel("Pronto.")
        self._status_bar.addWidget(self._status_message_label, 1)  # Expansível

        # --- Widgets Permanentes (à direita) ---
        # Coordenadas
        self._status_coords_label = QLabel("X: --- Y: ---")
        self._status_coords_label.setToolTip("Coordenadas do mouse na cena")
        self._status_coords_label.setMinimumWidth(160)  # Mais espaço
        self._status_coords_label.setAlignment(Qt.AlignCenter)
        self._status_bar.addPermanentWidget(self._status_coords_label)

        # Modo
        self._status_mode_label = QLabel("Modo: Select")
        self._status_mode_label.setToolTip("Modo de interação atual")
        self._status_mode_label.setMinimumWidth(100)
        self._status_mode_label.setAlignment(Qt.AlignCenter)
        self._status_bar.addPermanentWidget(self._status_mode_label)

        # Rotação
        self._status_rotation_label = QLabel("Rot: 0.0°")
        self._status_rotation_label.setToolTip("Rotação da vista (Shift+Setas)")
        self._status_rotation_label.setMinimumWidth(80)
        self._status_rotation_label.setAlignment(Qt.AlignCenter)
        self._status_bar.addPermanentWidget(self._status_rotation_label)

        # Zoom Label
        self._zoom_label = QLabel("Zoom: 100%")
        self._zoom_label.setMinimumWidth(90)
        self._zoom_label.setAlignment(
            Qt.AlignRight | Qt.AlignVCenter
        )  # Alinha à direita
        self._status_bar.addPermanentWidget(self._zoom_label)

        # Zoom Slider
        self._zoom_slider = QSlider(Qt.Horizontal)
        self._zoom_slider.setRange(self.SLIDER_RANGE_MIN, self.SLIDER_RANGE_MAX)
        self._zoom_slider.setToolTip("Controlar o nível de zoom")
        self._zoom_slider.setMinimumWidth(100)
        self._zoom_slider.setMaximumWidth(150)  # Largura máxima
        self._zoom_slider.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._status_bar.addPermanentWidget(self._zoom_slider)

    def _update_status_bar(self) -> None:
        """Atualiza as informações dinâmicas na barra de status."""
        # Modo
        mode_map = {
            DrawingMode.SELECT: "Seleção",
            DrawingMode.PAN: "Mover Vista",
            DrawingMode.POINT: "Ponto",
            DrawingMode.LINE: "Linha",
            DrawingMode.POLYGON: "Polígono",
        }
        mode_text = f"Modo: {mode_map.get(self._drawing_mode, 'N/D')}"
        self._status_mode_label.setText(mode_text)

        # Rotação (formatada)
        rotation_angle = self._view.get_rotation_angle()
        rotation_text = f"Rot: {QLocale().toString(rotation_angle, 'f', 1)}°"  # Usa locale para formatar
        self._status_rotation_label.setText(rotation_text)

        # Coordenadas (atualizadas por _update_mouse_coords_status)
        # Zoom (atualizado por _update_view_controls)
        # Mensagem (atualizada por ações específicas)

    def _update_mouse_coords_status(self, scene_pos: QPointF):
        """Atualiza o label de coordenadas na status bar."""
        locale = QLocale()  # Usa o locale padrão (definido no main.py ou sistema)
        coord_text = f"X: {locale.toString(scene_pos.x(), 'f', 2)}  Y: {locale.toString(scene_pos.y(), 'f', 2)}"
        self._status_coords_label.setText(coord_text)

    def _connect_signals(self) -> None:
        """Conecta sinais e slots entre os componentes."""
        # View -> Editor
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.scene_mouse_moved.connect(self._update_mouse_coords_status)
        self._view.delete_requested.connect(self._delete_selected_items)
        self._view.rotation_changed.connect(self._update_view_controls)
        self._view.scale_changed.connect(self._update_view_controls)

        # Controller -> Editor
        # Note: pyqtSignal(object) requires the slot to accept 'object' or a specific type
        self._transformation_controller.object_transformed.connect(
            self._handle_object_transformed
        )

        # Controles UI -> Editor/View
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider_changed)
        # Não conectamos scene.changed para evitar updates excessivos

    # --- Slots para Controles da View (Zoom/Rotação) ---

    def _on_zoom_slider_changed(self, value: int) -> None:
        """Mapeia o valor do slider (logarítmico) para a escala da view."""
        if self.SLIDER_RANGE_MAX == self.SLIDER_RANGE_MIN:
            return

        # Use constants FROM THE VIEW instance
        view_scale_min = self._view.VIEW_SCALE_MIN
        view_scale_max = self._view.VIEW_SCALE_MAX

        # Mapeamento Logarítmico Inverso
        log_min = np.log(view_scale_min)
        log_max = np.log(view_scale_max)

        # Check for invalid range after log
        if log_max <= log_min:
            return

        factor = (value - self.SLIDER_RANGE_MIN) / (
            self.SLIDER_RANGE_MAX - self.SLIDER_RANGE_MIN
        )
        target_scale = np.exp(log_min + factor * (log_max - log_min))

        # Define a escala na view (centraliza na view ao usar o slider)
        # The view's set_scale will handle clamping using its own constants
        self._view.set_scale(target_scale, center_on_mouse=False)

    def _update_view_controls(self) -> None:
        """Atualiza o slider de zoom e labels com base no estado atual da view."""
        # --- Atualiza Zoom ---
        current_scale = self._view.get_scale()
        zoom_percent = current_scale * 100
        self._zoom_label.setText(
            f"Zoom: {QLocale().toString(zoom_percent, 'f', 0)}%"
        )  # Usa locale

        # Use constants FROM THE VIEW instance
        view_scale_min = self._view.VIEW_SCALE_MIN
        view_scale_max = self._view.VIEW_SCALE_MAX

        # Mapeia escala (log) de volta para valor do slider (linear)
        if view_scale_max <= view_scale_min:
            return

        log_min = np.log(view_scale_min)
        log_max = np.log(view_scale_max)

        # Check for invalid range after log
        if log_max <= log_min:
            return

        # Clampa a escala atual dentro dos limites para evitar erros de log/divisão
        clamped_scale = max(view_scale_min, min(current_scale, view_scale_max))
        log_scale = np.log(clamped_scale)

        factor = (log_scale - log_min) / (log_max - log_min)
        slider_value = int(
            round(
                self.SLIDER_RANGE_MIN
                + factor * (self.SLIDER_RANGE_MAX - self.SLIDER_RANGE_MIN)
            )
        )

        # Define valor no slider sem emitir sinal para evitar loop
        self._zoom_slider.blockSignals(True)
        self._zoom_slider.setValue(slider_value)
        self._zoom_slider.blockSignals(False)

        # --- Atualiza outros labels da status bar ---
        self._update_status_bar()

    # --- Métodos Utilitários de UI ---

    def _create_color_icon(self, color: QColor, size: int = 16) -> QIcon:
        """Cria um ícone quadrado com a cor especificada."""
        pixmap = QPixmap(size, size)
        valid_color = color if color.isValid() else QColor(Qt.black)
        pixmap.fill(valid_color)
        painter = QPainter(pixmap)
        border_color = Qt.gray  # Borda cinza fixa
        painter.setPen(QPen(border_color, 1))
        painter.drawRect(0, 0, size - 1, size - 1)
        painter.end()
        return QIcon(pixmap)

    def _select_drawing_color(self):
        """Abre diálogo para selecionar a cor de desenho."""
        initial_color = (
            self._current_draw_color if self._current_draw_color.isValid() else Qt.black
        )
        new_color = QColorDialog.getColor(
            initial_color, self, "Selecionar Cor de Desenho"
        )
        if new_color.isValid():
            self._current_draw_color = new_color
            self.color_action.setIcon(
                self._create_color_icon(self._current_draw_color, 24)
            )

    def _set_status_message(self, message: str, timeout: int = 3000):
        """Exibe uma mensagem na barra de status por um tempo determinado."""
        self._status_message_label.setText(message)
        if timeout > 0:
            QTimer.singleShot(
                timeout, lambda: self._status_message_label.setText("Pronto.")
            )

    # --- Gerenciamento de Modo ---

    def _on_mode_action_triggered(self) -> None:
        """Chamado quando uma ação de modo na toolbar é clicada."""
        checked_action = self._mode_action_group.checkedAction()
        if checked_action:
            new_mode = checked_action.data()
            if isinstance(new_mode, DrawingMode):
                self._set_drawing_mode(new_mode)

    def _set_drawing_mode(self, mode: DrawingMode) -> None:
        """Define o modo de desenho atual e atualiza a UI."""
        if mode == self._drawing_mode:
            return

        self._finish_current_drawing(commit=False)  # Cancela desenho em progresso
        self._drawing_mode = mode
        self._update_view_interaction()
        self._update_status_bar()

        # Garante que a ação correta na toolbar esteja marcada
        for action in self._mode_action_group.actions():
            if action.data() == mode:
                if not action.isChecked():
                    action.setChecked(True)
                break

    def _update_view_interaction(self) -> None:
        """Atualiza o cursor e o modo de arrasto da view com base no modo."""
        if self._drawing_mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
        elif self._drawing_mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
        else:  # Modos de desenho
            self._view.set_drag_mode(QGraphicsView.NoDrag)
        # O cursor é atualizado dentro de view.set_drag_mode()

    # --- Lógica de Desenho ---

    def _handle_scene_left_click(self, scene_pos: QPointF) -> None:
        """Processa clique esquerdo na cena."""
        if self._drawing_mode in [DrawingMode.SELECT, DrawingMode.PAN]:
            return

        current_point_data = Point(
            scene_pos.x(), scene_pos.y(), color=self._current_draw_color
        )

        if self._drawing_mode == DrawingMode.POINT:
            self._add_data_object_to_scene(current_point_data)
            self._mark_as_modified()

        elif self._drawing_mode == DrawingMode.LINE:
            if self._current_line_start is None:
                self._current_line_start = current_point_data
                self._update_line_preview(scene_pos)  # Mostra preview inicial
            else:
                # Finaliza a linha
                if (
                    current_point_data.get_coords()
                    == self._current_line_start.get_coords()
                ):
                    self._set_status_message(
                        "Ponto final igual ao inicial. Clique em outro lugar.", 2000
                    )
                    return

                line_data = Line(
                    self._current_line_start,
                    current_point_data,
                    color=self._current_draw_color,
                )
                self._add_data_object_to_scene(line_data)
                self._finish_current_drawing(commit=True)
                self._mark_as_modified()

        elif self._drawing_mode == DrawingMode.POLYGON:
            # Pergunta sobre tipo na primeira vez
            if not self._current_polygon_points:
                reply = QMessageBox.question(
                    self,
                    "Tipo de Forma",
                    "Deseja criar uma Polilinha (sequência de linhas ABERTAS)?\n\n"
                    "- Sim: Polilinha (>= 2 pontos).\n"
                    "- Não: Polígono Fechado (>= 3 pontos).\n\n"
                    "(Clique com o botão direito para finalizar)",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                self._current_polygon_is_open = reply == QMessageBox.Yes

            # Evita pontos duplicados consecutivos
            if (
                self._current_polygon_points
                and current_point_data.get_coords()
                == self._current_polygon_points[-1].get_coords()
            ):
                self._set_status_message("Ponto duplicado ignorado.", 1500)
                return

            self._current_polygon_points.append(current_point_data)
            self._update_polygon_preview(scene_pos)
            self._mark_as_modified()  # Modifica a cada ponto

    def _handle_scene_right_click(self, scene_pos: QPointF) -> None:
        """Processa clique direito, usado para finalizar polígonos."""
        if self._drawing_mode == DrawingMode.POLYGON:
            self._finish_current_drawing(commit=True)
        # Poderia adicionar um menu de contexto aqui para seleção/pan no futuro

    def _handle_scene_mouse_move(self, scene_pos: QPointF) -> None:
        """Processa movimento do mouse para pré-visualização."""
        # Atualiza preview se estiver desenhando
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            self._update_line_preview(scene_pos)
        elif self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            self._update_polygon_preview(scene_pos)

    def _update_line_preview(self, current_pos: QPointF):
        """Atualiza ou cria a linha de pré-visualização."""
        if not self._current_line_start:
            return
        start_qpos = self._current_line_start.to_qpointf()

        if self._temp_line_item is None:
            self._temp_line_item = QGraphicsLineItem(QLineF(start_qpos, current_pos))
            self._temp_line_item.setPen(self._temp_item_pen)
            self._temp_line_item.setZValue(1000)  # Fica por cima
            self._scene.addItem(self._temp_line_item)
        else:
            self._temp_line_item.setLine(QLineF(start_qpos, current_pos))

    def _update_polygon_preview(self, current_pos: QPointF):
        """Atualiza ou cria o caminho de pré-visualização do polígono."""
        if not self._current_polygon_points:
            return

        path = QPainterPath()
        path.moveTo(self._current_polygon_points[0].to_qpointf())
        for point_data in self._current_polygon_points[1:]:
            path.lineTo(point_data.to_qpointf())
        # Linha do último ponto adicionado até o cursor
        path.lineTo(current_pos)
        # Não desenha linha de fechamento no preview, simplifica

        if self._temp_polygon_path is None:
            self._temp_polygon_path = QGraphicsPathItem()
            self._temp_polygon_path.setPen(self._temp_item_pen)
            self._temp_polygon_path.setZValue(1000)
            self._scene.addItem(self._temp_polygon_path)

        self._temp_polygon_path.setPath(path)

    def _finish_current_drawing(self, commit: bool = True) -> None:
        """Finaliza ou cancela a operação de desenho atual (linha/polígono)."""
        drawing_finished_or_cancelled = False
        if self._drawing_mode == DrawingMode.LINE and self._current_line_start:
            # Commit da linha é feito no segundo clique, aqui só cancela
            self._current_line_start = None
            drawing_finished_or_cancelled = True

        if self._drawing_mode == DrawingMode.POLYGON and self._current_polygon_points:
            min_points_needed = 2 if self._current_polygon_is_open else 3
            can_commit = len(self._current_polygon_points) >= min_points_needed

            if commit and can_commit:
                # Cria o objeto Polygon final
                polygon_data = Polygon(
                    self._current_polygon_points.copy(),
                    self._current_polygon_is_open,
                    color=self._current_draw_color,
                )
                self._add_data_object_to_scene(polygon_data)
                self._mark_as_modified()  # Marca modificação ao finalizar
            elif commit and not can_commit:
                # Tentou finalizar sem pontos suficientes
                QMessageBox.warning(
                    self,
                    "Pontos Insuficientes",
                    f"Não é possível finalizar o polígono {'aberto' if self._current_polygon_is_open else 'fechado'}. "
                    f"Requer {min_points_needed} pontos (você tem {len(self._current_polygon_points)}). "
                    "Continue clicando ou cancele mudando de modo.",
                )
                return  # Não reseta, permite continuar

            # Reseta estado do polígono (se commit bem sucedido ou cancelamento)
            self._current_polygon_points = []
            self._current_polygon_is_open = False
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

    # --- Gerenciamento de Objetos e Cena ---

    def _add_data_object_to_scene(self, data_object: DataObject):
        """Cria o QGraphicsItem e o adiciona à cena."""
        try:
            graphics_item = data_object.create_graphics_item()
            # Associa o objeto de dados ao item gráfico para referência futura
            graphics_item.setData(0, data_object)  # Chave 0 por convenção
            # Aplica estilo (pode ser redundante se create_graphics_item já faz, mas garante)
            self._apply_style_to_item(graphics_item, data_object)
            self._scene.addItem(graphics_item)
            # A view se encarrega da transformação visual (zoom/rotação)
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Adicionar Item",
                f"Não foi possível criar item gráfico para {type(data_object).__name__}: {e}",
            )
            print(f"Erro detalhes: {e}")

    def _delete_selected_items(self) -> None:
        """Remove os itens selecionados da cena."""
        selected = self._scene.selectedItems()
        if not selected:
            self._set_status_message("Nenhum item selecionado para excluir.", 2000)
            return

        # Confirmação opcional (desativada por padrão para fluidez)
        # reply = QMessageBox.question(self, "Confirmar Exclusão", ...)
        # if reply == QMessageBox.No: return

        items_deleted = 0
        for item in selected:
            if item.scene():  # Verifica se ainda está na cena
                self._scene.removeItem(item)
                items_deleted += 1
                # Considerar deletar o DataObject de alguma lista interna se houver

        if items_deleted > 0:
            self._scene.update()
            self._mark_as_modified()
            self._set_status_message(f"{items_deleted} item(ns) excluído(s).", 2000)

    def _prompt_clear_scene(self):
        """Pergunta ao usuário se deseja limpar a cena."""
        if self._check_unsaved_changes("limpar a cena"):
            self._clear_scene_confirmed()

    def _clear_scene_confirmed(self) -> None:
        """Limpa todos os itens da cena e reseta estado."""
        self._finish_current_drawing(commit=False)
        self._scene.clearSelection()
        self._scene.clear()  # Mais eficiente que iterar e remover
        self._scene.update()
        self._reset_view()
        self._mark_as_saved()
        self._current_filepath = None
        self._update_window_title()
        self._set_status_message("Nova cena criada.", 2000)

    def _reset_view(self) -> None:
        """Reseta a transformação da QGraphicsView."""
        self._view.reset_view()
        # Os sinais da view já atualizam os controles (slider, labels)

    # --- Modificação e Salvamento ---

    def _mark_as_modified(self):
        """Marca a cena como modificada."""
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_window_title()

    def _mark_as_saved(self):
        """Marca a cena como salva."""
        if self._unsaved_changes:
            self._unsaved_changes = False
            self._update_window_title()

    def _update_window_title(self):
        """Atualiza o título da janela (arquivo, estado modificado)."""
        title = "Editor Gráfico 2D - "
        filename = "Nova Cena"
        if self._current_filepath:
            filename = os.path.basename(self._current_filepath)
        title += filename
        if self._unsaved_changes:
            title += " *"  # Indicador de não salvo
        self.setWindowTitle(title)

    def _check_unsaved_changes(self, action_description: str = "prosseguir") -> bool:
        """Verifica alterações não salvas e pergunta ao usuário o que fazer."""
        if not self._unsaved_changes:
            return True

        reply = QMessageBox.warning(
            self,
            "Alterações Não Salvas",
            f"A cena contém alterações não salvas. Deseja salvá-las antes de {action_description}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,  # Default é salvar
        )

        if reply == QMessageBox.Save:
            return (
                self._save_current_file()
            )  # Tenta salvar; retorna True se sucesso/cancelado pelo user, False se falha
        elif reply == QMessageBox.Discard:
            return True  # Pode prosseguir
        else:  # reply == QMessageBox.Cancel
            return False  # Não prosseguir

    # --- Diálogos e Interações Externas ---

    def _open_coordinate_input_dialog(self) -> None:
        """Abre diálogo para adicionar formas via coordenadas."""
        self._finish_current_drawing(commit=False)

        dialog_mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
        }
        dialog_mode_str = dialog_mode_map.get(self._drawing_mode)

        # Se não estiver em modo de desenho, pergunta qual forma criar
        if dialog_mode_str is None:
            items = ("Ponto", "Linha", "Polígono")
            item, ok = QInputDialog.getItem(
                self,
                "Selecionar Forma",
                "Qual forma deseja adicionar?",
                items,
                0,
                False,
            )
            if ok and item:
                dialog_mode_str = {
                    "Ponto": "point",
                    "Linha": "line",
                    "Polígono": "polygon",
                }.get(item)
            else:
                return  # Cancelou

        if not dialog_mode_str:
            return

        dialog = CoordinateInputDialog(self, mode=dialog_mode_str)
        dialog.set_initial_color(self._current_draw_color)

        if dialog.exec_() == QDialog.Accepted:
            try:
                result_data = dialog.get_validated_data()  # Pega dados já validados
                if result_data:
                    self._add_item_from_validated_data(result_data, dialog_mode_str)
                    self._mark_as_modified()
            except ValueError as e:  # Erros durante a criação do objeto final
                QMessageBox.warning(
                    self,
                    "Erro ao Criar Objeto",
                    f"Não foi possível criar o objeto: {e}",
                )
            except Exception as e:  # Outros erros inesperados
                QMessageBox.critical(
                    self,
                    "Erro Interno",
                    f"Erro inesperado ao processar dados do diálogo: {e}",
                )

    def _add_item_from_validated_data(
        self, result_data: Any, dialog_mode_str: str
    ) -> None:
        """Cria e adiciona objeto de dados à cena a partir de dados validados do diálogo."""
        try:
            data_object: Optional[DataObject] = None
            color = result_data.get("color", QColor(Qt.black))
            coords = result_data.get("coords", [])

            if not coords:
                raise ValueError("Coordenadas ausentes.")

            if dialog_mode_str == "point":
                data_object = Point(coords[0][0], coords[0][1], color=color)
            elif dialog_mode_str == "line":
                if len(coords) < 2:
                    raise ValueError("Coordenadas da linha insuficientes.")
                # Validação de pontos iguais já feita no diálogo
                start_pt = Point(coords[0][0], coords[0][1], color=color)
                end_pt = Point(coords[1][0], coords[1][1], color=color)
                data_object = Line(start_pt, end_pt, color=color)
            elif dialog_mode_str == "polygon":
                is_open = result_data.get("is_open", False)
                min_pts = 2 if is_open else 3
                if len(coords) < min_pts:
                    raise ValueError(f"Pontos insuficientes ({len(coords)}/{min_pts}).")
                poly_pts = [Point(x, y, color=color) for x, y in coords]
                data_object = Polygon(poly_pts, is_open, color=color)

            if data_object:
                self._add_data_object_to_scene(data_object)
            else:
                raise ValueError(f"Modo de criação desconhecido: {dialog_mode_str}")

        except (ValueError, TypeError, IndexError, KeyError) as e:
            # Captura erros específicos da criação/processamento
            raise ValueError(
                f"Erro ao criar item: {e}"
            )  # Repassa erro para msgbox no chamador

    def _open_transformation_dialog(self) -> None:
        """Abre diálogo para aplicar transformações ao item selecionado."""
        selected_items = self._scene.selectedItems()
        if len(selected_items) != 1:
            QMessageBox.warning(
                self,
                "Seleção Inválida",
                "Selecione exatamente UM objeto para transformar.",
            )
            return

        graphics_item = selected_items[0]
        data_object = graphics_item.data(0)  # Recupera DataObject associado

        if not isinstance(data_object, (Point, Line, Polygon)):
            type_name = type(data_object).__name__ if data_object else "Nenhum"
            QMessageBox.critical(
                self,
                "Erro Interno",
                f"Item selecionado não tem dados válidos ({type_name}) ou não é transformável.",
            )
            return

        self._finish_current_drawing(commit=False)
        # Passa o objeto de DADOS para o controlador
        self._transformation_controller.request_transformation(data_object)
        # O controlador emitirá 'object_transformed' se OK

    # Slot to handle the transformed object signal from the controller
    # Needs to accept a generic 'object' due to pyqtSignal limitations
    def _handle_object_transformed(self, transformed_data_object: object) -> None:
        """Atualiza o item gráfico correspondente após a transformação."""
        # Check if the received object is one of our data types
        if not isinstance(transformed_data_object, (Point, Line, Polygon)):
            print(
                f"AVISO: Sinal object_transformed recebido com tipo inesperado: {type(transformed_data_object)}"
            )
            return

        # Find the corresponding graphics item
        graphics_item = self._find_graphics_item_for_object(transformed_data_object)
        if not graphics_item:
            print(
                f"AVISO: Item gráfico não encontrado para {transformed_data_object} após transformação."
            )
            QMessageBox.warning(
                self,
                "Erro de Atualização",
                "Não foi possível encontrar o item gráfico correspondente na cena.",
            )
            return

        try:
            graphics_item.prepareGeometryChange()  # Notifica mudança iminente
            self._update_graphics_item_geometry(graphics_item, transformed_data_object)
            self._apply_style_to_item(
                graphics_item, transformed_data_object
            )  # Garante cor/estilo
            # Scene update might be sufficient if geometry change is detected
            self._scene.update(graphics_item.boundingRect())  # Update area
            # self._view.viewport().update() # Force viewport redraw if needed
            self._mark_as_modified()
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Atualizar Gráfico",
                f"Falha ao atualizar item {type(graphics_item).__name__}: {e}",
            )
            print(f"Erro detalhes: {e}")

    def _find_graphics_item_for_object(
        self, data_obj: DataObject
    ) -> Optional[QGraphicsItem]:
        """Encontra o QGraphicsItem na cena correspondente ao DataObject."""
        if data_obj is None:
            return None
        # Itera sobre todos os itens na cena
        for item in self._scene.items():
            # Compara a identidade do objeto de dados associado (chave 0)
            if item.data(0) is data_obj:
                return item
        return None

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        """Atualiza a geometria do item gráfico com base no DataObject."""
        # Usa isinstance para garantir tipo correto do item e dos dados
        if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
            size, offset = 6.0, 3.0  # Consistente com point.py
            new_rect = QRectF(data.x - offset, data.y - offset, size, size)
            if item.rect() != new_rect:
                item.setRect(new_rect)
        elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
            new_line = QLineF(data.start.x, data.start.y, data.end.x, data.end.y)
            if item.line() != new_line:
                item.setLine(new_line)
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            new_polygon_qf = QPolygonF([p.to_qpointf() for p in data.points])
            if item.polygon() != new_polygon_qf:
                item.setPolygon(new_polygon_qf)
        else:
            print(
                f"AVISO: Combinação item/dado não prevista para atualização de geometria:"
                f" {type(item).__name__} / {type(data).__name__}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, data: DataObject):
        """Reaplica estilo (cor, preenchimento, etc.) ao item gráfico."""
        if not hasattr(data, "color"):
            return
        color = (
            data.color
            if isinstance(data.color, QColor) and data.color.isValid()
            else QColor(Qt.black)
        )

        pen = None
        brush = None

        if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
            pen = QPen(color, 2)  # Espessura padrão
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            pen = QPen(color, 2)
            brush = QBrush()  # Começa como NoBrush
            if data.is_open:
                pen.setStyle(Qt.DashLine)
                brush.setStyle(Qt.NoBrush)
            else:  # Fechado
                pen.setStyle(Qt.SolidLine)
                brush.setStyle(Qt.SolidPattern)
                fill_color = QColor(color)
                fill_color.setAlphaF(0.35)  # Preenchimento semi-transparente
                brush.setColor(fill_color)

        # Aplica apenas se mudou para evitar updates desnecessários
        if pen is not None and item.pen() != pen:
            item.setPen(pen)
        if brush is not None and item.brush() != brush:
            item.setBrush(brush)

    # --- Importação/Exportação OBJ ---

    def _prompt_load_obj(self) -> None:
        """Abre diálogo para carregar arquivo OBJ."""
        if not self._check_unsaved_changes("carregar um novo arquivo"):
            return
        obj_filepath = self._io_handler.prompt_load_obj()
        if obj_filepath:
            self._load_obj_file(obj_filepath, clear_before_load=True)

    def _load_obj_file(self, obj_filepath: str, clear_before_load: bool = True):
        """Carrega e processa um arquivo OBJ."""
        self._set_status_message(
            f"Carregando {os.path.basename(obj_filepath)}...", 0
        )  # 0 = sem timeout
        QApplication.processEvents()

        read_result = self._io_handler.read_obj_lines(obj_filepath)
        if read_result is None:
            self._set_status_message("Falha ao ler arquivo OBJ.")
            return
        obj_lines, mtl_filename_relative = read_result

        material_colors: Dict[str, QColor] = {}
        mtl_warnings: List[str] = []
        mtl_filepath_full: Optional[str] = None
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            mtl_filepath_full = os.path.normpath(
                os.path.join(obj_dir, mtl_filename_relative)
            )
            if os.path.exists(mtl_filepath_full):
                material_colors, mtl_warnings = self._io_handler.read_mtl_file(
                    mtl_filepath_full
                )
            else:
                mtl_warnings.append(
                    f"Arquivo MTL '{mtl_filename_relative}' não encontrado em '{obj_dir}'."
                )
                mtl_filepath_full = None

        # Analisa dados OBJ -> DataObjects
        parsed_objects, obj_warnings = self._object_manager.parse_obj_data(
            obj_lines,
            material_colors,
            self._current_draw_color,  # Cor padrão se material falhar
        )

        if clear_before_load:
            self._clear_scene_confirmed()  # Limpa cena e estado

        # Adiciona objetos à cena
        creation_errors = []
        num_added = 0
        if not parsed_objects and not mtl_warnings and not obj_warnings:
            msg = f"Nenhum objeto geométrico (v, l, f, p) ou material válido encontrado em '{os.path.basename(obj_filepath)}'."
            if mtl_filename_relative and not mtl_filepath_full:
                msg += f"\nArquivo MTL '{mtl_filename_relative}' referenciado não foi encontrado."
            QMessageBox.information(self, "Arquivo Vazio ou Não Suportado", msg)
            self._set_status_message("Carregamento concluído (sem geometria).")
        else:
            for data_obj in parsed_objects:
                try:
                    self._add_data_object_to_scene(data_obj)
                    num_added += 1
                except Exception as e:
                    creation_errors.append(
                        f"Erro ao criar item para {type(data_obj).__name__}: {e}"
                    )

            self._scene.update()
            # Reset view já feito em _clear_scene_confirmed se aplicável

            # Relatório final
            all_warnings = mtl_warnings + obj_warnings + creation_errors
            final_message = f"Carregado: {num_added} objeto(s) de '{os.path.basename(obj_filepath)}'."
            if all_warnings:
                formatted_warnings = "- " + "\n- ".join(all_warnings)
                QMessageBox.warning(
                    self,
                    "Carregado com Avisos",
                    f"{final_message}\n\nAvisos/Erros:\n{formatted_warnings}",
                )
                final_message += " (com avisos)"
            # else:
            # QMessageBox.information(self, "Carregamento Concluído", final_message) # Menos popups

            self._set_status_message(final_message)

        # Atualiza estado pós-carregamento
        self._current_filepath = obj_filepath
        self._mark_as_saved()  # Considera salvo após carregar
        self._update_window_title()

    def _prompt_save_as_obj(self) -> bool:
        """Abre diálogo "Salvar Como" e chama a lógica de salvamento."""
        self._finish_current_drawing(commit=False)

        default_name = (
            os.path.basename(self._current_filepath)
            if self._current_filepath
            else "cena_sem_titulo.obj"
        )
        base_filepath = self._io_handler.prompt_save_obj(default_name)
        if not base_filepath:
            self._set_status_message("Salvar cancelado.")
            return False

        # Chama salvamento real
        if self._save_to_file(base_filepath):
            # Remove a extensão .obj que prompt_save_obj pode ter retornado no base_filepath
            self._current_filepath = (
                base_filepath + ".obj"
                if not base_filepath.lower().endswith(".obj")
                else base_filepath
            )
            self._mark_as_saved()
            self._update_window_title()
            return True
        else:
            self._set_status_message("Falha ao salvar.")
            return False

    def _save_current_file(self) -> bool:
        """Salva a cena no arquivo atual. Se não houver, chama 'Salvar Como'."""
        if not self._current_filepath:
            return self._prompt_save_as_obj()
        else:
            self._finish_current_drawing(commit=False)
            base_filepath, _ = os.path.splitext(
                self._current_filepath
            )  # Obtém caminho base sem extensão
            if self._save_to_file(base_filepath):
                self._mark_as_saved()
                self._update_window_title()
                return True
            else:
                return False  # Mensagem de erro já mostrada por _save_to_file

    def _save_to_file(self, base_filepath: str) -> bool:
        """Lógica interna para gerar e escrever arquivos OBJ e MTL."""
        self._set_status_message(f"Salvando em {os.path.basename(base_filepath)}...", 0)
        QApplication.processEvents()

        # Coleta DataObjects da cena
        scene_data_objects: List[DataObject] = []
        for item in self._scene.items():
            # Ignora itens temporários
            if item is self._temp_line_item or item is self._temp_polygon_path:
                continue
            data = item.data(0)
            if isinstance(data, (Point, Line, Polygon)):
                scene_data_objects.append(data)

        if not scene_data_objects:
            QMessageBox.information(self, "Nada para Salvar", "A cena está vazia.")
            self._set_status_message("Nada para salvar.")
            return False

        # Gera dados OBJ/MTL
        mtl_filename = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, warnings_gen = self._object_manager.generate_obj_data(
            scene_data_objects, mtl_filename
        )

        if obj_lines is None:  # Geração falhou
            msg = "Falha ao gerar dados OBJ para salvar."
            if warnings_gen:
                msg += "\n\nAvisos:\n- " + "\n- ".join(warnings_gen)
            QMessageBox.critical(self, "Erro na Geração OBJ", msg)
            self._set_status_message("Erro ao gerar OBJ.")
            return False

        # Escreve arquivos
        success = self._io_handler.write_obj_and_mtl(
            base_filepath, obj_lines, mtl_lines
        )

        if success:
            obj_name = os.path.basename(base_filepath + ".obj")
            msg = f"Cena salva como '{obj_name}'"
            if mtl_lines:
                msg += f" e '{os.path.basename(base_filepath)}.mtl'"
            msg += "."
            if warnings_gen:
                formatted_warnings = "\n\nAvisos:\n- " + "\n- ".join(warnings_gen)
                QMessageBox.warning(
                    self, "Salvo com Avisos", f"{msg}{formatted_warnings}"
                )
                msg += " (com avisos)"
            self._set_status_message(msg)
            return True
        else:
            # IOHandler já mostrou erro crítico
            self._set_status_message(
                f"Falha ao escrever arquivo(s) para '{os.path.basename(base_filepath)}'."
            )
            return False

    # --- Evento de Fechamento ---

    def closeEvent(self, event: QCloseEvent) -> None:
        """Chamado ao tentar fechar a janela."""
        self._finish_current_drawing(commit=False)
        if self._check_unsaved_changes("fechar a aplicação"):
            event.accept()  # Permite fechar
        else:
            event.ignore()  # Cancela fechamento
