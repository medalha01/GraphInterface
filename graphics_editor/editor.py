# graphics_editor/editor.py
import sys
import os
import numpy as np
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Union, Any, Callable
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
from .models import Point, Line, Polygon, BezierCurve
from .dialogs.coordinates_input import CoordinateInputDialog
from .dialogs.transformation_dialog import TransformationDialog
from .controllers.transformation_controller import (
    TransformationController,
    TransformableObject,
)
from .io_handler import IOHandler
from .object_manager import ObjectManager
from .utils import clipping as clp

from .state_manager import EditorStateManager, DrawingMode, LineClippingAlgorithm
from .controllers.drawing_controller import DrawingController
from .controllers.scene_controller import SceneController, SC_ORIGINAL_OBJECT_KEY
from .ui_manager import UIManager
from .services.file_operation_service import FileOperationService

DataObject = Union[Point, Line, Polygon, BezierCurve]
DATA_OBJECT_TYPES = (Point, Line, Polygon, BezierCurve)


class GraphicsEditor(QMainWindow):
    """
    Janela principal da aplicação para o editor gráfico 2D.
    
    Esta classe coordena todos os componentes do editor gráfico, incluindo:
    - Gerenciamento da interface do usuário
    - Controle de desenho
    - Transformações de objetos
    - Operações de arquivo
    - Gerenciamento de estado
    - Visualização da cena
    """

    BEZIER_CLIPPING_SAMPLES_PER_SEGMENT = 20
    BEZIER_SAVE_SAMPLES_PER_SEGMENT = 20

    def __init__(self, parent=None):
        """
        Inicializa o editor gráfico.
        
        Args:
            parent: Widget pai da janela principal
        """
        super().__init__(parent)
        self.setWindowTitle("Editor Gráfico 2D - Nova Cena")
        self.resize(1000, 750)

        self._status_reset_timer = QTimer(self)
        self._status_reset_timer.setSingleShot(True)
        self._status_reset_timer.timeout.connect(
            lambda: self._ui_manager.update_status_bar_message("Pronto.")
        )

        self._setup_core_components()
        self._setup_managers_controllers_services()
        self._setup_special_items()
        self._setup_ui_elements()
        self._connect_signals()
        self._initialize_ui_state()

    def _setup_core_components(self) -> None:
        """
        Configura os componentes principais da cena e visualização.
        Inicializa a cena gráfica e a visualização central.
        """
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-50000, -50000, 100000, 100000)
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

    def _setup_managers_controllers_services(self) -> None:
        """
        Configura todos os gerenciadores, controladores e serviços necessários.
        Inicializa componentes para gerenciamento de estado, interface, desenho,
        transformações, entrada/saída e operações de arquivo.
        """
        self._state_manager = EditorStateManager(self)
        self._ui_manager = UIManager(self, self._state_manager)
        self._drawing_controller = DrawingController(
            self._scene, self._state_manager, self
        )
        self._transformation_controller = TransformationController(self)

        self._io_handler = IOHandler(self)
        self._object_manager = ObjectManager(
            bezier_samples=self.BEZIER_SAVE_SAMPLES_PER_SEGMENT
        )

        self._scene_controller = SceneController(self._scene, self._state_manager, self)
        self._scene_controller.bezier_clipping_samples_per_segment = (  # Ensure consistent naming
            self.BEZIER_CLIPPING_SAMPLES_PER_SEGMENT
        )

        self._file_operation_service = FileOperationService(
            parent_widget=self,
            io_handler=self._io_handler,
            object_manager=self._object_manager,
            state_manager=self._state_manager,
            scene_controller=self._scene_controller,
            drawing_controller=self._drawing_controller,
            check_unsaved_changes_func=self._check_unsaved_changes,
            clear_scene_confirmed_func=self._clear_scene_confirmed,
        )

    def _setup_special_items(self) -> None:
        """
        Configura itens especiais da cena, como o retângulo de recorte.
        Define as propriedades visuais e comportamentais destes itens.
        """
        self._clip_rect_item = QGraphicsRectItem(self._state_manager.clip_rect())
        pen = QPen(QColor(0, 0, 255, 100), 1, Qt.DashLine)
        pen.setCosmetic(True)
        self._clip_rect_item.setPen(pen)
        self._clip_rect_item.setBrush(QBrush(Qt.NoBrush))
        self._clip_rect_item.setZValue(-1)
        # Using a specific key for non-data objects to avoid confusion with SC_ORIGINAL_OBJECT_KEY
        self._clip_rect_item.setData(Qt.UserRole + 100, "viewport_rect")
        self._scene.addItem(self._clip_rect_item)

    def _setup_ui_elements(self) -> None:
        """
        Configura os elementos da interface do usuário.
        Inicializa a barra de menu, barra de ferramentas e barra de status.
        """
        menu_callbacks = {
            "new_scene": self._prompt_clear_scene,
            "load_obj": self._handle_load_obj_action,
            "save_as_obj": self._file_operation_service.prompt_save_as_obj,
            "exit": self.close,
            "delete_selected": self._delete_selected_items,
            "transform_object": self._open_transformation_dialog,
            "reset_view": self._reset_view,
            "toggle_viewport": self._toggle_viewport_visibility,
        }
        self._ui_manager.setup_menu_bar(
            menu_callbacks, lambda: self._clip_rect_item.isVisible()
        )

        self._ui_manager.setup_toolbar(
            mode_callback=self._set_drawing_mode,
            color_callback=self._select_drawing_color,
            coord_callback=self._open_coordinate_input_dialog,
            transform_callback=self._open_transformation_dialog,
            clipper_callback=self._set_line_clipper,
        )
        self._ui_manager.setup_status_bar(zoom_callback=self._on_zoom_slider_changed)

    def _initialize_ui_state(self) -> None:
        """
        Inicializa o estado inicial da interface do usuário.
        Atualiza a interação da visualização e controles.
        """
        self._update_view_interaction()
        self._update_window_title()
        QTimer.singleShot(0, self._update_view_controls)

    def _connect_signals(self) -> None:
        """
        Conecta todos os sinais e slots necessários para a comunicação entre componentes.
        Estabelece as conexões entre eventos do mouse, mudanças de estado e atualizações da interface.
        """
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(self._delete_selected_items)
        self._view.scene_mouse_moved.connect(self._ui_manager.update_status_bar_coords)
        self._view.rotation_changed.connect(self._update_view_controls)
        self._view.scale_changed.connect(self._update_view_controls)

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
        # SceneController connects to these for re-clipping. Editor updates the visual rect.
        self._state_manager.clip_rect_changed.connect(self._update_clip_rect_item)

        self._state_manager.drawing_mode_changed.connect(self._update_view_interaction)
        self._state_manager.drawing_mode_changed.connect(
            self._drawing_controller.cancel_current_drawing
        )

        self._drawing_controller.object_ready_to_add.connect(
            self._scene_controller.add_object
        )
        self._drawing_controller.status_message_requested.connect(
            self._set_status_message
        )
        self._drawing_controller.polygon_properties_query_requested.connect(
            self._prompt_polygon_properties
        )

        self._transformation_controller.object_transformed.connect(
            self._scene_controller.update_object_item
        )
        self._scene_controller.scene_modified.connect(self._handle_scene_modification)

        if hasattr(self, "_file_operation_service"):
            self._file_operation_service.status_message_requested.connect(
                self._set_status_message
            )

    def _handle_scene_modification(self, requires_saving: bool):
        """
        Manipula modificações na cena.
        
        Args:
            requires_saving: Indica se as modificações requerem salvamento
        """
        if requires_saving:
            self._state_manager.mark_as_modified()

    def _handle_scene_left_click(self, scene_pos: QPointF):
        """
        Manipula cliques do botão esquerdo do mouse na cena.
        
        Args:
            scene_pos: Posição do clique na cena
        """
        mode = self._state_manager.drawing_mode()
        if mode in [
            DrawingMode.POINT,
            DrawingMode.LINE,
            DrawingMode.POLYGON,
            DrawingMode.BEZIER,
            DrawingMode.BSPLINE,
        ]:
            self._drawing_controller.handle_scene_left_click(scene_pos)

    def _handle_scene_right_click(self, scene_pos: QPointF):
        """
        Manipula cliques do botão direito do mouse na cena.
        
        Args:
            scene_pos: Posição do clique na cena
        """
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.POLYGON, DrawingMode.BEZIER, DrawingMode.BSPLINE]:
            self._drawing_controller.handle_scene_right_click(scene_pos)

    def _handle_scene_mouse_move(self, scene_pos: QPointF):
        """
        Manipula o movimento do mouse na cena.
        
        Args:
            scene_pos: Posição atual do mouse na cena
        """
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.LINE, DrawingMode.POLYGON, DrawingMode.BEZIER, DrawingMode.BSPLINE]:
            self._drawing_controller.handle_scene_mouse_move(scene_pos)

    def _set_drawing_mode(self, mode: DrawingMode):
        """
        Define o modo de desenho atual.
        
        Args:
            mode: Novo modo de desenho a ser ativado
        """
        self._state_manager.set_drawing_mode(mode)

    def _update_view_interaction(self):
        """
        Atualiza o modo de interação da visualização baseado no modo de desenho atual.
        """
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
        elif mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
        else:
            self._view.set_drag_mode(QGraphicsView.NoDrag)

    def _set_line_clipper(self, algorithm: LineClippingAlgorithm):
        # This will trigger SceneController to re-clip via StateManager signal
        self._state_manager.set_selected_line_clipper(algorithm)
        algo_name = (
            "Cohen-Sutherland"
            if algorithm == LineClippingAlgorithm.COHEN_SUTHERLAND
            else "Liang-Barsky"
        )
        self._set_status_message(f"Clipping de linha: {algo_name}", 2000)

    def _on_zoom_slider_changed(self, value: int):
        """
        Manipula mudanças no controle deslizante de zoom.
        
        Args:
            value: Novo valor do zoom (0-100)
        """
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        if max_slider <= min_slider or max_scale <= min_scale:
            return
        log_min, log_max = np.log(min_scale), np.log(max_scale)
        if log_max <= log_min:
            return
        factor = (value - min_slider) / (max_slider - min_slider)
        target_scale = np.exp(log_min + factor * (log_max - log_min))
        self._view.set_scale(target_scale, center_on_mouse=False)

    def _update_view_controls(self):
        """
        Atualiza todos os controles de visualização.
        Atualiza controles de zoom e rotação.
        """
        self._update_zoom_controls()
        self._update_rotation_controls()

    def _update_zoom_controls(self):
        """
        Atualiza os controles de zoom baseado no estado atual da visualização.
        """
        current_scale = self._view.get_scale()
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        slider_value = min_slider
        if max_scale > min_scale and max_slider > min_slider:
            log_min, log_max = np.log(min_scale), np.log(max_scale)
            if log_max > log_min:
                clamped_scale = np.clip(current_scale, min_scale, max_scale)
                log_scale = np.log(clamped_scale)
                factor = (log_scale - log_min) / (log_max - log_min)
                slider_value = int(
                    round(min_slider + factor * (max_slider - min_slider))
                )
        self._ui_manager.update_status_bar_zoom(current_scale, slider_value)

    def _update_rotation_controls(self):
        """
        Atualiza os controles de rotação baseado no estado atual da visualização.
        """
        rotation_angle = self._view.get_rotation_angle()
        self._ui_manager.update_status_bar_rotation(rotation_angle)

    def _reset_view(self):
        """
        Reseta a visualização para seu estado inicial.
        Restaura zoom e rotação para valores padrão.
        """
        self._view.reset_view()
        self._view.centerOn(self._state_manager.clip_rect().center())

    def _delete_selected_items(self):
        """
        Remove os itens selecionados da cena.
        Atualiza o estado de modificação após a remoção.
        """
        selected_data_objects = self._scene_controller.get_selected_data_objects()
        if not selected_data_objects:
            self._set_status_message("Nenhum item selecionado para excluir.", 2000)
            return

        removed_count = self._scene_controller.remove_data_objects(
            selected_data_objects
        )
        if removed_count > 0:
            self._view.viewport().update()
            self._set_status_message(f"{removed_count} item(ns) excluído(s).", 2000)

    def _clear_scene_confirmed(self):
        """
        Limpa a cena após confirmação do usuário.
        Remove todos os objetos e reseta o estado.
        """
        self._drawing_controller.cancel_current_drawing()
        self._scene_controller.clear_scene()
        self._reset_view()
        self._state_manager.mark_as_saved()
        self._state_manager.set_current_filepath(None)
        self._set_status_message("Nova cena criada.", 2000)

    def _prompt_clear_scene(self):
        """
        Solicita confirmação do usuário antes de limpar a cena.
        Verifica se há alterações não salvas antes de prosseguir.
        """
        self._drawing_controller.cancel_current_drawing()
        if self._check_unsaved_changes("limpar a cena"):
            self._clear_scene_confirmed()

    def _select_drawing_color(self):
        """
        Abre o diálogo de seleção de cor para o desenho.
        Atualiza a cor atual de desenho após a seleção.
        """
        initial_color = self._state_manager.draw_color()
        new_color = QColorDialog.getColor(
            initial_color, self, "Selecionar Cor de Desenho"
        )
        if new_color.isValid():
            self._state_manager.set_draw_color(new_color)

    def _set_status_message(self, message: str, timeout: int = 3000):
        """
        Define uma mensagem temporária na barra de status.
        
        Args:
            message: Mensagem a ser exibida
            timeout: Tempo em milissegundos para exibir a mensagem
        """
        if not hasattr(self, "_ui_manager") or self._ui_manager is None:
            return
        self._ui_manager.update_status_bar_message(message)
        self._status_reset_timer.stop()
        if timeout > 0:
            self._status_reset_timer.start(timeout)

    def _update_window_title(self, *args):
        """
        Atualiza o título da janela com informações do estado atual.
        Inclui nome do arquivo e indicador de modificações não salvas.
        """
        title = "Editor Gráfico 2D - "
        filepath = self._state_manager.current_filepath()
        filename = os.path.basename(filepath) if filepath else "Nova Cena"
        title += filename
        if self._state_manager.has_unsaved_changes():
            title += " *"
        self.setWindowTitle(title)

    def _check_unsaved_changes(self, action_description: str = "prosseguir") -> bool:
        """
        Verifica se há alterações não salvas antes de executar uma ação.
        
        Args:
            action_description: Descrição da ação que será executada
            
        Returns:
            bool: True se pode prosseguir, False se deve cancelar
        """
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
            if hasattr(self, "_file_operation_service"):
                return self._file_operation_service.save_current_file()
            else:
                QMessageBox.critical(
                    self, "Erro", "Serviço de arquivo não inicializado."
                )
                return False
        elif reply == QMessageBox.Discard:
            return True
        else:  # Cancel
            return False

    def _open_coordinate_input_dialog(self):
        """
        Abre o diálogo de entrada de coordenadas.
        Permite ao usuário inserir coordenadas precisas para novos objetos.
        """
        self._drawing_controller.cancel_current_drawing()
        dialog_mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
            DrawingMode.BEZIER: "bezier",
        }
        default_mode = dialog_mode_map.get(
            self._state_manager.drawing_mode(), "polygon"
        )
        dialog = CoordinateInputDialog(self, mode=default_mode)
        dialog.set_initial_color(self._state_manager.draw_color())

        if dialog.exec_() == QDialog.Accepted:
            try:
                result_data = dialog.get_validated_data()
                if result_data:
                    data_object = self._create_data_object_from_dialog(
                        result_data, dialog.mode
                    )
                    if data_object:
                        self._scene_controller.add_object(data_object)
            except ValueError as e:
                QMessageBox.warning(self, "Erro ao Criar Objeto", f"{e}")
            except Exception as e:
                QMessageBox.critical(self, "Erro Interno", f"Erro inesperado: {e}")

    def _create_data_object_from_dialog(
        self, result_data: Dict[str, Any], dialog_mode_str: str
    ) -> Optional[DataObject]:
        """
        Cria um objeto de dados baseado nos resultados do diálogo.
        
        Args:
            result_data: Dados inseridos pelo usuário
            dialog_mode_str: Modo do diálogo que gerou os dados
            
        Returns:
            Optional[DataObject]: Objeto criado ou None se inválido
        """
        color = result_data.get("color", QColor(Qt.black))
        coords = result_data.get("coords", [])
        if not coords:
            raise ValueError("Coordenadas ausentes.")
        try:
            if dialog_mode_str == "point":
                return Point(coords[0][0], coords[0][1], color=color)
            elif dialog_mode_str == "line":
                return Line(
                    Point(coords[0][0], coords[0][1]),
                    Point(coords[1][0], coords[1][1]),
                    color=color,
                )
            elif dialog_mode_str == "polygon":
                return Polygon(
                    [Point(x, y) for x, y in coords],
                    is_open=result_data.get("is_open", False),
                    color=color,
                    is_filled=result_data.get("is_filled", False),
                )
            elif dialog_mode_str == "bezier":
                return BezierCurve([Point(x, y) for x, y in coords], color=color)
            else:
                raise ValueError(f"Modo desconhecido: {dialog_mode_str}")
        except ValueError as e:
            raise ValueError(f"Erro ao criar {dialog_mode_str}: {e}")

    def _open_transformation_dialog(self):
        """
        Abre o diálogo de transformação para objetos selecionados.
        Permite aplicar transformações geométricas aos objetos.
        """
        selected_objects = self._scene_controller.get_selected_data_objects()
        if len(selected_objects) != 1:
            QMessageBox.warning(
                self,
                "Seleção Inválida",
                "Selecione exatamente UM objeto para transformar.",
            )
            return
        data_object = selected_objects[0]
        self._drawing_controller.cancel_current_drawing()
        self._transformation_controller.request_transformation(data_object)

    def _handle_load_obj_action(self):
        """
        Manipula a ação de carregar arquivo OBJ.
        Verifica alterações não salvas e carrega o arquivo selecionado.
        """
        filepath, num_added, num_clipped_out, warnings = (
            self._file_operation_service.prompt_load_obj()
        )

        if filepath:
            self._report_load_results(filepath, num_added, num_clipped_out, warnings)
        elif warnings:
            self._set_status_message(
                warnings[0] if warnings else "Carregamento cancelado.", 3000
            )

    def _report_load_results(
        self,
        obj_filepath: str,
        num_added: int,
        num_clipped_out: int,
        warnings: List[str],
    ):
        """
        Reporta os resultados do carregamento de um arquivo OBJ.
        
        Args:
            obj_filepath: Caminho do arquivo carregado
            num_added: Número de objetos adicionados
            num_clipped_out: Número de objetos recortados
            warnings: Lista de avisos gerados durante o carregamento
        """
        base_filename = (
            os.path.basename(obj_filepath) if obj_filepath else "desconhecido"
        )
        if num_added == 0 and num_clipped_out == 0 and not warnings:
            msg = f"Nenhum objeto suportado encontrado ou adicionado de '{base_filename}'."
            if (
                obj_filepath
                and os.path.exists(obj_filepath)
                and os.path.getsize(obj_filepath) > 0
            ):
                QMessageBox.information(self, "Arquivo Vazio ou Não Suportado", msg)
            self._set_status_message(
                self._ui_manager.status_message_label.text()
                if "Falha ao ler" in self._ui_manager.status_message_label.text()
                else "Carregamento concluído (sem geometria adicionada)."
            )
        else:
            final_message = f"Carregado: {num_added} objeto(s) de '{base_filename}'."
            if num_clipped_out > 0:
                final_message += (
                    f" ({num_clipped_out} totalmente fora da viewport ou inválido(s))."
                )
            if warnings:
                max_warnings_display = 15
                formatted_warnings = "- " + "\n- ".join(warnings[:max_warnings_display])
                if len(warnings) > max_warnings_display:
                    formatted_warnings += (
                        f"\n- ... ({len(warnings) - max_warnings_display} mais)"
                    )
                QMessageBox.warning(
                    self,
                    "Carregado com Avisos",
                    f"{final_message}\n\nAvisos:\n{formatted_warnings}",
                )
                final_message += " (com avisos)"
            self._set_status_message(final_message, 5000)

    def _report_save_results(
        self,
        base_filepath: str,
        success: bool,
        warnings: List[str],
        has_mtl: bool = False,
        is_generation_error: bool = False,
    ):
        """
        Reporta os resultados do salvamento de um arquivo.
        
        Args:
            base_filepath: Caminho base do arquivo
            success: Indica se o salvamento foi bem sucedido
            warnings: Lista de avisos gerados durante o salvamento
            has_mtl: Indica se um arquivo MTL foi gerado
            is_generation_error: Indica se houve erro na geração do arquivo
        """
        base_filename = os.path.basename(base_filepath)
        if not success and not warnings:
            self._set_status_message(
                f"Falha ao escrever arquivo(s) para '{base_filename}'.", 3000
            )
            return

        if not success and warnings:
            msg = f"Falha ao salvar dados para '{base_filename}'."
            msg += "\n\nAvisos/Erros:\n- " + "\n- ".join(warnings)
            QMessageBox.critical(self, "Erro ao Salvar Arquivo", msg)
            self._set_status_message(f"Erro ao salvar '{base_filename}'.", 3000)
        elif success:
            obj_name = base_filename + ".obj"
            msg = f"Cena salva como '{obj_name}'"
            if has_mtl:
                msg += f" e '{base_filename}.mtl'"
            msg += "."
            if warnings:
                max_warnings_display = 15
                formatted = "\n\nAvisos:\n- " + "\n- ".join(
                    warnings[:max_warnings_display]
                )
                if len(warnings) > max_warnings_display:
                    formatted += (
                        f"\n- ... ({len(warnings) - max_warnings_display} mais)"
                    )
                QMessageBox.warning(self, "Salvo com Avisos", f"{msg}{formatted}")
                msg += " (com avisos)"
            self._set_status_message(msg, 5000)

    def _toggle_viewport_visibility(self, checked: bool):
        """
        Alterna a visibilidade do retângulo de recorte.
        
        Args:
            checked: Estado do checkbox de visibilidade
        """
        self._clip_rect_item.setVisible(checked)
        self._ui_manager.update_viewport_action_state(checked)
        # Changing viewport visibility might affect how users perceive clipping,
        # but doesn't change the actual clipping logic. Re-clipping not strictly needed here.
        # If appearance of _clip_rect_item itself affects objects, then scene->update()
        self._scene.update()

    def _update_clip_rect_item(self, rect: QRectF):
        """
        Atualiza o retângulo de recorte na cena.
        
        Args:
            rect: Novo retângulo de recorte
        """
        normalized_rect = rect.normalized()
        if self._clip_rect_item.rect() != normalized_rect:
            self._clip_rect_item.setRect(normalized_rect)
        # The actual re-clipping of objects is handled by SceneController
        # in response to state_manager.clip_rect_changed.

    def _prompt_polygon_properties(self):
        """
        Solicita propriedades adicionais para um polígono.
        Permite definir preenchimento e outras características.
        """
        type_reply = QMessageBox.question(
            self,
            "Tipo de Polígono",
            "Deseja criar uma Polilinha (ABERTA)?\n\n"
            "- Sim: Polilinha (>= 2 pontos).\n"
            "- Não: Polígono Fechado (>= 3 pontos).\n\n"
            "(Clique com o botão direito para finalizar)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No,
        )

        if type_reply == QMessageBox.Cancel:
            self._drawing_controller.set_pending_polygon_properties(
                False, False, cancelled=True
            )
            return

        is_open = type_reply == QMessageBox.Yes
        is_filled = False

        if not is_open:
            fill_reply = QMessageBox.question(
                self,
                "Preenchimento",
                "Deseja preencher o polígono fechado?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.No,
            )
            if fill_reply == QMessageBox.Cancel:
                self._drawing_controller.set_pending_polygon_properties(
                    False, False, cancelled=True
                )
                return
            is_filled = fill_reply == QMessageBox.Yes

        self._drawing_controller.set_pending_polygon_properties(is_open, is_filled)

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Manipula o evento de fechamento da janela.
        Verifica alterações não salvas antes de fechar.
        
        Args:
            event: Evento de fechamento
        """
        self._drawing_controller.cancel_current_drawing()
        if self._check_unsaved_changes("fechar a aplicação"):
            event.accept()
        else:
            event.ignore()
