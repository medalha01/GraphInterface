# graphics_editor/editor.py
import math
import sys
import os
import numpy as np
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Union, Any
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QGraphicsScene,
    QAction,
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
    QGraphicsRectItem,
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
from PyQt5.QtWidgets import QApplication

# Importações relativas dentro do pacote
from .view.main_view import GraphicsView
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon
from .models.bezier_curve import BezierCurve
from .dialogs.coordinates_input import CoordinateInputDialog
from .dialogs.transformation_dialog import TransformationDialog
from .controllers.transformation_controller import (
    TransformationController,
    TransformableObject,
)
from .io_handler import IOHandler
from .object_manager import ObjectManager
from .utils import clipping as clp

# Importações dos componentes MVC/Estado
from .state_manager import EditorStateManager, DrawingMode, LineClippingAlgorithm
from .controllers.drawing_controller import DrawingController
from .ui_manager import UIManager

# Alias para tipos de dados dos modelos
DataObject = Union[Point, Line, Polygon, BezierCurve]
# Tuple of actual types for isinstance checks
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve)


class GraphicsEditor(QMainWindow):
    """Janela principal da aplicação para o editor gráfico 2D (Coordenador)."""

    # Configuration constants
    BEZIER_CLIPPING_SAMPLES_PER_SEGMENT = 20  # Samples for clipping Bezier curves
    BEZIER_SAVE_SAMPLES_PER_SEGMENT = 20  # Samples for saving Bezier as lines in OBJ

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Gráfico 2D - Nova Cena")
        self.resize(1000, 750)

        # Centralized Map for Object Lookup (Optimization)
        self._data_object_to_item_map: Dict[DataObject, QGraphicsItem] = {}

        # Reusable timer for status bar messages
        self._status_reset_timer = QTimer(self)
        self._status_reset_timer.setSingleShot(True)
        self._status_reset_timer.timeout.connect(
            lambda: self._ui_manager.update_status_bar_message("Pronto.")
        )

        # --- Configura Componentes Principais ---
        self._setup_core_components()

        # --- Configura Gerenciadores e Controladores ---
        self._setup_managers_controllers()

        # --- Configura Itens Gráficos Especiais ---
        self._setup_special_items()

        # --- Configura Elementos da UI ---
        self._setup_ui_elements()

        # --- Conecta Sinais e Slots ---
        self._connect_signals()

        # --- Estado Inicial da UI ---
        self._initialize_ui_state()

    # --- Helpers de Inicialização ---

    def _setup_core_components(self) -> None:
        """Inicializa a cena e a vista principais."""
        self._scene = QGraphicsScene(self)
        # Define a large scene rectangle to allow extensive panning
        self._scene.setSceneRect(-50000, -50000, 100000, 100000)  # Increased size
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

    def _setup_managers_controllers(self) -> None:
        """Inicializa os gerenciadores e controladores."""
        self._state_manager = EditorStateManager(self)
        self._ui_manager = UIManager(self, self._state_manager)
        self._drawing_controller = DrawingController(
            self._scene, self._state_manager, self
        )
        self._transformation_controller = TransformationController(self)
        self._io_handler = IOHandler(self)
        # Pass configuration for Bezier saving samples
        self._object_manager = ObjectManager(
            bezier_samples=self.BEZIER_SAVE_SAMPLES_PER_SEGMENT
        )

    def _setup_special_items(self) -> None:
        """Inicializa itens especiais da cena como o retângulo do viewport."""
        self._clip_rect_item = QGraphicsRectItem(self._state_manager.clip_rect())
        pen = QPen(QColor(0, 0, 255, 100), 1, Qt.DashLine)  # Blue dashed line
        pen.setCosmetic(True)  # Keep pen width constant regardless of zoom
        self._clip_rect_item.setPen(pen)
        self._clip_rect_item.setBrush(QBrush(Qt.NoBrush))
        self._clip_rect_item.setZValue(-1)  # Ensure it's behind other items
        self._clip_rect_item.setData(0, "viewport_rect")  # Identify this item
        self._scene.addItem(self._clip_rect_item)

    def _setup_ui_elements(self) -> None:
        """Configura os elementos principais da UI (menu, toolbar, status bar)."""
        self._setup_menu_bar()
        # Pass callbacks for toolbar actions
        self._ui_manager.setup_toolbar(
            mode_callback=self._set_drawing_mode,
            color_callback=self._select_drawing_color,
            coord_callback=self._open_coordinate_input_dialog,
            transform_callback=self._open_transformation_dialog,
            clipper_callback=self._set_line_clipper,
        )
        # Pass callback for zoom slider interaction
        self._ui_manager.setup_status_bar(zoom_callback=self._on_zoom_slider_changed)

    def _initialize_ui_state(self) -> None:
        """Define o estado inicial da UI após a configuração."""
        self._update_view_interaction()
        self._update_window_title()  # Set initial window title
        # Update view controls after the event loop starts, ensuring view is ready
        QTimer.singleShot(0, self._update_view_controls)

    # --- Configuração da UI (Menus principalmente) ---

    def _get_icon(self, name: str) -> QIcon:
        """Reutiliza método do UIManager para carregar ícones."""
        # Ensure UIManager is initialized before calling this
        if not hasattr(self, "_ui_manager"):
            # Fallback or error if called too early
            print("Error: _get_icon called before UIManager initialization.")
            return QIcon()
        return self._ui_manager._get_icon(name)

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
        exit_action.triggered.connect(self.close)  # Use built-in close method
        file_menu.addAction(exit_action)

        # --- Menu Editar ---
        edit_menu = menubar.addMenu("&Editar")
        delete_action = QAction(
            QIcon.fromTheme("edit-delete", self._get_icon("delete.png")),
            "&Excluir Selecionado(s)",
            self,
        )
        delete_action.setShortcuts(
            [Qt.Key_Delete, Qt.Key_Backspace]
        )  # Standard shortcuts
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
        # Action to toggle viewport visibility
        # Store reference in UIManager to update checked state
        self._ui_manager.viewport_toggle_action = QAction(
            "Mostrar/Ocultar Viewport", self, checkable=True
        )
        self._ui_manager.viewport_toggle_action.setChecked(
            self._clip_rect_item.isVisible()
        )
        self._ui_manager.viewport_toggle_action.triggered.connect(
            self._toggle_viewport_visibility
        )
        view_menu.addAction(self._ui_manager.viewport_toggle_action)

    # --- Conexão de Sinais e Slots ---

    def _connect_signals(self) -> None:
        """Conecta sinais e slots entre os componentes."""

        # --- View -> Editor (Coordenação / Ações) ---
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(
            self._delete_selected_items
        )  # From keyboard

        # --- View -> UI Manager (Atualização de Status Display) ---
        self._view.scene_mouse_moved.connect(self._ui_manager.update_status_bar_coords)
        self._view.rotation_changed.connect(
            self._update_view_controls
        )  # Update status bar on view change
        self._view.scale_changed.connect(
            self._update_view_controls
        )  # Update status bar on view change

        # --- StateManager -> UI Manager (Atualização da UI baseada no Estado) ---
        self._state_manager.drawing_mode_changed.connect(
            self._ui_manager.update_toolbar_mode_selection
        )
        self._state_manager.drawing_mode_changed.connect(
            self._ui_manager.update_status_bar_mode
        )
        self._state_manager.draw_color_changed.connect(
            self._ui_manager.update_color_button
        )
        self._state_manager.unsaved_changes_changed.connect(self._update_window_title)
        self._state_manager.filepath_changed.connect(self._update_window_title)
        self._state_manager.line_clipper_changed.connect(
            self._ui_manager.update_clipper_selection
        )
        self._state_manager.clip_rect_changed.connect(
            self._update_clip_rect_item
        )  # Update visual viewport rect

        # --- StateManager -> Editor (Lógica de Interação e Controle) ---
        self._state_manager.drawing_mode_changed.connect(
            self._update_view_interaction
        )  # Change view drag mode
        # Cancel any ongoing drawing if mode changes
        self._state_manager.drawing_mode_changed.connect(
            self._drawing_controller.cancel_current_drawing
        )

        # --- DrawingController -> Editor (Adicionar Objeto Finalizado / Mensagens) ---
        self._drawing_controller.object_ready_to_add.connect(
            self._add_data_object_to_scene
        )
        self._drawing_controller.status_message_requested.connect(
            self._set_status_message
        )

        # --- TransformationController -> Editor (Atualizar Objeto Transformado) ---
        self._transformation_controller.object_transformed.connect(
            self._handle_object_transformed
        )

    # --- Handlers de Eventos da Vista (Delegam ou Processam) ---

    def _handle_scene_left_click(self, scene_pos: QPointF):
        """Decide se passa o clique para o DrawingController ou deixa a Vista tratar."""
        mode = self._state_manager.drawing_mode()
        # Pass clicks to drawing controller only if in a drawing mode
        if mode in [
            DrawingMode.POINT,
            DrawingMode.LINE,
            DrawingMode.POLYGON,
            DrawingMode.BEZIER,
        ]:
            self._drawing_controller.handle_scene_left_click(scene_pos)
        # Otherwise, the View handles it (e.g., selection in SELECT mode, pan start in PAN mode)
        # The view's mousePressEvent already handles passing events to base class when appropriate.

    def _handle_scene_right_click(self, scene_pos: QPointF):
        """Decide se passa o clique direito para o DrawingController."""
        mode = self._state_manager.drawing_mode()
        # Right-click finishes Polygon or Bezier drawing
        if mode in [DrawingMode.POLYGON, DrawingMode.BEZIER]:
            self._drawing_controller.handle_scene_right_click(scene_pos)
        # Future: Could implement context menus for SELECT mode here

    def _handle_scene_mouse_move(self, scene_pos: QPointF):
        """Passa o movimento para o DrawingController se estiver desenhando."""
        mode = self._state_manager.drawing_mode()
        # Update drawing previews if in a drawing mode and drawing has started
        if mode in [DrawingMode.LINE, DrawingMode.POLYGON, DrawingMode.BEZIER]:
            self._drawing_controller.handle_scene_mouse_move(scene_pos)
        # Status bar coordinate update is handled by direct connection view->uimanager

    # --- Controle de Modo e Interação ---

    def _set_drawing_mode(self, mode: DrawingMode):
        """Define o modo de desenho/interação através do StateManager."""
        self._state_manager.set_drawing_mode(mode)

    def _update_view_interaction(self):
        """Atualiza o modo de arrasto e cursor da vista com base no modo do StateManager."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
        elif mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
        else:  # Drawing modes
            self._view.set_drag_mode(
                QGraphicsView.NoDrag
            )  # Let controller handle clicks
        # set_drag_mode in GraphicsView already handles setting the cursor

    def _set_line_clipper(self, algorithm: LineClippingAlgorithm):
        """Define o algoritmo de clipping de linha via StateManager."""
        self._state_manager.set_selected_line_clipper(algorithm)
        algo_name = (
            "Cohen-Sutherland"
            if algorithm == LineClippingAlgorithm.COHEN_SUTHERLAND
            else "Liang-Barsky"
        )
        self._set_status_message(f"Clipping de linha: {algo_name}", 2000)

    # --- Controle da Vista (Zoom/Rotação) ---

    def _on_zoom_slider_changed(self, value: int):
        """Mapeia o valor do slider (linear) para a escala da vista (logarítmica)."""
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX

        # Avoid division by zero or invalid ranges
        if max_slider <= min_slider or max_scale <= min_scale:
            return
        log_min, log_max = np.log(min_scale), np.log(max_scale)
        if log_max <= log_min:
            return

        # Map slider value linearly to the logarithmic scale range
        factor = (value - min_slider) / (max_slider - min_slider)
        target_scale = np.exp(log_min + factor * (log_max - log_min))

        # Apply scale via view's method, centering on view center (not mouse) for slider
        self._view.set_scale(target_scale, center_on_mouse=False)

    def _update_view_controls(self):
        """Atualiza os controles da UI (slider/labels) com base no estado atual da vista."""
        # Called when view scale or rotation changes
        self._update_zoom_controls()
        self._update_rotation_controls()

    def _update_zoom_controls(self):
        """Atualiza o slider e label de zoom com base na escala da vista (log inverso)."""
        current_scale = self._view.get_scale()
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        slider_value = min_slider  # Default value

        # Avoid division by zero or log(0) if scales are valid
        if max_scale > min_scale and max_slider > min_slider:
            log_min, log_max = np.log(min_scale), np.log(max_scale)
            if log_max > log_min:
                # Ensure current scale is within bounds before calculating log
                clamped_scale = np.clip(current_scale, min_scale, max_scale)
                log_scale = np.log(clamped_scale)
                # Map log scale value linearly back to the slider's range
                factor = (log_scale - log_min) / (log_max - log_min)
                slider_value = int(
                    round(min_slider + factor * (max_slider - min_slider))
                )

        # Update UI elements via UIManager
        self._ui_manager.update_status_bar_zoom(current_scale, slider_value)

    def _update_rotation_controls(self):
        """Atualiza o label de rotação com base na rotação da vista."""
        rotation_angle = self._view.get_rotation_angle()
        self._ui_manager.update_status_bar_rotation(rotation_angle)

    def _reset_view(self):
        """Reseta a transformação da vista e centraliza no viewport padrão."""
        self._view.reset_view()
        # Center on the middle of the default clip rectangle after resetting
        self._view.centerOn(self._state_manager.clip_rect().center())
        # The view's reset method emits signals which trigger UI updates (_update_view_controls)

    # --- Gerenciamento de Objetos e Clipping ---

    def _clip_data_object(
        self, data_object: DataObject
    ) -> Tuple[Optional[DataObject], bool]:
        """
        Recorta um objeto de dados contra o viewport atual.
        Bézier curves são APROXIMADAS por polilinhas e clipadas como tal.

        Returns:
            Tuple (clipped_object, needs_replacement):
                clipped_object: O objeto recortado (pode ser de tipo diferente, e.g., Polygon para Bezier),
                                ou None se totalmente fora.
                needs_replacement: True se o tipo do objeto mudou durante o clipping (requer
                                   substituição do QGraphicsItem), False caso contrário.
        """
        clipped_result: Optional[DataObject] = None
        needs_replacement = False  # Assume only update is needed initially
        clip_rect_tuple = self._get_clip_rect_tuple()
        clipper_algo = self._state_manager.selected_line_clipper()
        clipper_func = (
            clp.cohen_sutherland
            if clipper_algo == LineClippingAlgorithm.COHEN_SUTHERLAND
            else clp.liang_barsky
        )

        try:
            if isinstance(data_object, Point):
                clipped_coords = clp.clip_point(
                    data_object.get_coords(), clip_rect_tuple
                )
                if clipped_coords:
                    clipped_result = Point(
                        clipped_coords[0], clipped_coords[1], data_object.color
                    )
            elif isinstance(data_object, Line):
                clipped_segment = clipper_func(
                    data_object.start.get_coords(),
                    data_object.end.get_coords(),
                    clip_rect_tuple,
                )
                if clipped_segment:
                    p1, p2 = clipped_segment
                    # Create new Point objects for the clipped line
                    start_pt = Point(
                        p1[0], p1[1], data_object.color
                    )  # Use line color for points
                    end_pt = Point(p2[0], p2[1], data_object.color)
                    clipped_result = Line(start_pt, end_pt, data_object.color)
            elif isinstance(data_object, Polygon):
                clipped_vertices_coords = clp.sutherland_hodgman(
                    data_object.get_coords(), clip_rect_tuple
                )
                min_points = 2 if data_object.is_open else 3
                if len(clipped_vertices_coords) >= min_points:
                    clipped_points = [
                        Point(x, y, data_object.color)
                        for x, y in clipped_vertices_coords
                    ]
                    clipped_result = Polygon(
                        clipped_points,
                        is_open=data_object.is_open,
                        color=data_object.color,
                        is_filled=data_object.is_filled,
                    )
            elif isinstance(data_object, BezierCurve):
                # Clipping Bezier by sampling is an approximation.
                # The result is a polyline (represented as an open Polygon).
                sampled_points = data_object.sample_curve(
                    self.BEZIER_CLIPPING_SAMPLES_PER_SEGMENT
                )
                if len(sampled_points) < 2:
                    return None, False  # Cannot form segments

                clipped_polyline_points: List[Point] = []
                for i in range(len(sampled_points) - 1):
                    p1 = (sampled_points[i].x(), sampled_points[i].y())
                    p2 = (sampled_points[i + 1].x(), sampled_points[i + 1].y())
                    clipped_segment = clipper_func(p1, p2, clip_rect_tuple)
                    if clipped_segment:
                        # Add points of the clipped segment, avoiding duplicates
                        start_pt = Point(
                            clipped_segment[0][0],
                            clipped_segment[0][1],
                            data_object.color,
                        )
                        end_pt = Point(
                            clipped_segment[1][0],
                            clipped_segment[1][1],
                            data_object.color,
                        )
                        if not clipped_polyline_points or not (
                            math.isclose(clipped_polyline_points[-1].x, start_pt.x)
                            and math.isclose(clipped_polyline_points[-1].y, start_pt.y)
                        ):
                            clipped_polyline_points.append(start_pt)
                        # Always add end point unless it's identical to the start (shouldn't happen often with clipping)
                        if not (
                            math.isclose(start_pt.x, end_pt.x)
                            and math.isclose(start_pt.y, end_pt.y)
                        ):
                            clipped_polyline_points.append(end_pt)

                if len(clipped_polyline_points) >= 2:
                    # Result is an open Polygon (polyline)
                    clipped_result = Polygon(
                        clipped_polyline_points, is_open=True, color=data_object.color
                    )
                    # Type changed from BezierCurve to Polygon, item needs replacement
                    needs_replacement = True

            return clipped_result, needs_replacement

        except Exception as e:
            print(f"Erro durante o clipping de {type(data_object).__name__}: {e}")
            # import traceback
            # traceback.print_exc() # Uncomment for detailed debug info
            self._set_status_message(
                f"Aviso: Erro ao clipar {type(data_object).__name__}.", 3000
            )
            return None, False

    def _get_clip_rect_tuple(self) -> clp.ClipRect:
        """Obtém a tupla de clip (xmin, ymin, xmax, ymax) do StateManager, garantindo ordem."""
        rect = self._state_manager.clip_rect()  # Already normalized by StateManager
        # QRectF provides left(), top(), right(), bottom() correctly ordered
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _add_data_object_to_scene(self, data_object: DataObject):
        """Recebe um objeto, aplica clipping e adiciona o resultado à cena. Manages item map."""
        clipped_data_object, _ = self._clip_data_object(
            data_object
        )  # Ignore replacement flag here

        if clipped_data_object:
            try:
                # Create graphics item from the CLIPPED data
                graphics_item = clipped_data_object.create_graphics_item()
                # Associate the CLIPPED data object with the graphics item
                graphics_item.setData(0, clipped_data_object)
                self._scene.addItem(graphics_item)
                # Add to lookup map
                self._data_object_to_item_map[clipped_data_object] = graphics_item
                self._state_manager.mark_as_modified()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro ao Criar Item Gráfico",
                    f"Não foi possível criar item gráfico para {type(clipped_data_object).__name__} pós-clip: {e}",
                )
        # else: object was completely clipped out or error occurred

    def _delete_selected_items(self):
        """Remove os itens gráficos selecionados da cena e do lookup map."""
        selected = self._scene.selectedItems()
        if not selected:
            self._set_status_message("Nenhum item selecionado para excluir.", 2000)
            return

        items_deleted = 0
        for item in selected:
            # Skip special items like the viewport rectangle
            if item.data(0) == "viewport_rect":
                continue
            if item.scene():  # Check if still in scene
                # Remove from lookup map *before* removing from scene
                data_obj = item.data(0)
                if data_obj in self._data_object_to_item_map:
                    del self._data_object_to_item_map[data_obj]
                else:
                    # This might happen if item was added outside _add_data_object_to_scene
                    print(
                        f"Aviso: Objeto de dados para o item {item} não encontrado no mapa ao excluir."
                    )

                self._scene.removeItem(item)
                items_deleted += 1

        if items_deleted > 0:
            # self._scene.update() # Implicitly updated by removeItem? Might need explicit update.
            self.centralWidget().viewport().update()  # Force viewport redraw
            self._state_manager.mark_as_modified()
            self._set_status_message(f"{items_deleted} item(ns) excluído(s).", 2000)

    def _clear_scene_confirmed(self):
        """Limpa todos os itens da cena (exceto viewport) e reseta estado e map."""
        self._drawing_controller.cancel_current_drawing()
        self._scene.clearSelection()
        items_to_remove = [
            item for item in self._scene.items() if item.data(0) != "viewport_rect"
        ]
        for item in items_to_remove:
            self._scene.removeItem(item)

        # Clear the lookup map as well
        self._data_object_to_item_map.clear()

        self._scene.update()
        self._reset_view()  # Reset view transform and center
        self._state_manager.mark_as_saved()
        self._state_manager.set_current_filepath(None)
        self._set_status_message("Nova cena criada.", 2000)

    # --- Ações e Diálogos ---

    def _prompt_clear_scene(self):
        """Pergunta ao usuário se deseja limpar a cena, verificando alterações."""
        self._drawing_controller.cancel_current_drawing()
        if self._check_unsaved_changes("limpar a cena"):
            self._clear_scene_confirmed()

    def _select_drawing_color(self):
        """Abre diálogo para selecionar a cor de desenho."""
        initial_color = self._state_manager.draw_color()
        new_color = QColorDialog.getColor(
            initial_color, self, "Selecionar Cor de Desenho"
        )
        if new_color.isValid():
            self._state_manager.set_draw_color(new_color)

    def _set_status_message(self, message: str, timeout: int = 3000):
        """Exibe uma mensagem temporária na barra de status usando o timer reutilizável."""
        if not hasattr(self, "_ui_manager") or self._ui_manager is None:
            return  # Avoid error during init/shutdown
        self._ui_manager.update_status_bar_message(message)
        # Stop any previous timer and start new one if timeout > 0
        self._status_reset_timer.stop()
        if timeout > 0:
            self._status_reset_timer.start(timeout)

    def _update_window_title(self, *args):
        """Atualiza o título da janela com base no estado (arquivo, modificações)."""
        # Args parameter allows connection to signals with arbitrary arguments
        title = "Editor Gráfico 2D - "
        filepath = self._state_manager.current_filepath()
        filename = os.path.basename(filepath) if filepath else "Nova Cena"
        title += filename
        if self._state_manager.has_unsaved_changes():
            title += " *"  # Indicator for unsaved changes
        self.setWindowTitle(title)

    def _check_unsaved_changes(self, action_description: str = "prosseguir") -> bool:
        """Verifica alterações não salvas e pergunta ao usuário como proceder."""
        if not self._state_manager.has_unsaved_changes():
            return True  # No unsaved changes, safe to proceed

        reply = QMessageBox.warning(
            self,
            "Alterações Não Salvas",
            f"A cena contém alterações não salvas. Deseja salvá-las antes de {action_description}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )  # Default button

        if reply == QMessageBox.Save:
            # Attempt to save; return True if save succeeded, False otherwise
            return self._save_current_file()
        elif reply == QMessageBox.Discard:
            return True  # User chose to discard changes
        else:  # reply == QMessageBox.Cancel or dialog closed
            return False  # User cancelled the action

    def _open_coordinate_input_dialog(self):
        """Abre diálogo para adicionar formas via coordenadas numéricas."""
        self._drawing_controller.cancel_current_drawing()
        dialog_mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
            DrawingMode.BEZIER: "bezier",
        }
        # Default to current editor mode, or polygon if in Select/Pan
        default_mode = dialog_mode_map.get(
            self._state_manager.drawing_mode(), "polygon"
        )

        dialog = CoordinateInputDialog(self, mode=default_mode)
        dialog.set_initial_color(self._state_manager.draw_color())

        if dialog.exec_() == QDialog.Accepted:
            try:
                result_data = dialog.get_validated_data()
                if result_data:
                    # Use the mode the dialog was actually in (might differ from editor state)
                    actual_dialog_mode = dialog.mode
                    self._add_item_from_validated_data(result_data, actual_dialog_mode)
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    "Erro ao Criar Objeto",
                    f"Não foi possível criar o objeto: {e}",
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro Interno",
                    f"Erro inesperado ao processar dados do diálogo: {e}",
                )

    def _add_item_from_validated_data(
        self, result_data: Dict[str, Any], dialog_mode_str: str
    ):
        """Cria e adiciona um objeto à cena a partir dos dados validados do diálogo."""
        try:
            data_object = self._create_data_object_from_dialog(
                result_data, dialog_mode_str
            )
            if data_object:
                self._add_data_object_to_scene(
                    data_object
                )  # Handles clipping and map update
            else:
                # Validation should prevent this, but as a safeguard
                raise ValueError(
                    f"Falha interna ao criar objeto do tipo '{dialog_mode_str}'"
                )
        except ValueError as e:
            raise ValueError(
                f"Erro ao processar dados do diálogo: {e}"
            )  # Re-raise for caller

    def _create_data_object_from_dialog(
        self, result_data: Dict[str, Any], dialog_mode_str: str
    ) -> Optional[DataObject]:
        """Helper para criar objeto a partir dos resultados validados do diálogo."""
        color = result_data.get("color", QColor(Qt.black))
        coords = result_data.get("coords", [])
        if not coords:
            raise ValueError("Coordenadas ausentes nos dados validados.")

        try:
            if dialog_mode_str == "point":
                if len(coords) != 1:
                    raise ValueError("Dados de ponto inválidos (esperado 1 par).")
                return Point(coords[0][0], coords[0][1], color=color)
            elif dialog_mode_str == "line":
                if len(coords) < 2:
                    raise ValueError("Dados de linha inválidos (esperado 2 pares).")
                start_pt = Point(coords[0][0], coords[0][1], color=color)
                end_pt = Point(coords[1][0], coords[1][1], color=color)
                return Line(start_pt, end_pt, color=color)
            elif dialog_mode_str == "polygon":
                is_open = result_data.get("is_open", False)
                is_filled = result_data.get("is_filled", False)
                poly_pts = [Point(x, y, color=color) for x, y in coords]
                # Validation of min points happens in Polygon.__init__
                return Polygon(
                    poly_pts, is_open=is_open, color=color, is_filled=is_filled
                )
            elif dialog_mode_str == "bezier":
                bezier_pts = [Point(x, y, color=color) for x, y in coords]
                # Validation of point count happens in BezierCurve.__init__
                return BezierCurve(bezier_pts, color=color)
            else:
                raise ValueError(
                    f"Modo de criação de diálogo desconhecido: {dialog_mode_str}"
                )
        except (
            ValueError
        ) as e:  # Catch errors from model constructors (e.g., not enough points)
            raise ValueError(f"Erro ao criar objeto {dialog_mode_str}: {e}")

    def _open_transformation_dialog(self):
        """Abre diálogo para aplicar transformações ao item selecionado."""
        selected_items = [
            item
            for item in self._scene.selectedItems()
            if item.data(0) != "viewport_rect"
        ]

        if len(selected_items) != 1:
            QMessageBox.warning(
                self,
                "Seleção Inválida",
                "Selecione exatamente UM objeto para transformar.",
            )
            return

        graphics_item = selected_items[0]
        # Retrieve the associated DataObject using the lookup map for efficiency
        data_object = self._find_data_object_for_item(graphics_item)

        # Check if data object is valid and transformable
        if not isinstance(data_object, DATA_OBJECT_TYPES):
            type_name = type(data_object).__name__ if data_object else "Nenhum/Inválido"
            QMessageBox.warning(
                self,
                "Item Não Transformável",
                f"O item selecionado ({type_name}) não pode ser transformado ou não tem dados válidos associados.",
            )
            return

        self._drawing_controller.cancel_current_drawing()
        # Pass the *original* data object to the transformation controller
        self._transformation_controller.request_transformation(data_object)

    def _handle_object_transformed(self, transformed_data_object: DataObject):
        """
        Atualiza o item gráfico correspondente após a transformação do seu DataObject,
        incluindo re-clipping e potential item replacement.
        """
        if not isinstance(transformed_data_object, DATA_OBJECT_TYPES):
            print(
                f"AVISO: Sinal object_transformed com tipo inesperado: {type(transformed_data_object)}"
            )
            return

        # Find the QGraphicsItem associated with this transformed DataObject using the map
        graphics_item = self._find_graphics_item_for_object(transformed_data_object)

        if not graphics_item or not graphics_item.scene():
            print(
                f"AVISO: Item gráfico não encontrado ou fora da cena para {transformed_data_object} após transformação."
            )
            # Object might have been deleted between transformation and signal handling
            return

        # Re-clip the transformed data object and check if type changed
        clipped_data_object, needs_replacement = self._clip_data_object(
            transformed_data_object
        )

        # Update the scene based on clipping result
        if clipped_data_object is None:
            # Object clipped out completely, remove the item from scene and map
            if transformed_data_object in self._data_object_to_item_map:
                del self._data_object_to_item_map[transformed_data_object]
            self._scene.removeItem(graphics_item)
            self._set_status_message(
                "Objeto movido/transformado para fora da viewport.", 2000
            )
            self._state_manager.mark_as_modified()
        else:
            # Object still (partially) visible. Update or replace the item.
            try:
                if needs_replacement:
                    # Remove old item from scene and map
                    if transformed_data_object in self._data_object_to_item_map:
                        del self._data_object_to_item_map[transformed_data_object]
                    self._scene.removeItem(graphics_item)
                    # Add the new clipped item (which also adds to map)
                    self._add_data_object_to_scene(clipped_data_object)
                    # Note: _add_data_object_to_scene already marks modified
                else:
                    # Type is the same, update the existing item in place
                    graphics_item.prepareGeometryChange()  # Notify item about geometry change
                    # Update the data association ONLY IF the object instance is the same
                    # If clipping returned a new instance (even of same type), map needs update
                    if clipped_data_object is not transformed_data_object:
                        # Remove old mapping, add new mapping
                        if transformed_data_object in self._data_object_to_item_map:
                            del self._data_object_to_item_map[transformed_data_object]
                        self._data_object_to_item_map[clipped_data_object] = (
                            graphics_item
                        )
                        graphics_item.setData(
                            0, clipped_data_object
                        )  # Associate new clipped data
                    # else: data object instance is the same, map is still valid

                    # Update item's visual representation
                    self._update_graphics_item_geometry(
                        graphics_item, clipped_data_object
                    )
                    self._apply_style_to_item(graphics_item, clipped_data_object)
                    graphics_item.update()  # Request redraw of the item
                    self._state_manager.mark_as_modified()

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro ao Atualizar Gráfico Pós-Transformação",
                    f"Falha ao atualizar item {type(graphics_item).__name__} após clipping: {e}",
                )

    def _find_graphics_item_for_object(
        self, data_obj: DataObject
    ) -> Optional[QGraphicsItem]:
        """Finds the QGraphicsItem using the lookup map (O(1))."""
        return self._data_object_to_item_map.get(data_obj)

    def _find_data_object_for_item(self, item: QGraphicsItem) -> Optional[DataObject]:
        """Finds the DataObject associated with a QGraphicsItem."""
        data = item.data(0)
        if isinstance(data, DATA_OBJECT_TYPES):
            return data
        return None

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        """Atualiza a geometria do item gráfico com base no DataObject associado."""
        # This function assumes the item type matches the data type (or is compatible, e.g., PathItem for Bezier)
        # It's called *after* handling potential type changes in _handle_object_transformed
        try:
            if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
                size, offset = data.GRAPHICS_SIZE, data.GRAPHICS_SIZE / 2.0
                new_rect = QRectF(data.x - offset, data.y - offset, size, size)
                if item.rect() != new_rect:
                    item.setRect(new_rect)
            elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
                new_line = QLineF(data.start.to_qpointf(), data.end.to_qpointf())
                if item.line() != new_line:
                    item.setLine(new_line)
            elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
                # Handles polygons created normally or from clipped Beziers
                new_polygon_qf = QPolygonF([p.to_qpointf() for p in data.points])
                if item.polygon() != new_polygon_qf:
                    item.setPolygon(new_polygon_qf)
            elif isinstance(data, Polygon) and isinstance(item, QGraphicsPathItem):
                # Case where a clipped Bezier (now a Polygon) is represented by a PathItem
                new_path = QPainterPath()
                if data.points:
                    new_path.addPolygon(
                        QPolygonF([p.to_qpointf() for p in data.points])
                    )
                if item.path() != new_path:
                    item.setPath(new_path)
            elif isinstance(data, BezierCurve) and isinstance(item, QGraphicsPathItem):
                # Recreate the cubic path for Bezier
                new_path = QPainterPath()
                if data.points:
                    new_path.moveTo(data.points[0].to_qpointf())
                    num_segments = data.get_num_segments()
                    for i in range(num_segments):
                        p1_idx, p2_idx, p3_idx = 3 * i + 1, 3 * i + 2, 3 * i + 3
                        if p3_idx < len(data.points):
                            ctrl1 = data.points[p1_idx].to_qpointf()
                            ctrl2 = data.points[p2_idx].to_qpointf()
                            endpt = data.points[p3_idx].to_qpointf()
                            new_path.cubicTo(ctrl1, ctrl2, endpt)
                if item.path() != new_path:
                    item.setPath(new_path)

        except Exception as e:
            print(
                f"ERRO _update_graphics_item_geometry para {type(data).__name__} / {type(item).__name__}: {e}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, data: DataObject):
        """Reaplica o estilo (cor, preenchimento, etc.) ao item gráfico."""
        if not hasattr(data, "color"):
            return  # Cannot style without color attribute
        color = (
            data.color
            if isinstance(data.color, QColor) and data.color.isValid()
            else QColor(Qt.black)
        )
        # Initialize with defaults (or current item's style?)
        pen = QPen(item.pen() if hasattr(item, "pen") else QPen(Qt.NoPen))
        brush = QBrush(item.brush() if hasattr(item, "brush") else QBrush(Qt.NoBrush))

        # Determine new style based on data object type
        if isinstance(data, Point):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(data, Line):
            pen = QPen(color, data.GRAPHICS_WIDTH, Qt.SolidLine)
            brush = QBrush(Qt.NoBrush)
        elif isinstance(data, Polygon):
            pen = QPen(color, data.GRAPHICS_BORDER_WIDTH)
            if data.is_open:  # Polyline (potentially from clipped Bezier)
                pen.setStyle(Qt.DashLine)
                brush.setStyle(Qt.NoBrush)
            else:  # Closed Polygon
                pen.setStyle(Qt.SolidLine)
                if data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color)
                    fill_color.setAlphaF(data.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
                else:
                    brush.setStyle(Qt.NoBrush)
        elif isinstance(data, BezierCurve):
            pen = QPen(color, data.GRAPHICS_WIDTH, Qt.SolidLine)
            brush = QBrush(Qt.NoBrush)

        # Apply style only if it has changed and the item supports it
        if hasattr(item, "setPen") and pen is not None and item.pen() != pen:
            item.setPen(pen)
        if hasattr(item, "setBrush") and brush is not None and item.brush() != brush:
            item.setBrush(brush)

    # --- Importação/Exportação OBJ ---

    def _prompt_load_obj(self):
        """Abre diálogo para carregar um arquivo Wavefront OBJ."""
        if not self._check_unsaved_changes("carregar um novo arquivo"):
            return
        obj_filepath = self._io_handler.prompt_load_obj()
        if obj_filepath:
            self._load_obj_file(obj_filepath, clear_before_load=True)

    def _load_obj_file(self, obj_filepath: str, clear_before_load: bool = True):
        """Carrega e processa um arquivo Wavefront OBJ."""
        self._set_status_message(f"Carregando {os.path.basename(obj_filepath)}...", 0)
        QApplication.processEvents()  # Update UI to show status message

        # 1. Read OBJ and potentially associated MTL data
        obj_lines, material_colors, mtl_warnings = self._read_obj_and_mtl_data(
            obj_filepath
        )
        if obj_lines is None:  # Reading failed (error already shown by IOHandler)
            self._set_status_message("Falha ao ler arquivo(s) OBJ/MTL.")
            return

        # 2. Parse OBJ data into internal DataObjects
        # Note: Bezier curves will not be created by parser from standard OBJ
        parsed_objects, obj_warnings = self._object_manager.parse_obj_data(
            obj_lines,
            material_colors,
            self._state_manager.draw_color(),  # Use current draw color as default
        )

        # 3. Prepare scene (clear if requested)
        if clear_before_load:
            # This also clears the object map
            self._clear_scene_confirmed()

        # 4. Add parsed objects to the scene (handles clipping and map update)
        num_added, num_clipped_out = self._add_parsed_objects_to_scene(parsed_objects)

        # 5. Report results (number added, clipped, warnings)
        self._report_load_results(
            obj_filepath, num_added, num_clipped_out, mtl_warnings + obj_warnings
        )

        # 6. Update application state
        self._state_manager.set_current_filepath(obj_filepath)
        self._state_manager.mark_as_saved()  # Mark as saved immediately after load

    def _read_obj_and_mtl_data(
        self, obj_filepath: str
    ) -> Tuple[Optional[List[str]], Dict[str, QColor], List[str]]:
        """Lê as linhas do arquivo OBJ e os dados do arquivo MTL associado."""
        all_warnings: List[str] = []
        material_colors: Dict[str, QColor] = {}

        # Read OBJ lines and get relative MTL filename (if any)
        read_result = self._io_handler.read_obj_lines(obj_filepath)
        if read_result is None:
            return None, {}, ["Falha ao ler arquivo OBJ."]  # Error handled by IOHandler
        obj_lines, mtl_filename_relative = read_result

        # Read MTL file if referenced
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            # Construct full path, normalizing separators
            mtl_filepath_full = os.path.normpath(
                os.path.join(obj_dir, mtl_filename_relative)
            )
            if os.path.exists(mtl_filepath_full):
                # IOHandler reads MTL, returns colors and warnings
                material_colors, mtl_read_warnings = self._io_handler.read_mtl_file(
                    mtl_filepath_full
                )
                all_warnings.extend(mtl_read_warnings)
            else:
                # File referenced in OBJ doesn't exist
                all_warnings.append(
                    f"Arquivo MTL '{mtl_filename_relative}' referenciado não encontrado em '{obj_dir}'."
                )

        return obj_lines, material_colors, all_warnings

    def _add_parsed_objects_to_scene(
        self, parsed_objects: List[DataObject]
    ) -> Tuple[int, int]:
        """Adiciona uma lista de DataObjects parseados à cena, contando resultados."""
        num_added = 0
        num_clipped_out = 0
        for data_obj in parsed_objects:
            # Store item count before adding to see if it increases
            item_count_before = len(self._data_object_to_item_map)
            self._add_data_object_to_scene(data_obj)  # Handles clipping & map update
            item_count_after = len(self._data_object_to_item_map)

            if item_count_after > item_count_before:
                num_added += 1
            elif item_count_after == item_count_before and not isinstance(
                data_obj, Point
            ):
                # If count didn't increase and it wasn't a point (which might just be clipped),
                # assume Line/Polygon/Bezier was completely clipped out.
                num_clipped_out += 1

        if num_added > 0:
            self._scene.update()  # Update scene if items were added
        return num_added, num_clipped_out

    def _report_load_results(
        self,
        obj_filepath: str,
        num_added: int,
        num_clipped_out: int,
        warnings: List[str],
    ):
        """Exibe mensagens resumindo o resultado do carregamento do arquivo OBJ."""
        base_filename = os.path.basename(obj_filepath)
        # Case 1: Nothing added, no warnings (likely empty or unsupported file)
        if num_added == 0 and num_clipped_out == 0 and not warnings:
            msg = f"Nenhum objeto geométrico suportado (v,l,f,p) encontrado ou adicionado de '{base_filename}'."
            # Check if file actually exists and has content, otherwise it was truly empty
            if os.path.exists(obj_filepath) and os.path.getsize(obj_filepath) > 0:
                QMessageBox.information(self, "Arquivo Vazio ou Não Suportado", msg)
            self._set_status_message(
                "Carregamento concluído (sem geometria adicionada)."
            )
        # Case 2: Objects added or clipped, potentially with warnings
        else:
            final_message = f"Carregado: {num_added} objeto(s) de '{base_filename}'."
            if num_clipped_out > 0:
                final_message += f" ({num_clipped_out} totalmente fora da viewport)"
            if warnings:
                # Limit number of warnings shown in popup for readability
                max_warnings_in_popup = 15
                formatted_warnings = "- " + "\n- ".join(
                    warnings[:max_warnings_in_popup]
                )
                if len(warnings) > max_warnings_in_popup:
                    formatted_warnings += (
                        f"\n- ... ({len(warnings) - max_warnings_in_popup} mais avisos)"
                    )
                QMessageBox.warning(
                    self,
                    "Carregado com Avisos",
                    f"{final_message}\n\nAvisos:\n{formatted_warnings}",
                )
                final_message += " (com avisos)"
            self._set_status_message(final_message)

    def _prompt_save_as_obj(self) -> bool:
        """Abre diálogo "Salvar Como" para arquivos OBJ."""
        self._drawing_controller.cancel_current_drawing()
        current_path = self._state_manager.current_filepath()
        default_name = (
            os.path.basename(current_path) if current_path else "nova_cena.obj"
        )

        # IOHandler returns base path (without extension) selected by user
        base_filepath = self._io_handler.prompt_save_obj(default_name)
        if not base_filepath:
            self._set_status_message("Salvar cancelado.")
            return False  # User cancelled

        # Attempt to save using the base path
        if self._save_to_file(base_filepath):
            # If save succeeded, update state with the full path (.obj added)
            self._state_manager.set_current_filepath(base_filepath + ".obj")
            self._state_manager.mark_as_saved()
            return True
        else:
            # Save failed (error message already shown by _save_to_file or IOHandler)
            self._set_status_message("Falha ao salvar.")
            return False

    def _save_current_file(self) -> bool:
        """Salva no arquivo atual ou chama 'Salvar Como' se não houver arquivo."""
        current_path = self._state_manager.current_filepath()
        if not current_path:
            # No current file, delegate to Save As
            return self._prompt_save_as_obj()
        else:
            # Has a current file, save directly
            self._drawing_controller.cancel_current_drawing()
            # Get base path (without extension) from the current path
            base_filepath, _ = os.path.splitext(current_path)
            if self._save_to_file(base_filepath):
                self._state_manager.mark_as_saved()  # Mark saved on successful overwrite
                return True
            else:
                return False  # Save failed (error message already shown)

    def _save_to_file(self, base_filepath: str) -> bool:
        """Salva a cena atual nos arquivos OBJ e MTL usando o base_filepath."""
        self._set_status_message(f"Salvando em {os.path.basename(base_filepath)}...", 0)
        QApplication.processEvents()  # Update UI

        # 1. Collect savable DataObjects from the scene using the map
        scene_data_objects = list(
            self._data_object_to_item_map.keys()
        )  # Get keys (DataObjects)
        if not scene_data_objects:
            # Don't show popup if scene is empty, just report status.
            # If overwriting, this effectively creates empty files.
            self._set_status_message("Nada para salvar (cena vazia).")
            # Write empty files? Or just return success? Let's write empty files.
            obj_ok = self._io_handler.write_obj_and_mtl(
                base_filepath, ["# Cena Vazia"], None
            )
            return obj_ok

        # 2. Generate OBJ and MTL content (approximates Beziers)
        mtl_filename = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, gen_warnings = self._object_manager.generate_obj_data(
            scene_data_objects, mtl_filename
        )

        # Check if generation itself failed (e.g., no vertices)
        if obj_lines is None:
            self._report_save_results(
                base_filepath, False, gen_warnings, is_generation_error=True
            )
            return False

        # 3. Write content to files using IOHandler
        write_success = self._io_handler.write_obj_and_mtl(
            base_filepath, obj_lines, mtl_lines
        )

        # 4. Report results (success/failure, warnings)
        has_mtl = mtl_lines is not None and len(mtl_lines) > 0
        self._report_save_results(
            base_filepath, write_success, gen_warnings, has_mtl=has_mtl
        )
        return write_success

    # Removed _collect_scene_data_objects as we now use the map directly

    def _report_save_results(
        self,
        base_filepath: str,
        success: bool,
        warnings: List[str],
        has_mtl: bool = False,
        is_generation_error: bool = False,
    ):
        """Exibe mensagens resumindo o resultado do salvamento."""
        base_filename = os.path.basename(base_filepath)
        if is_generation_error:
            msg = "Falha ao gerar dados OBJ/MTL para salvar."
            if warnings:
                msg += "\n\nAvisos:\n- " + "\n- ".join(warnings)
            QMessageBox.critical(self, "Erro na Geração de Arquivo", msg)
            self._set_status_message("Erro ao gerar arquivo(s).")
        elif success:
            obj_name = base_filename + ".obj"
            msg = f"Cena salva como '{obj_name}'"
            if has_mtl:
                msg += f" e '{base_filename}.mtl'"
            msg += "."
            # Show warnings popup only if warnings exist
            if warnings:
                max_warnings_in_popup = 15
                formatted = "\n\nAvisos:\n- " + "\n- ".join(
                    warnings[:max_warnings_in_popup]
                )
                if len(warnings) > max_warnings_in_popup:
                    formatted += (
                        f"\n- ... ({len(warnings) - max_warnings_in_popup} mais avisos)"
                    )
                QMessageBox.warning(self, "Salvo com Avisos", f"{msg}{formatted}")
                msg += " (com avisos)"
            self._set_status_message(msg)
        else:
            # IOHandler should have shown the critical write error
            self._set_status_message(
                f"Falha ao escrever arquivo(s) para '{base_filename}'."
            )

    # --- Viewport ---

    def _toggle_viewport_visibility(self, checked: bool):
        """Mostra ou oculta o retângulo visual do viewport."""
        self._clip_rect_item.setVisible(checked)
        # Keep the menu item state synchronized
        self._ui_manager.update_viewport_action_state(checked)

    def _update_clip_rect_item(self, rect: QRectF):
        """Atualiza a geometria do item gráfico do viewport quando o state muda."""
        # Ensure rect is normalized before comparing/setting
        normalized_rect = rect.normalized()
        if self._clip_rect_item.rect() != normalized_rect:
            self._clip_rect_item.setRect(normalized_rect)

    # --- Evento de Fechamento ---

    def closeEvent(self, event: QCloseEvent) -> None:
        """Chamado ao tentar fechar a janela principal."""
        # Ensure any drawing operation is cancelled first
        self._drawing_controller.cancel_current_drawing()
        # Check for unsaved changes and prompt user
        if self._check_unsaved_changes("fechar a aplicação"):
            event.accept()  # Allow closing
        else:
            event.ignore()  # Cancel closing
