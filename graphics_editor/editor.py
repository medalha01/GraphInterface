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
from PyQt5.QtWidgets import QApplication  # Import QApplication for processEvents

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
from .utils import clipping as clp  # Import clipping module

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
        self.setWindowTitle("Editor Gráfico 2D - Nova Cena")  # Título inicial
        self.resize(1000, 750)

        # --- Componentes Principais ---
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-10000, -10000, 20000, 20000)
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

        # --- Gerenciadores e Controladores ---
        # Ordem de inicialização pode ser importante se houver dependências
        self._state_manager = EditorStateManager(self)
        self._ui_manager = UIManager(
            self, self._state_manager
        )  # UI Manager precisa do state
        self._drawing_controller = DrawingController(
            self._scene, self._state_manager, self
        )
        self._transformation_controller = TransformationController(self)
        self._io_handler = IOHandler(self)
        self._object_manager = ObjectManager()

        # --- Itens Gráficos Especiais (Viewport) ---
        self._clip_rect_item = QGraphicsRectItem(self._state_manager.clip_rect())
        self._clip_rect_item.setPen(QPen(QColor(0, 0, 255, 100), 1, Qt.DashLine))
        self._clip_rect_item.setBrush(QBrush(Qt.NoBrush))
        self._clip_rect_item.setZValue(-1)
        self._scene.addItem(self._clip_rect_item)

        # --- Configuração da UI (Delegada ao UIManager onde possível) ---
        self._setup_menu_bar()  # Menu ainda configurado aqui por simplicidade
        self._ui_manager.setup_toolbar(
            mode_callback=self._set_drawing_mode,
            color_callback=self._select_drawing_color,
            coord_callback=self._open_coordinate_input_dialog,
            transform_callback=self._open_transformation_dialog,
            clipper_callback=self._set_line_clipper,
        )
        self._ui_manager.setup_status_bar(zoom_callback=self._on_zoom_slider_changed)

        # --- Conectar Sinais e Slots ---
        self._connect_signals()

        # --- Estado Inicial da UI ---
        self._update_view_interaction()  # Define modo de arrasto inicial da view
        # Atualiza controles da view (zoom/rotação) após a inicialização da UI
        QTimer.singleShot(0, self._update_view_controls)

    # --- UI Setup (Menus principalmente) ---

    def _get_icon(self, name: str) -> QIcon:
        # Reutiliza método do UIManager
        return self._ui_manager._get_icon(name)

    def _setup_menu_bar(self) -> None:
        """Configura a barra de menus (ainda gerenciado aqui)."""
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
        # Guarda referência para poder atualizar estado checkado
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

        # --- View -> Editor (Coordenação) ---
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(
            self._delete_selected_items
        )  # Atalho de teclado
        # View -> UI Manager (Atualização de Status)
        self._view.scene_mouse_moved.connect(self._ui_manager.update_status_bar_coords)
        self._view.rotation_changed.connect(
            self._update_view_controls
        )  # Atualiza slider e label rot
        self._view.scale_changed.connect(
            self._update_view_controls
        )  # Atualiza slider e label zoom

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
        # Se clip rect for dinâmico, conecte aqui também
        # self._state_manager.clip_rect_changed.connect(self._update_clip_rect_item)

        # --- StateManager -> Editor (Lógica de Interação) ---
        self._state_manager.drawing_mode_changed.connect(self._update_view_interaction)
        self._state_manager.drawing_mode_changed.connect(
            self._drawing_controller.cancel_current_drawing
        )  # Cancela desenho ao mudar modo

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

        # --- Componentes -> UI Manager (Atualização de Status) ---
        # Zoom slider é conectado diretamente no setup do UIManager

    # --- Handlers de Eventos da View (Delegam ou Processam) ---

    def _handle_scene_left_click(self, scene_pos: QPointF):
        """Decide se passa o clique para o DrawingController ou para a View."""
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.POINT, DrawingMode.LINE, DrawingMode.POLYGON]:
            self._drawing_controller.handle_scene_left_click(scene_pos)
        elif mode == DrawingMode.SELECT:
            # Deixa a view lidar com a seleção (rubberband)
            pass  # O clique já foi processado pela view para iniciar a seleção
        elif mode == DrawingMode.PAN:
            # Pan é iniciado no press event da view
            pass

    def _handle_scene_right_click(self, scene_pos: QPointF):
        """Decide se passa o clique para o DrawingController."""
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
        """Define o modo via StateManager."""
        self._state_manager.set_drawing_mode(mode)
        # O StateManager emitirá sinal que atualizará a UI e cancelará desenhos

    def _update_view_interaction(self):
        """Atualiza o modo de arrasto da view com base no modo do StateManager."""
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
        elif mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
        else:  # Modos de desenho
            self._view.set_drag_mode(QGraphicsView.NoDrag)
        # O cursor é atualizado dentro de view.set_drag_mode()

    def _set_line_clipper(self, algorithm: LineClippingAlgorithm):
        """Define o algoritmo de clipping via StateManager."""
        self._state_manager.set_selected_line_clipper(algorithm)
        algo_name = (
            "Cohen-Sutherland"
            if algorithm == LineClippingAlgorithm.COHEN_SUTHERLAND
            else "Liang-Barsky"
        )
        self._set_status_message(f"Clipping de linha: {algo_name}", 2000)

    # --- Controle da View (Zoom/Rotação) ---

    def _on_zoom_slider_changed(self, value: int):
        """Mapeia valor do slider para escala da view."""
        # Lógica de mapeamento logarítmico (igual a antes)
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        if max_slider == min_slider or max_scale <= min_scale:
            return

        log_min, log_max = np.log(min_scale), np.log(max_scale)
        if log_max <= log_min:
            return

        factor = (value - min_slider) / (max_slider - min_slider)
        target_scale = np.exp(log_min + factor * (log_max - log_min))
        self._view.set_scale(
            target_scale, center_on_mouse=False
        )  # View emitirá scale_changed

    def _update_view_controls(self):
        """Atualiza UI (slider/labels) com base no estado da view."""
        # Zoom
        current_scale = self._view.get_scale()
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        slider_value = min_slider  # Default
        if max_scale > min_scale and max_slider > min_slider:
            log_min, log_max = np.log(min_scale), np.log(max_scale)
            if log_max > log_min:
                clamped_scale = max(min_scale, min(current_scale, max_scale))
                log_scale = np.log(clamped_scale)
                factor = (log_scale - log_min) / (log_max - log_min)
                slider_value = int(
                    round(min_slider + factor * (max_slider - min_slider))
                )

        self._ui_manager.update_status_bar_zoom(current_scale, slider_value)

        # Rotação
        rotation_angle = self._view.get_rotation_angle()
        self._ui_manager.update_status_bar_rotation(rotation_angle)

    def _reset_view(self):
        """Reseta a transformação da QGraphicsView."""
        self._view.reset_view()
        # Centraliza na viewport padrão após resetar
        self._view.centerOn(self._state_manager.clip_rect().center())
        # A view emitirá sinais scale_changed/rotation_changed que atualizarão a UI

    # --- Gerenciamento de Objetos na Cena Final ---

    def _get_clip_rect_tuple(self) -> clp.ClipRect:
        """Obtém a tupla de clip do StateManager."""
        rect = self._state_manager.clip_rect()
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _add_data_object_to_scene(self, data_object: object):
        """
        Recebe um objeto finalizado do DrawingController ou de diálogos,
        aplica clipping e adiciona à cena.
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
                    start_pt = Point(
                        p1[0], p1[1], data_object.start.color
                    )  # Mantém cor original
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

            if clipped_data_object:
                graphics_item = clipped_data_object.create_graphics_item()
                graphics_item.setData(0, clipped_data_object)  # Associa dado ao item
                self._scene.addItem(graphics_item)
                self._state_manager.mark_as_modified()  # Marca como modificado
            # else: O objeto foi completamente clipado, não adiciona nada

        except Exception as e:
            QMessageBox.critical(
                self,
                "Erro ao Adicionar/Clipar Item",
                f"Não foi possível clipar ou criar item gráfico para {type(data_object).__name__}: {e}",
            )
            print(f"Erro detalhes: {e}")

    def _delete_selected_items(self):
        """Remove os itens selecionados da cena."""
        selected = self._scene.selectedItems()
        if not selected:
            self._set_status_message("Nenhum item selecionado para excluir.", 2000)
            return

        items_deleted = 0
        for item in selected:
            if item is self._clip_rect_item:
                continue  # Não exclui viewport
            if item.scene():  # Verifica se ainda está na cena
                # TODO: Idealmente, deveria remover o DataObject correspondente do ObjectManager também
                self._scene.removeItem(item)
                items_deleted += 1

        if items_deleted > 0:
            self._scene.update()
            self._state_manager.mark_as_modified()
            self._set_status_message(f"{items_deleted} item(ns) excluído(s).", 2000)

    def _clear_scene_confirmed(self):
        """Limpa todos os itens da cena (exceto viewport) e reseta estado."""
        self._drawing_controller.cancel_current_drawing()  # Cancela desenho pendente
        self._scene.clearSelection()
        items_to_remove = [
            item for item in self._scene.items() if item is not self._clip_rect_item
        ]
        for item in items_to_remove:
            self._scene.removeItem(item)

        self._scene.update()
        self._reset_view()  # Reseta zoom/pan/rotação
        self._state_manager.mark_as_saved()
        self._state_manager.set_current_filepath(None)
        # Título da janela será atualizado via sinais do state_manager
        self._set_status_message("Nova cena criada.", 2000)

    # --- Ações e Diálogos ---
    def _prompt_clear_scene(self):
        """Pergunta ao usuário se deseja limpar a cena, verificando alterações."""
        # Cancela qualquer desenho em progresso antes de perguntar
        self._drawing_controller.cancel_current_drawing()
        if self._check_unsaved_changes("limpar a cena"):
            self._clear_scene_confirmed() # Chama a limpeza real se confirmado


    def _clear_scene_confirmed(self):
        """Limpa todos os itens da cena (exceto viewport) e reseta estado."""
        self._drawing_controller.cancel_current_drawing() # Cancela desenho pendente
        self._scene.clearSelection()
        items_to_remove = [
            item for item in self._scene.items() if item is not self._clip_rect_item
        ]
        for item in items_to_remove:
            self._scene.removeItem(item)

        self._scene.update()
        self._reset_view() # Reseta zoom/pan/rotação
        self._state_manager.mark_as_saved()
        self._state_manager.set_current_filepath(None)
        # Título da janela será atualizado via sinais do state_manager
        self._set_status_message("Nova cena criada.", 2000)
    def _select_drawing_color(self):
        """Abre diálogo para selecionar a cor de desenho."""
        initial_color = self._state_manager.draw_color()
        new_color = QColorDialog.getColor(
            initial_color, self, "Selecionar Cor de Desenho"
        )
        if new_color.isValid():
            self._state_manager.set_draw_color(new_color)  # Atualiza estado central
            # UI Manager será notificado pelo sinal do state_manager

    def _set_status_message(self, message: str, timeout: int = 3000):
        """Exibe uma mensagem na barra de status."""
        self._ui_manager.update_status_bar_message(message)
        if timeout > 0:
            QTimer.singleShot(
                timeout, lambda: self._ui_manager.update_status_bar_message("Pronto.")
            )

    def _update_window_title(self, *args):  # Aceita args extras dos sinais
        """Atualiza o título da janela com base no estado."""
        title = "Editor Gráfico 2D - "
        filepath = self._state_manager.current_filepath()
        filename = os.path.basename(filepath) if filepath else "Nova Cena"
        title += filename
        if self._state_manager.has_unsaved_changes():
            title += " *"
        self.setWindowTitle(title)

    def _check_unsaved_changes(self, action_description: str = "prosseguir") -> bool:
        """Verifica alterações não salvas e pergunta ao usuário."""
        if not self._state_manager.has_unsaved_changes():
            return True

        reply = QMessageBox.warning(
            self,
            "Alterações Não Salvas",
            f"A cena contém alterações não salvas. Deseja salvá-las antes de {action_description}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if reply == QMessageBox.Save:
            return self._save_current_file()  # Tenta salvar
        elif reply == QMessageBox.Discard:
            return True  # Pode prosseguir
        else:  # reply == QMessageBox.Cancel
            return False  # Não prosseguir

    def _open_coordinate_input_dialog(self):
        """Abre diálogo para adicionar formas via coordenadas."""
        self._drawing_controller.cancel_current_drawing()
        dialog_mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
        }
        dialog_mode_str = dialog_mode_map.get(
            self._state_manager.drawing_mode(), "polygon"
        )
        dialog = CoordinateInputDialog(self, mode=dialog_mode_str)
        dialog.set_initial_color(self._state_manager.draw_color())

        if dialog.exec_() == QDialog.Accepted:
            try:
                result_data = dialog.get_validated_data()
                if result_data:
                    # Reutiliza lógica de criação (mas evita duplicação com _add_item_from...)
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

    def _add_item_from_validated_data(self, result_data: Any, dialog_mode_str: str):
        """Cria objeto a partir de dados validados do diálogo e o adiciona."""
        # Esta lógica é quase idêntica à validação no diálogo, idealmente seria unificada.
        # Mas por enquanto, recria o DataObject e chama _add_data_object_to_scene.
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
                start_pt = Point(coords[0][0], coords[0][1], color=color)
                end_pt = Point(coords[1][0], coords[1][1], color=color)
                data_object = Line(start_pt, end_pt, color=color)
            elif dialog_mode_str == "polygon":
                is_open = result_data.get("is_open", False)
                is_filled = result_data.get("is_filled", False)
                min_pts = 2 if is_open else 3
                if len(coords) < min_pts:
                    raise ValueError(f"Pontos insuficientes ({len(coords)}/{min_pts}).")
                poly_pts = [Point(x, y, color=color) for x, y in coords]
                data_object = Polygon(
                    poly_pts, is_open, color=color, is_filled=is_filled
                )

            if data_object:
                self._add_data_object_to_scene(
                    data_object
                )  # Adiciona à cena (com clipping)
            else:
                raise ValueError(f"Modo de criação desconhecido: {dialog_mode_str}")

        except (ValueError, TypeError, IndexError, KeyError) as e:
            raise ValueError(f"Erro ao criar item do diálogo: {e}")  # Repassa erro

    def _open_transformation_dialog(self):
        """Abre diálogo para aplicar transformações ao item selecionado."""
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
        # O controlador emitirá 'object_transformed' se OK

    def _handle_object_transformed(self, transformed_data_object: object):
        """Atualiza o item gráfico correspondente após a transformação (Slot)."""
        if not isinstance(transformed_data_object, (Point, Line, Polygon)):
            print(
                f"AVISO: Sinal object_transformed com tipo inesperado: {type(transformed_data_object)}"
            )
            return

        graphics_item = self._find_graphics_item_for_object(transformed_data_object)
        if not graphics_item:
            print(
                f"AVISO: Item gráfico não encontrado para {transformed_data_object} após transformação."
            )
            # Poderia tentar recriar o item? Ou é um erro? Por ora, apenas avisa.
            return

        try:
            if not graphics_item.scene():
                print(
                    f"AVISO: Item {graphics_item} encontrado, mas não está mais na cena."
                )
                return

            # --- Atualização da Geometria e Estilo ---
            # O TransformationController modificou o DataObject. Agora atualizamos
            # o QGraphicsItem para refletir essas mudanças.
            # Re-clipping *não* está sendo feito aqui. O objeto transformado pode
            # agora estar (parcialmente) fora da viewport.

            graphics_item.prepareGeometryChange()  # Notifica mudança iminente
            self._update_graphics_item_geometry(graphics_item, transformed_data_object)
            self._apply_style_to_item(
                graphics_item, transformed_data_object
            )  # Garante cor/estilo

            graphics_item.update()  # Redesenha o item específico
            self._scene.update(
                graphics_item.boundingRect()
            )  # Atualiza área antiga/nova

            self._state_manager.mark_as_modified()

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
        """Encontra o QGraphicsItem na cena correspondente ao DataObject (pela identidade)."""
        if data_obj is None:
            return None
        for item in self._scene.items():
            if item is self._clip_rect_item:
                continue
            # Compara a identidade do objeto de dados associado
            if item.data(0) is data_obj:
                return item
        return None

    def _update_graphics_item_geometry(self, item: QGraphicsItem, data: DataObject):
        """Atualiza a geometria do item gráfico com base no DataObject (igual a antes)."""
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
            # Comparação mais robusta para QPolygonF
            current_poly = item.polygon()
            if (
                current_poly.size() != new_polygon_qf.size()
                or not np.allclose(
                    current_poly.boundingRect().getCoords(),
                    new_polygon_qf.boundingRect().getCoords(),
                )
                or any(p1 != p2 for p1, p2 in zip(current_poly, new_polygon_qf))
            ):  # Verifica ponto a ponto se bboxes são iguais
                item.setPolygon(new_polygon_qf)
        else:
            print(
                f"AVISO: Combinação item/dado não prevista para atualização: {type(item).__name__}/{type(data).__name__}"
            )

    def _apply_style_to_item(self, item: QGraphicsItem, data: DataObject):
        """Reaplica estilo (cor, preenchimento, etc.) ao item gráfico (igual a antes)."""
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
            pen = QPen(color, data.GRAPHICS_WIDTH)
        elif isinstance(data, Polygon) and isinstance(item, QGraphicsPolygonItem):
            pen = QPen(color, data.GRAPHICS_BORDER_WIDTH)
            brush = QBrush()
            if data.is_open:
                pen.setStyle(Qt.DashLine)
                brush.setStyle(Qt.NoBrush)
            else:
                pen.setStyle(Qt.SolidLine)
                if data.is_filled:
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color)
                    fill_color.setAlphaF(data.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
                else:
                    brush.setStyle(Qt.NoBrush)

        # Aplica apenas se mudou
        current_pen = getattr(item, "pen", lambda: None)()
        current_brush = getattr(item, "brush", lambda: None)()
        if (
            pen is not None
            and (current_pen is None or current_pen != pen)
            and hasattr(item, "setPen")
        ):
            item.setPen(pen)
        if (
            brush is not None
            and (current_brush is None or current_brush != brush)
            and hasattr(item, "setBrush")
        ):
            item.setBrush(brush)

    # --- Importação/Exportação OBJ ---

    def _prompt_load_obj(self):
        """Abre diálogo para carregar arquivo OBJ."""
        if not self._check_unsaved_changes("carregar um novo arquivo"):
            return
        obj_filepath = self._io_handler.prompt_load_obj()
        if obj_filepath:
            self._load_obj_file(obj_filepath, clear_before_load=True)

    def _load_obj_file(self, obj_filepath: str, clear_before_load: bool = True):
        """Carrega e processa um arquivo OBJ."""
        self._set_status_message(f"Carregando {os.path.basename(obj_filepath)}...", 0)
        QApplication.processEvents()  # Força atualização da UI

        # Leitura (IOHandler)
        read_result = self._io_handler.read_obj_lines(obj_filepath)
        if read_result is None:
            self._set_status_message("Falha ao ler arquivo OBJ.")
            return
        obj_lines, mtl_filename_relative = read_result

        # Leitura MTL (IOHandler)
        material_colors: Dict[str, QColor] = {}
        mtl_warnings: List[str] = []
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

        # Parsing (ObjectManager)
        parsed_objects, obj_warnings = self._object_manager.parse_obj_data(
            obj_lines, material_colors, self._state_manager.draw_color()  # Cor padrão
        )

        # Limpeza e Adição à Cena
        if clear_before_load:
            self._clear_scene_confirmed()  # Limpa cena e reseta estado (via state_manager)

        num_added = 0
        num_clipped_out = 0
        if not parsed_objects and not mtl_warnings and not obj_warnings:
            msg = f"Nenhum objeto geométrico (v, l, f, p) ou material válido encontrado em '{os.path.basename(obj_filepath)}'."
            if mtl_filename_relative and not os.path.exists(
                mtl_filepath_full
            ):  # Verifica se mtl era esperado mas não achado
                msg += f"\nArquivo MTL '{mtl_filename_relative}' referenciado não foi encontrado."
            QMessageBox.information(self, "Arquivo Vazio ou Não Suportado", msg)
            self._set_status_message("Carregamento concluído (sem geometria).")
        else:
            for data_obj in parsed_objects:
                # Conta itens antes/depois para ver se foi adicionado (pós-clip)
                item_count_before = len(
                    [i for i in self._scene.items() if i is not self._clip_rect_item]
                )
                self._add_data_object_to_scene(data_obj)  # Adiciona (com clipping)
                item_count_after = len(
                    [i for i in self._scene.items() if i is not self._clip_rect_item]
                )
                if item_count_after > item_count_before:
                    num_added += 1
                elif not isinstance(data_obj, Point):
                    num_clipped_out += 1  # Se não é ponto e não aumentou, foi clipado

            self._scene.update()
            # Relatório final
            all_warnings = mtl_warnings + obj_warnings
            final_message = f"Carregado: {num_added} objeto(s) de '{os.path.basename(obj_filepath)}'."
            if num_clipped_out > 0:
                final_message += f" ({num_clipped_out} fora da viewport)"
            if all_warnings:
                formatted_warnings = "- " + "\n- ".join(all_warnings)
                QMessageBox.warning(
                    self,
                    "Carregado com Avisos",
                    f"{final_message}\n\nAvisos/Erros:\n{formatted_warnings}",
                )
                final_message += " (com avisos)"
            self._set_status_message(final_message)

        # Atualiza estado pós-carregamento
        self._state_manager.set_current_filepath(obj_filepath)
        self._state_manager.mark_as_saved()  # Considera salvo após carregar

    def _prompt_save_as_obj(self) -> bool:
        """Abre diálogo "Salvar Como"."""
        self._drawing_controller.cancel_current_drawing()
        current_path = self._state_manager.current_filepath()
        default_name = (
            os.path.basename(current_path) if current_path else "cena_sem_titulo.obj"
        )

        # IOHandler retorna o caminho BASE (sem extensão)
        base_filepath = self._io_handler.prompt_save_obj(default_name)
        if not base_filepath:
            self._set_status_message("Salvar cancelado.")
            return False

        # Chama salvamento real
        if self._save_to_file(base_filepath):
            # Atualiza o path no state manager (adicionando .obj)
            self._state_manager.set_current_filepath(base_filepath + ".obj")
            self._state_manager.mark_as_saved()
            # Título atualiza via sinal
            return True
        else:
            self._set_status_message("Falha ao salvar.")
            return False

    def _save_current_file(self) -> bool:
        """Salva no arquivo atual ou chama 'Salvar Como'."""
        current_path = self._state_manager.current_filepath()
        if not current_path:
            return self._prompt_save_as_obj()
        else:
            self._drawing_controller.cancel_current_drawing()
            base_filepath, _ = os.path.splitext(current_path)  # Obtém caminho base
            if self._save_to_file(base_filepath):
                self._state_manager.mark_as_saved()
                return True
            else:
                return False  # Mensagem de erro já mostrada

    def _save_to_file(self, base_filepath: str) -> bool:
        """Lógica interna para gerar e escrever arquivos OBJ/MTL."""
        self._set_status_message(f"Salvando em {os.path.basename(base_filepath)}...", 0)
        QApplication.processEvents()

        # Coleta DataObjects da cena
        scene_data_objects: List[DataObject] = []
        for item in self._scene.items():
            # Ignora viewport e itens temporários do drawing controller
            if (
                item is self._clip_rect_item
                or item is self._drawing_controller._temp_line_item
                or item is self._drawing_controller._temp_polygon_path
            ):
                continue
            data = item.data(0)
            if isinstance(data, (Point, Line, Polygon)):
                scene_data_objects.append(data)

        if not scene_data_objects:
            QMessageBox.information(self, "Nada para Salvar", "A cena está vazia.")
            self._set_status_message("Nada para salvar.")
            return True  # Salvar vazio é sucesso

        # Geração (ObjectManager)
        mtl_filename = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, warnings_gen = self._object_manager.generate_obj_data(
            scene_data_objects, mtl_filename
        )

        if obj_lines is None:  # Geração falhou
            msg = "Falha ao gerar dados OBJ."
            if warnings_gen:
                msg += "\n\nAvisos:\n- " + "\n- ".join(warnings_gen)
            QMessageBox.critical(self, "Erro na Geração OBJ", msg)
            self._set_status_message("Erro ao gerar OBJ.")
            return False

        # Escrita (IOHandler)
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
                formatted = "\n\nAvisos:\n- " + "\n- ".join(warnings_gen)
                QMessageBox.warning(self, "Salvo com Avisos", f"{msg}{formatted}")
                msg += " (com avisos)"
            self._set_status_message(msg)
            return True
        else:
            # IOHandler já mostrou erro crítico
            self._set_status_message(
                f"Falha ao escrever arquivo(s) para '{os.path.basename(base_filepath)}'."
            )
            return False

    # --- Viewport ---
    def _toggle_viewport_visibility(self, checked: bool):
        """Mostra ou oculta o retângulo visual da viewport."""
        self._clip_rect_item.setVisible(checked)
        # Atualiza o estado da ação no menu (caso seja clicado fora do menu)
        self._ui_manager.update_viewport_action_state(checked)

    # --- Evento de Fechamento ---
    def closeEvent(self, event: QCloseEvent) -> None:
        """Chamado ao tentar fechar a janela."""
        self._drawing_controller.cancel_current_drawing()  # Garante cancelamento
        if self._check_unsaved_changes("fechar a aplicação"):
            event.accept()  # Permite fechar
        else:
            event.ignore()  # Cancela fechamento
