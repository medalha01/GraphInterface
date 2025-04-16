# graphics_editor/editor.py
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
from PyQt5.QtWidgets import QApplication  # Importa QApplication para processEvents

# Importações relativas dentro do pacote
from .view.main_view import GraphicsView
from .models.point import Point
from .models.line import Line
from .models.polygon import Polygon
from .dialogs.coordinates_input import CoordinateInputDialog
from .dialogs.transformation_dialog import TransformationDialog
from .controllers.transformation_controller import (
    TransformationController,
)
from .io_handler import IOHandler
from .object_manager import ObjectManager
from .utils import clipping as clp

# Importações dos novos módulos
from .state_manager import EditorStateManager, DrawingMode, LineClippingAlgorithm
from .controllers.drawing_controller import DrawingController
from .ui_manager import UIManager

# Alias para tipos de dados dos modelos
DataObject = Union[Point, Line, Polygon]


class GraphicsEditor(QMainWindow):
    """Janela principal da aplicação para o editor gráfico 2D (Coordenador)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Gráfico 2D - Nova Cena")
        self.resize(1000, 750)

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
        # Define um retângulo de cena grande para permitir pan extensivo
        self._scene.setSceneRect(-10000, -10000, 20000, 20000)
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
        self._object_manager = ObjectManager()

    def _setup_special_items(self) -> None:
        """Inicializa itens especiais da cena como o retângulo do viewport."""
        self._clip_rect_item = QGraphicsRectItem(self._state_manager.clip_rect())
        self._clip_rect_item.setPen(QPen(QColor(0, 0, 255, 100), 1, Qt.DashLine))
        self._clip_rect_item.setBrush(QBrush(Qt.NoBrush))
        self._clip_rect_item.setZValue(-1)  # Garante que fique atrás dos outros itens
        self._scene.addItem(self._clip_rect_item)

    def _setup_ui_elements(self) -> None:
        """Configura os elementos principais da UI (menu, toolbar, status bar)."""
        self._setup_menu_bar()
        self._ui_manager.setup_toolbar(
            mode_callback=self._set_drawing_mode,
            color_callback=self._select_drawing_color,
            coord_callback=self._open_coordinate_input_dialog,
            transform_callback=self._open_transformation_dialog,
            clipper_callback=self._set_line_clipper,
        )
        self._ui_manager.setup_status_bar(zoom_callback=self._on_zoom_slider_changed)

    def _initialize_ui_state(self) -> None:
        """Define o estado inicial da UI após a configuração."""
        self._update_view_interaction()
        # Usa QTimer para garantir que a vista esteja totalmente inicializada
        QTimer.singleShot(0, self._update_view_controls)

    # --- Configuração da UI (Menus principalmente) ---

    def _get_icon(self, name: str) -> QIcon:
        """Reutiliza método do UIManager para carregar ícones."""
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
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # --- Menu Editar ---
        edit_menu = menubar.addMenu("&Editar")
        delete_action = QAction(
            QIcon.fromTheme("edit-delete", self._get_icon("delete.png")),
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
        # Guarda referência para poder atualizar estado checado
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

        # --- Vista -> Editor (Coordenação) ---
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(self._delete_selected_items)

        # --- Vista -> UI Manager (Atualização de Status) ---
        self._view.scene_mouse_moved.connect(self._ui_manager.update_status_bar_coords)
        self._view.rotation_changed.connect(self._update_view_controls)
        self._view.scale_changed.connect(self._update_view_controls)

        # --- StateManager -> UI Manager (Atualização da UI) ---
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
        # self._state_manager.clip_rect_changed.connect(self._update_clip_rect_item) # Descomentar se viewport for dinâmico

        # --- StateManager -> Editor (Lógica de Interação) ---
        self._state_manager.drawing_mode_changed.connect(self._update_view_interaction)
        self._state_manager.drawing_mode_changed.connect(
            self._drawing_controller.cancel_current_drawing
        )

        # --- DrawingController -> Editor (Adicionar Objeto Finalizado) ---
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
        """Decide se passa o clique para o DrawingController ou para a Vista."""
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.POINT, DrawingMode.LINE, DrawingMode.POLYGON]:
            self._drawing_controller.handle_scene_left_click(scene_pos)
        # Outros modos (SELECT, PAN) são gerenciados pela própria QGraphicsView

    def _handle_scene_right_click(self, scene_pos: QPointF):
        """Decide se passa o clique direito para o DrawingController."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.POLYGON:
            self._drawing_controller.handle_scene_right_click(scene_pos)
        # Outros modos podem ter menu de contexto no futuro

    def _handle_scene_mouse_move(self, scene_pos: QPointF):
        """Passa o movimento para o DrawingController se estiver desenhando."""
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.LINE, DrawingMode.POLYGON]:
            self._drawing_controller.handle_scene_mouse_move(scene_pos)
        # A atualização das coords no status bar é feita por conexão direta view -> uimanager

    # --- Controle de Modo e Interação ---

    def _set_drawing_mode(self, mode: DrawingMode):
        """Define o modo de desenho/interação através do StateManager."""
        self._state_manager.set_drawing_mode(mode)

    def _update_view_interaction(self):
        """Atualiza o modo de arrasto da vista com base no modo do StateManager."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
        elif mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
        else:  # Modos de desenho
            self._view.set_drag_mode(QGraphicsView.NoDrag)

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
        """Mapeia o valor do slider para a escala da vista."""
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX

        if max_slider == min_slider or max_scale <= min_scale:
            return  # Evita divisão por zero

        log_min, log_max = np.log(min_scale), np.log(max_scale)
        if log_max <= log_min:
            return  # Evita divisão por zero

        factor = (value - min_slider) / (max_slider - min_slider)
        target_scale = np.exp(log_min + factor * (log_max - log_min))

        # Aplica a escala, centralizando na posição atual (não no mouse)
        self._view.set_scale(target_scale, center_on_mouse=False)

    def _update_view_controls(self):
        """Atualiza os controles da UI (slider/labels) com base no estado da vista."""
        self._update_zoom_controls()
        self._update_rotation_controls()

    def _update_zoom_controls(self):
        """Atualiza o slider e label de zoom com base na escala da vista."""
        current_scale = self._view.get_scale()
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        slider_value = min_slider  # Valor padrão

        # Evita divisão por zero ou log(0)
        if max_scale > min_scale and max_slider > min_slider:
            log_min, log_max = np.log(min_scale), np.log(max_scale)
            if log_max > log_min:
                # Garante que a escala esteja dentro dos limites antes de calcular
                clamped_scale = np.clip(current_scale, min_scale, max_scale)
                log_scale = np.log(clamped_scale)
                factor = (log_scale - log_min) / (log_max - log_min)
                slider_value = int(
                    round(min_slider + factor * (max_slider - min_slider))
                )

        self._ui_manager.update_status_bar_zoom(current_scale, slider_value)

    def _update_rotation_controls(self):
        """Atualiza o label de rotação com base na rotação da vista."""
        rotation_angle = self._view.get_rotation_angle()
        self._ui_manager.update_status_bar_rotation(rotation_angle)

    def _reset_view(self):
        """Reseta a transformação (zoom, pan, rotação) da QGraphicsView."""
        self._view.reset_view()
        # Centraliza na área de viewport padrão após resetar
        self._view.centerOn(self._state_manager.clip_rect().center())
        # A vista emitirá sinais que atualizarão a UI

    # --- Gerenciamento de Objetos e Clipping ---

    def _clip_data_object(self, data_object: DataObject) -> Optional[DataObject]:
        """
        Recorta um objeto de dados (Point, Line, Polygon) contra o viewport atual.

        Retorna:
            Um novo DataObject recortado se estiver (parcialmente) dentro,
            ou None se estiver completamente fora ou ocorrer erro.
        """
        clipped_data_object: Optional[DataObject] = None
        clip_rect_tuple = self._get_clip_rect_tuple()
        clipper_algo = self._state_manager.selected_line_clipper()

        try:
            if isinstance(data_object, Point):
                clipped_coords = clp.clip_point(
                    data_object.get_coords(), clip_rect_tuple
                )
                if clipped_coords:
                    clipped_data_object = Point(
                        clipped_coords[0], clipped_coords[1], data_object.color
                    )
            elif isinstance(data_object, Line):
                clipper_func = (
                    clp.cohen_sutherland
                    if clipper_algo == LineClippingAlgorithm.COHEN_SUTHERLAND
                    else clp.liang_barsky
                )
                clipped_segment = clipper_func(
                    data_object.start.get_coords(),
                    data_object.end.get_coords(),
                    clip_rect_tuple,
                )
                if clipped_segment:
                    p1, p2 = clipped_segment
                    start_pt = Point(p1[0], p1[1], data_object.start.color)
                    end_pt = Point(p2[0], p2[1], data_object.end.color)
                    clipped_data_object = Line(start_pt, end_pt, data_object.color)
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
                    clipped_data_object = Polygon(
                        clipped_points,
                        is_open=data_object.is_open,
                        color=data_object.color,
                        is_filled=data_object.is_filled,
                    )

            return clipped_data_object

        except Exception as e:
            print(f"Erro durante o clipping de {type(data_object).__name__}: {e}")
            self._set_status_message(
                f"Aviso: Erro ao clipar {type(data_object).__name__}.", 3000
            )
            return None

    def _get_clip_rect_tuple(self) -> clp.ClipRect:
        """Obtém a tupla de clip (xmin, ymin, xmax, ymax) do StateManager."""
        rect = self._state_manager.clip_rect()
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _add_data_object_to_scene(self, data_object: DataObject):
        """Recebe um objeto, aplica clipping e adiciona à cena."""
        clipped_data_object = self._clip_data_object(data_object)

        if clipped_data_object:
            try:
                graphics_item = clipped_data_object.create_graphics_item()
                # Associa o objeto de DADOS (já recortado) ao item gráfico
                graphics_item.setData(0, clipped_data_object)
                self._scene.addItem(graphics_item)
                self._state_manager.mark_as_modified()
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro ao Criar Item Gráfico",
                    f"Não foi possível criar item gráfico para {type(clipped_data_object).__name__} pós-clip: {e}",
                )
                print(f"Erro detalhes criação: {e}")
        # Se clipped_data_object for None, o objeto está fora ou houve erro no clip

    def _delete_selected_items(self):
        """Remove os itens gráficos selecionados da cena."""
        selected = self._scene.selectedItems()
        if not selected:
            self._set_status_message("Nenhum item selecionado para excluir.", 2000)
            return

        items_deleted = 0
        for item in selected:
            if item is self._clip_rect_item:
                continue  # Não exclui viewport
            if item.scene():  # Verifica se ainda está na cena
                # Idealmente, removeria o DataObject associado de uma lista central, se houver
                self._scene.removeItem(item)
                items_deleted += 1

        if items_deleted > 0:
            self._scene.update()
            self._state_manager.mark_as_modified()
            self._set_status_message(f"{items_deleted} item(ns) excluído(s).", 2000)

    def _clear_scene_confirmed(self):
        """Limpa todos os itens da cena (exceto viewport) e reseta estado."""
        self._drawing_controller.cancel_current_drawing()
        self._scene.clearSelection()
        items_to_remove = [
            item for item in self._scene.items() if item is not self._clip_rect_item
        ]
        for item in items_to_remove:
            self._scene.removeItem(item)

        self._scene.update()
        self._reset_view()
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
        """Exibe uma mensagem temporária na barra de status."""
        self._ui_manager.update_status_bar_message(message)
        if timeout > 0:
            QTimer.singleShot(
                timeout, lambda: self._ui_manager.update_status_bar_message("Pronto.")
            )

    def _update_window_title(self, *args):
        """Atualiza o título da janela com base no estado (arquivo, modificações)."""
        title = "Editor Gráfico 2D - "
        filepath = self._state_manager.current_filepath()
        filename = os.path.basename(filepath) if filepath else "Nova Cena"
        title += filename
        if self._state_manager.has_unsaved_changes():
            title += " *"
        self.setWindowTitle(title)

    def _check_unsaved_changes(self, action_description: str = "prosseguir") -> bool:
        """Verifica alterações não salvas e pergunta ao usuário como proceder."""
        if not self._state_manager.has_unsaved_changes():
            return True

        reply = QMessageBox.warning(
            self,
            "Alterações Não Salvas",
            f"A cena contém alterações não salvas. Deseja salvá-las antes de {action_description}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,  # Botão padrão
        )

        if reply == QMessageBox.Save:
            return (
                self._save_current_file()
            )  # Tenta salvar, retorna sucesso/falha do salvamento
        elif reply == QMessageBox.Discard:
            return True  # Pode prosseguir descartando
        else:  # reply == QMessageBox.Cancel
            return False  # Não prosseguir com a ação

    def _open_coordinate_input_dialog(self):
        """Abre diálogo para adicionar formas via coordenadas numéricas."""
        self._drawing_controller.cancel_current_drawing()
        dialog_mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
        }
        # Usa o modo atual como padrão, ou polígono se modo for SELECT/PAN
        dialog_mode_str = dialog_mode_map.get(
            self._state_manager.drawing_mode(), "polygon"
        )
        dialog = CoordinateInputDialog(self, mode=dialog_mode_str)
        dialog.set_initial_color(self._state_manager.draw_color())

        if dialog.exec_() == QDialog.Accepted:
            try:
                result_data = dialog.get_validated_data()
                if result_data:
                    self._add_item_from_validated_data(result_data, dialog_mode_str)
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
                print(f"Detalhes erro diálogo: {e}")  # Log para depuração

    def _add_item_from_validated_data(self, result_data: Any, dialog_mode_str: str):
        """Cria e adiciona um objeto à cena a partir dos dados validados do diálogo."""
        try:
            data_object = self._create_data_object_from_dialog(
                result_data, dialog_mode_str
            )
            if data_object:
                self._add_data_object_to_scene(data_object)
            else:
                # Deve ser prevenido pela validação anterior
                raise ValueError(
                    f"Falha interna ao criar objeto do tipo '{dialog_mode_str}'"
                )
        except ValueError as e:
            # Re-levanta para o chamador (_open_coordinate_input_dialog) mostrar o erro
            raise ValueError(f"Erro ao processar dados do diálogo: {e}")

    def _create_data_object_from_dialog(
        self, result_data: Dict[str, Any], dialog_mode_str: str
    ) -> Optional[DataObject]:
        """Helper para criar Point, Line, ou Polygon a partir dos resultados validados do diálogo."""
        color = result_data.get("color", QColor(Qt.black))
        coords = result_data.get("coords", [])
        if not coords:
            raise ValueError("Coordenadas ausentes nos dados validados.")

        if dialog_mode_str == "point":
            if len(coords) != 1:
                raise ValueError("Dados de ponto inválidos (esperado 1 par de coords).")
            return Point(coords[0][0], coords[0][1], color=color)
        elif dialog_mode_str == "line":
            if len(coords) < 2:
                raise ValueError(
                    "Dados de linha inválidos (esperado 2 pares de coords)."
                )
            start_pt = Point(coords[0][0], coords[0][1], color=color)
            end_pt = Point(coords[1][0], coords[1][1], color=color)
            return Line(start_pt, end_pt, color=color)
        elif dialog_mode_str == "polygon":
            is_open = result_data.get("is_open", False)
            is_filled = result_data.get("is_filled", False)
            min_pts = 2 if is_open else 3
            if len(coords) < min_pts:
                raise ValueError(
                    f"Pontos insuficientes ({len(coords)}/{min_pts}) para polígono {'aberto' if is_open else 'fechado'}."
                )
            poly_pts = [Point(x, y, color=color) for x, y in coords]
            return Polygon(poly_pts, is_open=is_open, color=color, is_filled=is_filled)
        else:
            raise ValueError(
                f"Modo de criação de diálogo desconhecido: {dialog_mode_str}"
            )

    def _open_transformation_dialog(self):
        """Abre diálogo para aplicar transformações geométricas ao item selecionado."""
        selected_items = [
            item
            for item in self._scene.selectedItems()
            if item is not self._clip_rect_item
        ]

        if len(selected_items) != 1:
            QMessageBox.warning(
                self,
                "Seleção Inválida",
                "Selecione exatamente UM objeto para transformar.",
            )
            return

        graphics_item = selected_items[0]
        data_object = graphics_item.data(0)  # Pega o DataObject associado

        if not isinstance(data_object, (Point, Line, Polygon)):
            type_name = type(data_object).__name__ if data_object else "Nenhum"
            QMessageBox.critical(
                self,
                "Erro Interno",
                f"Item selecionado sem dados válidos ({type_name}) ou não transformável.",
            )
            return

        self._drawing_controller.cancel_current_drawing()
        # Passa o objeto de DADOS para o controlador de transformação
        self._transformation_controller.request_transformation(data_object)
        # O controlador emitirá 'object_transformed' se a transformação for aplicada

    def _handle_object_transformed(self, transformed_data_object: DataObject):
        """
        Atualiza o item gráfico correspondente após a transformação, incluindo re-clipping.
        """
        if not isinstance(transformed_data_object, (Point, Line, Polygon)):
            print(
                f"AVISO: Sinal object_transformed com tipo inesperado: {type(transformed_data_object)}"
            )
            return

        # Encontra o QGraphicsItem original (antes do clipping pós-transformação)
        graphics_item = self._find_graphics_item_for_object(transformed_data_object)

        if not graphics_item:
            print(
                f"AVISO: Item gráfico não encontrado para {transformed_data_object} após transformação (antes do clip)."
            )
            return  # Não há o que atualizar

        if not graphics_item.scene():
            print(
                f"AVISO: Item {graphics_item} encontrado, mas não está mais na cena (antes do clip)."
            )
            return  # Já foi removido por outra ação

        # Recorta o objeto de dados *já transformado*
        clipped_data_object = self._clip_data_object(transformed_data_object)

        # Atualiza a cena com base no resultado do clipping
        if clipped_data_object is None:
            # Objeto foi completamente clipado, remove o item gráfico
            self._scene.removeItem(graphics_item)
            self._set_status_message(
                "Objeto movido/transformado para fora da viewport.", 2000
            )
            self._state_manager.mark_as_modified()
        else:
            # Objeto ainda está (parcialmente) visível, atualiza o item existente
            try:
                graphics_item.prepareGeometryChange()
                # ASSOCIA O NOVO OBJETO CLIPPADO AO ITEM GRÁFICO EXISTENTE
                graphics_item.setData(0, clipped_data_object)
                # Atualiza a geometria e o estilo com base no objeto CLIPPADO
                self._update_graphics_item_geometry(graphics_item, clipped_data_object)
                self._apply_style_to_item(graphics_item, clipped_data_object)

                graphics_item.update()
                self._scene.update(
                    graphics_item.sceneBoundingRect()
                )  # Atualiza área antiga/nova
                self._state_manager.mark_as_modified()

            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erro ao Atualizar Gráfico Pós-Transformação",
                    f"Falha ao atualizar item {type(graphics_item).__name__} após clipping: {e}",
                )
                print(f"Erro detalhes atualização pós-clip: {e}")

    def _find_graphics_item_for_object(
        self, data_obj: DataObject
    ) -> Optional[QGraphicsItem]:
        """Encontra o QGraphicsItem na cena correspondente ao DataObject (pela identidade do objeto)."""
        if data_obj is None:
            return None
        for item in self._scene.items():
            if item is self._clip_rect_item:
                continue
            # Compara a identidade do objeto de dados associado via setData(0, ...)
            if item.data(0) is data_obj:
                return item
        return None

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        """Atualiza a geometria do item gráfico com base no DataObject associado."""
        if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
            size, offset = data.GRAPHICS_SIZE, data.GRAPHICS_SIZE / 2.0
            new_rect = QRectF(data.x - offset, data.y - offset, size, size)
            if item.rect() != new_rect:
                item.setRect(new_rect)
        elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
            new_line = QLineF(data.start.x, data.start.y, data.end.x, data.end.y)
            if item.line() != new_line:
                item.setLine(new_line)
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            new_polygon_qf = QPolygonF([p.to_qpointf() for p in data.points])
            current_poly = item.polygon()
            # Verifica se o polígono realmente mudou (tamanho ou pontos)
            if current_poly.size() != new_polygon_qf.size() or any(
                p1 != p2 for p1, p2 in zip(current_poly, new_polygon_qf)
            ):
                item.setPolygon(new_polygon_qf)
        else:
            # Situação inesperada, log para depuração
            print(
                f"AVISO: Combinação item/dado não prevista para atualização geométrica: {type(item).__name__}/{type(data).__name__}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, data: DataObject):
        """Reaplica o estilo (cor, preenchimento, tipo de linha) ao item gráfico."""
        if not hasattr(data, "color"):
            return

        color = (
            data.color
            if isinstance(data.color, QColor) and data.color.isValid()
            else QColor(Qt.black)
        )
        pen, brush = None, None

        if isinstance(data, Point) and isinstance(item, QGraphicsEllipseItem):
            pen = QPen(color, 1)
            brush = QBrush(color)
        elif isinstance(data, Line) and isinstance(item, QGraphicsLineItem):
            pen = QPen(
                color, data.GRAPHICS_WIDTH, Qt.SolidLine
            )  # Linhas são sempre sólidas
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            pen = QPen(color, data.GRAPHICS_BORDER_WIDTH)
            brush = QBrush()  # Inicializa pincel
            if data.is_open:
                pen.setStyle(Qt.DashLine)
                brush.setStyle(Qt.NoBrush)
            else:  # Polígono Fechado
                pen.setStyle(Qt.SolidLine)
                if data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color)
                    fill_color.setAlphaF(data.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
                else:
                    brush.setStyle(Qt.NoBrush)

        # Aplica pen/brush apenas se necessário e se o item suportar
        if hasattr(item, "setPen") and pen is not None:
            current_pen = getattr(item, "pen", lambda: None)()
            if current_pen is None or current_pen != pen:
                item.setPen(pen)
        if hasattr(item, "setBrush") and brush is not None:
            current_brush = getattr(item, "brush", lambda: None)()
            if current_brush is None or current_brush != brush:
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
        QApplication.processEvents()  # Atualiza UI

        # 1. Lê dados OBJ e MTL
        obj_lines, material_colors, mtl_warnings = self._read_obj_and_mtl_data(
            obj_filepath
        )
        if obj_lines is None:
            self._set_status_message("Falha ao ler arquivo(s) OBJ/MTL.")
            return

        # 2. Parseia dados OBJ para objetos internos
        parsed_objects, obj_warnings = self._object_manager.parse_obj_data(
            obj_lines, material_colors, self._state_manager.draw_color()
        )

        # 3. Prepara cena (limpa se necessário)
        if clear_before_load:
            self._clear_scene_confirmed()

        # 4. Adiciona objetos parseados à cena (com clipping)
        num_added, num_clipped_out = self._add_parsed_objects_to_scene(parsed_objects)

        # 5. Reporta resultados
        self._report_load_results(
            obj_filepath, num_added, num_clipped_out, mtl_warnings + obj_warnings
        )

        # 6. Atualiza estado da aplicação
        self._state_manager.set_current_filepath(obj_filepath)
        self._state_manager.mark_as_saved()

    def _read_obj_and_mtl_data(
        self, obj_filepath: str
    ) -> Tuple[Optional[List[str]], Dict[str, QColor], List[str]]:
        """Lê as linhas do arquivo OBJ e os dados do arquivo MTL associado, se houver."""
        obj_lines: Optional[List[str]] = None
        material_colors: Dict[str, QColor] = {}
        all_warnings: List[str] = []

        # Lê OBJ e obtém caminho relativo do MTL
        read_result = self._io_handler.read_obj_lines(obj_filepath)
        if read_result is None:
            return None, {}, ["Falha ao ler arquivo OBJ."]  # IOHandler mostra erro

        obj_lines, mtl_filename_relative = read_result

        # Lê MTL se referenciado
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            mtl_filepath_full = os.path.normpath(
                os.path.join(obj_dir, mtl_filename_relative)
            )
            if os.path.exists(mtl_filepath_full):
                material_colors, mtl_warnings = self._io_handler.read_mtl_file(
                    mtl_filepath_full
                )
                all_warnings.extend(mtl_warnings)
            else:
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
        initial_item_count = len(
            [i for i in self._scene.items() if i is not self._clip_rect_item]
        )

        for data_obj in parsed_objects:
            item_count_before = len(
                [i for i in self._scene.items() if i is not self._clip_rect_item]
            )
            self._add_data_object_to_scene(data_obj)  # Lida com clipping internamente
            item_count_after = len(
                [i for i in self._scene.items() if i is not self._clip_rect_item]
            )

            if item_count_after > item_count_before:
                num_added += 1
            elif not isinstance(data_obj, Point):  # Pontos fora são apenas clipados
                num_clipped_out += 1

        if num_added > 0 or num_clipped_out > 0:
            self._scene.update()

        return num_added, num_clipped_out

    def _report_load_results(
        self,
        obj_filepath: str,
        num_added: int,
        num_clipped_out: int,
        warnings: List[str],
    ) -> None:
        """Exibe mensagens resumindo o resultado do carregamento do arquivo OBJ."""
        base_filename = os.path.basename(obj_filepath)
        if num_added == 0 and num_clipped_out == 0 and not warnings:
            # Verifica se MTL era esperado mas não encontrado
            mtl_not_found = any(
                "Arquivo MTL" in w and "não encontrado" in w for w in warnings
            )
            msg = f"Nenhum objeto geométrico (v, l, f, p) encontrado ou adicionado de '{base_filename}'."
            if mtl_not_found:
                msg += f"\n(Arquivo MTL referenciado não foi encontrado.)"
            QMessageBox.information(self, "Arquivo Vazio ou Não Suportado", msg)
            self._set_status_message(
                "Carregamento concluído (sem geometria adicionada)."
            )
        else:
            final_message = f"Carregado: {num_added} objeto(s) de '{base_filename}'."
            if num_clipped_out > 0:
                final_message += f" ({num_clipped_out} totalmente fora da viewport)"

            if warnings:
                formatted_warnings = "- " + "\n- ".join(warnings)
                QMessageBox.warning(
                    self,
                    "Carregado com Avisos",
                    f"{final_message}\n\nAvisos/Erros:\n{formatted_warnings}",
                )
                final_message += " (com avisos)"
            self._set_status_message(final_message)

    def _prompt_save_as_obj(self) -> bool:
        """Abre diálogo "Salvar Como" para arquivos OBJ."""
        self._drawing_controller.cancel_current_drawing()
        current_path = self._state_manager.current_filepath()
        default_name = (
            os.path.basename(current_path) if current_path else "cena_sem_titulo.obj"
        )

        # IOHandler retorna caminho base (sem extensão)
        base_filepath = self._io_handler.prompt_save_obj(default_name)
        if not base_filepath:
            self._set_status_message("Salvar cancelado.")
            return False

        if self._save_to_file(base_filepath):
            # Atualiza path no state manager (adicionando .obj)
            self._state_manager.set_current_filepath(base_filepath + ".obj")
            self._state_manager.mark_as_saved()
            return True
        else:
            # Mensagem de falha já mostrada por _save_to_file ou IOHandler
            self._set_status_message("Falha ao salvar.")
            return False

    def _save_current_file(self) -> bool:
        """Salva no arquivo atual ou chama 'Salvar Como' se não houver arquivo."""
        current_path = self._state_manager.current_filepath()
        if not current_path:
            return self._prompt_save_as_obj()
        else:
            self._drawing_controller.cancel_current_drawing()
            # Obtém caminho base (sem extensão)
            base_filepath, _ = os.path.splitext(current_path)
            if self._save_to_file(base_filepath):
                self._state_manager.mark_as_saved()
                return True
            else:
                return False  # Mensagem de erro já mostrada

    def _save_to_file(self, base_filepath: str) -> bool:
        """Salva a cena atual nos arquivos OBJ e MTL."""
        self._set_status_message(f"Salvando em {os.path.basename(base_filepath)}...", 0)
        QApplication.processEvents()

        # 1. Coleta objetos de dados da cena
        scene_data_objects = self._collect_scene_data_objects()
        if not scene_data_objects:
            QMessageBox.information(self, "Nada para Salvar", "A cena está vazia.")
            self._set_status_message("Nada para salvar.")
            return True  # Salvar vazio é sucesso

        # 2. Gera dados OBJ e MTL
        mtl_filename = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, gen_warnings = self._object_manager.generate_obj_data(
            scene_data_objects, mtl_filename
        )

        if obj_lines is None:
            self._report_save_results(
                base_filepath, False, gen_warnings, is_generation_error=True
            )
            return False

        # 3. Escreve dados nos arquivos
        write_success = self._io_handler.write_obj_and_mtl(
            base_filepath, obj_lines, mtl_lines
        )

        # 4. Reporta resultados
        has_mtl = mtl_lines is not None and len(mtl_lines) > 0
        self._report_save_results(
            base_filepath, write_success, gen_warnings, has_mtl=has_mtl
        )
        return write_success

    def _collect_scene_data_objects(self) -> List[DataObject]:
        """Extrai os DataObjects (Point, Line, Polygon) dos itens da cena."""
        data_objects: List[DataObject] = []
        # Ignora itens que não devem ser salvos
        items_to_ignore = {
            self._clip_rect_item,
            self._drawing_controller._temp_line_item,
            self._drawing_controller._temp_polygon_path,
        }
        for item in self._scene.items():
            if item in items_to_ignore:
                continue
            # Pega o objeto de dados associado ao item gráfico
            data = item.data(0)
            if isinstance(data, (Point, Line, Polygon)):
                data_objects.append(data)
        return data_objects

    def _report_save_results(
        self,
        base_filepath: str,
        success: bool,
        warnings: List[str],
        has_mtl: bool = False,
        is_generation_error: bool = False,
    ) -> None:
        """Exibe mensagens resumindo o resultado do salvamento."""
        base_filename = os.path.basename(base_filepath)
        if is_generation_error:
            msg = "Falha ao gerar dados OBJ."
            if warnings:
                msg += "\n\nAvisos:\n- " + "\n- ".join(warnings)
            QMessageBox.critical(self, "Erro na Geração OBJ", msg)
            self._set_status_message("Erro ao gerar OBJ.")
        elif success:
            obj_name = base_filename + ".obj"
            msg = f"Cena salva como '{obj_name}'"
            if has_mtl:
                msg += f" e '{base_filename}.mtl'"
            msg += "."
            if warnings:
                formatted = "\n\nAvisos:\n- " + "\n- ".join(warnings)
                QMessageBox.warning(self, "Salvo com Avisos", f"{msg}{formatted}")
                msg += " (com avisos)"
            self._set_status_message(msg)
        else:
            # IOHandler mostra erro crítico de escrita
            self._set_status_message(
                f"Falha ao escrever arquivo(s) para '{base_filename}'."
            )

    # --- Viewport ---

    def _toggle_viewport_visibility(self, checked: bool):
        """Mostra ou oculta o retângulo visual do viewport."""
        self._clip_rect_item.setVisible(checked)
        # Atualiza estado da ação no menu (caso clicado fora do menu)
        self._ui_manager.update_viewport_action_state(checked)

    # --- Evento de Fechamento ---

    def closeEvent(self, event: QCloseEvent) -> None:
        """Chamado ao tentar fechar a janela principal."""
        self._drawing_controller.cancel_current_drawing()  # Garante cancelamento
        if self._check_unsaved_changes("fechar a aplicação"):
            event.accept()  # Permite fechar
        else:
            event.ignore()  # Cancela fechamento
