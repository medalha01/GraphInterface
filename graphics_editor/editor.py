# graphics_editor/editor.py
import sys
import os
import numpy as np
import math  # Adicionado para math.degrees
from enum import Enum, auto
from typing import List, Optional, Tuple, Dict, Union, Any, Callable
from PyQt5.QtCore import Qt, QPoint, QRect
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
from PyQt5.QtCore import (
    QPointF,
    Qt,
    pyqtSignal,
    QSize,
    QLineF,
    QRectF,
    QTimer,
    QLocale,
    QSignalBlocker,
)
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
    QVector3D,
    QResizeEvent,
    QShowEvent,  # Adicionado QShowEvent
)
from PyQt5.QtWidgets import QApplication

# Importações relativas dentro do pacote
from .view.main_view import GraphicsView
from .models import Point, Line, Polygon, BezierCurve, BSplineCurve
from .models.ponto3d import Ponto3D
from .models.objeto3d import Objeto3D
from .dialogs.coordinates_input import CoordinateInputDialog
from .dialogs.transformation_dialog import TransformationDialog
from .dialogs.camera_dialog import CameraDialog
from .controllers.transformation_controller import (
    TransformationController,
    TransformableObject2D,
    TransformableObject3D,
    AnyTransformableObject,
)
from .io_handler import IOHandler
from .object_manager import ObjectManager
from .utils import clipping as clp
from .utils import transformations_3d as tf3d

from .state_manager import (
    EditorStateManager,
    DrawingMode,
    LineClippingAlgorithm,
    ProjectionMode,
)
from .controllers.drawing_controller import DrawingController
from .controllers.scene_controller import (
    SceneController,
    SC_ORIGINAL_OBJECT_KEY,
    AnyDataObject,
)
from .ui_manager import UIManager
from .services.file_operation_service import FileOperationService

DATA_OBJECT_TYPES_3D = (Ponto3D, Objeto3D)


class GraphicsEditor(QMainWindow):
    BEZIER_CLIPPING_SAMPLES_PER_SEGMENT = 20
    BEZIER_SAVE_SAMPLES_PER_SEGMENT = 20
    BSPLINE_SAVE_SAMPLES_PER_SEGMENT = 20
    BSPLINE_CLIPPING_SAMPLES = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Editor Gráfico 2D/3D - Nova Cena")
        self.resize(1200, 800)

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
        self._update_3d_status_bar_info()
        # _update_aspect_ratio() será chamado no showEvent ou resizeEvent

    def _setup_core_components(self) -> None:
        self._scene = QGraphicsScene(self)
        self._scene.setSceneRect(-50000, -50000, 100000, 100000)
        self._view = GraphicsView(self._scene, self)
        self.setCentralWidget(self._view)

    def _setup_managers_controllers_services(self) -> None:
        self._state_manager = EditorStateManager(self)
        self._ui_manager = UIManager(self, self._state_manager)
        self._drawing_controller = DrawingController(
            self._scene, self._state_manager, self
        )
        self._transformation_controller = TransformationController(self)
        self._io_handler = IOHandler(self)
        self._object_manager = ObjectManager(
            bezier_samples=self.BEZIER_SAVE_SAMPLES_PER_SEGMENT,
            bspline_samples=self.BSPLINE_SAVE_SAMPLES_PER_SEGMENT,
        )
        self._scene_controller = SceneController(self._scene, self._state_manager, self)
        self._scene_controller.bezier_clipping_samples_per_segment = (
            self.BEZIER_CLIPPING_SAMPLES_PER_SEGMENT
        )
        self._scene_controller.bspline_clipping_samples = self.BSPLINE_CLIPPING_SAMPLES

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
        self._clip_rect_item = QGraphicsRectItem(self._state_manager.clip_rect())
        pen = QPen(QColor(0, 0, 255, 100), 1, Qt.DashLine)
        pen.setCosmetic(True)
        self._clip_rect_item.setPen(pen)
        self._clip_rect_item.setBrush(QBrush(Qt.NoBrush))
        self._clip_rect_item.setZValue(-1)
        self._clip_rect_item.setData(Qt.UserRole + 100, "viewport_rect_2d")
        self._scene.addItem(self._clip_rect_item)

    def _setup_ui_elements(self) -> None:
        menu_callbacks = {
            "new_scene": self._prompt_clear_scene,
            "load_obj": self._handle_load_obj_action,
            "save_as_obj": self._file_operation_service.prompt_save_as_obj,
            "exit": self.close,
            "delete_selected": self._delete_selected_items,
            "transform_object": self._open_transformation_dialog,
            "reset_view": self._reset_view,
            "toggle_viewport": self._toggle_viewport_visibility,
            "create_cube_3d": self._create_cube_3d,
            "create_pyramid_3d": self._create_pyramid_3d,
            "set_camera_3d": self._open_camera_dialog,
            "reset_camera_3d": self._reset_camera_3d,
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
        self._update_view_interaction()
        self._update_window_title()
        QTimer.singleShot(0, self._update_view_controls)

    def _connect_signals(self) -> None:
        self._view.scene_left_clicked.connect(self._handle_scene_left_click)
        self._view.scene_right_clicked.connect(self._handle_scene_right_click)
        self._view.scene_mouse_moved.connect(self._handle_scene_mouse_move)
        self._view.delete_requested.connect(self._delete_selected_items)
        self._view.scene_mouse_moved.connect(self._ui_manager.update_status_bar_coords)
        self._view.rotation_changed.connect(self._update_view_controls)
        self._view.scale_changed.connect(self._update_view_controls)
        self._view.mouse_drag_event_3d.connect(self._handle_mouse_drag_3d)
        self._view.mouse_wheel_event_3d.connect(self._handle_mouse_wheel_3d)
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
        self._state_manager.clip_rect_changed.connect(self._update_clip_rect_item)
        self._state_manager.drawing_mode_changed.connect(self._update_view_interaction)
        self._state_manager.drawing_mode_changed.connect(
            self._drawing_controller.cancel_current_drawing
        )
        self._state_manager.camera_params_changed.connect(
            self._scene_controller.refresh_all_object_clipping_and_projection
        )
        self._state_manager.camera_params_changed.connect(
            self._update_3d_status_bar_info
        )
        self._state_manager.projection_params_changed.connect(
            self._scene_controller.refresh_all_object_clipping_and_projection
        )
        self._state_manager.projection_params_changed.connect(
            self._update_3d_status_bar_info
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

    def showEvent(self, event: QShowEvent) -> None:
        """Chamado quando a janela é exibida pela primeira vez ou após ser ocultada."""
        super().showEvent(event)
        # Garante que o aspect ratio seja calculado após a janela ter suas dimensões iniciais.
        # Usar QTimer.singleShot pode ser mais robusto se o layout ainda não estiver finalizado.
        QTimer.singleShot(0, self._update_aspect_ratio)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Chamado quando a janela principal é redimensionada."""
        super().resizeEvent(event)
        self._update_aspect_ratio()

    def _update_aspect_ratio(self):
        """Atualiza a proporção da viewport no state_manager para projeção 3D."""
        if (
            not self.centralWidget()
            or not hasattr(self._view, "viewport")
            or not self._view.viewport()
        ):
            return  # View ou viewport ainda não existem
        view_size = self._view.viewport().size()
        current_aspect = self._state_manager.aspect_ratio()
        new_aspect = 1.0  # Padrão

        if view_size.height() > 0:
            new_aspect = float(view_size.width()) / view_size.height()

        if (
            abs(current_aspect - new_aspect) > 1e-6
        ):  # Atualiza apenas se houver mudança significativa
            self._state_manager.set_aspect_ratio(new_aspect)

    def _update_3d_status_bar_info(self):
        vrp = self._state_manager.camera_vrp()
        self._ui_manager.update_status_bar_3d_coords(vrp.x(), vrp.y(), vrp.z(), "VRP")

    def _handle_scene_modification(self, requires_saving: bool):
        if requires_saving:
            self._state_manager.mark_as_modified()

    def _handle_scene_left_click(self, scene_pos: QPointF):
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
        mode = self._state_manager.drawing_mode()
        if mode in [DrawingMode.POLYGON, DrawingMode.BEZIER, DrawingMode.BSPLINE]:
            self._drawing_controller.handle_scene_right_click(scene_pos)

    def _handle_scene_mouse_move(self, scene_pos: QPointF):
        mode = self._state_manager.drawing_mode()
        if mode in [
            DrawingMode.LINE,
            DrawingMode.POLYGON,
            DrawingMode.BEZIER,
            DrawingMode.BSPLINE,
        ]:
            self._drawing_controller.handle_scene_mouse_move(scene_pos)

    def _handle_mouse_drag_3d(
        self,
        prev_pos_vp: QPoint,
        current_pos_vp: QPoint,
        buttons: Qt.MouseButtons,
        modifiers: Qt.KeyboardModifiers,
    ):
        dx = current_pos_vp.x() - prev_pos_vp.x()
        dy = current_pos_vp.y() - prev_pos_vp.y()

        vrp = self._state_manager.camera_vrp()
        target = self._state_manager.camera_target()
        vup = self._state_manager.camera_vup()

        if buttons & Qt.MiddleButton and not (modifiers & Qt.ShiftModifier):  # Órbita
            orbit_sensitivity_deg_per_pixel = 0.3
            angle_yaw_deg = (
                -dx * orbit_sensitivity_deg_per_pixel
            )  # Rotação horizontal em torno do VUP global
            angle_pitch_deg = (
                -dy * orbit_sensitivity_deg_per_pixel
            )  # Rotação vertical em torno do eixo "direita" da câmera

            # Vetor do VRP para o Target (em relação ao qual orbitamos)
            to_target_vec = target - vrp

            # Rotação Yaw (horizontal)
            # Rotaciona o vetor (VRP - Target) em torno do VUP global
            # Depois, novo VRP = Target - (vetor rotacionado)
            q_yaw = QQuaternion.fromAxisAndAngle(vup, angle_yaw_deg)
            rotated_to_target_yaw = q_yaw.rotatedVector(to_target_vec)

            # Calcular novo VRP intermediário e o eixo "direita" para Pitch
            temp_vrp_after_yaw = target - rotated_to_target_yaw
            right_axis_cam = QVector3D.crossProduct(
                vup, -rotated_to_target_yaw.normalized()
            ).normalized()  # -view_dir_norm X VUP_global
            if right_axis_cam.isNull():  # Se VUP e direção da visão estiverem alinhados
                right_axis_cam = (
                    QVector3D(1, 0, 0)
                    if abs(vup.y()) < 0.9
                    else QVector3D.crossProduct(
                        QVector3D(0, 0, 1), -rotated_to_target_yaw.normalized()
                    ).normalized()
                )

            # Rotação Pitch (vertical)
            # Rotaciona o `rotated_to_target_yaw` e o `vup` em torno do `right_axis_cam`
            q_pitch = QQuaternion.fromAxisAndAngle(right_axis_cam, angle_pitch_deg)
            final_rotated_to_target = q_pitch.rotatedVector(rotated_to_target_yaw)
            new_vup = q_pitch.rotatedVector(vup)  # Rotaciona VUP também

            new_vrp = target - final_rotated_to_target

            # Validação do VUP para evitar inversão ou alinhamento excessivo com a direção da visão
            if (
                abs(
                    QVector3D.dotProduct(
                        final_rotated_to_target.normalized(), new_vup.normalized()
                    )
                )
                < 0.995
            ):  # Não muito alinhado
                self._state_manager.set_camera_parameters(new_vrp, target, new_vup)
            else:  # Se VUP ficou problemático, reverte a parte do pitch no VUP ou usa VUP original
                self._state_manager.set_camera_parameters(
                    new_vrp,
                    target,
                    q_yaw.rotatedVector(self._state_manager.camera_vup()),
                )

        elif buttons & Qt.MiddleButton and modifiers & Qt.ShiftModifier:  # Pan 3D
            pan_sensitivity = 0.5 * (
                (vrp - target).length() / 200.0
            )  # Sensibilidade proporcional à distância
            pan_sensitivity = max(0.01, pan_sensitivity)  # Mínimo

            n_cam_dir = (target - vrp).normalized()
            u_cam_dir = QVector3D.crossProduct(vup, n_cam_dir).normalized()
            v_cam_dir = QVector3D.crossProduct(n_cam_dir, u_cam_dir)

            pan_vector = (-u_cam_dir * dx * pan_sensitivity) + (
                v_cam_dir * dy * pan_sensitivity
            )

            self._state_manager.set_camera_parameters(
                vrp + pan_vector, target + pan_vector, vup
            )

    def _handle_mouse_wheel_3d(self, delta: int, modifiers: Qt.KeyboardModifiers):
        vrp = self._state_manager.camera_vrp()
        target = self._state_manager.camera_target()
        vup = self._state_manager.camera_vup()

        direction_to_target = target - vrp
        current_distance = direction_to_target.length()
        if current_distance < tf3d.EPSILON:
            return  # Evita problemas se VRP e Target coincidirem

        zoom_speed_factor = 0.15  # Mais sensível
        dolly_amount = (delta / 120.0) * current_distance * zoom_speed_factor

        new_vrp = vrp + direction_to_target.normalized() * dolly_amount

        min_dist = (
            0.1 * self._state_manager.ortho_box_size()
        )  # Dist min baseada no tamanho da ortho box
        min_dist = max(0.1, min_dist)  # Garante um valor mínimo absoluto

        if (target - new_vrp).length() < min_dist and dolly_amount < 0:
            new_vrp = target - direction_to_target.normalized() * min_dist

        self._state_manager.set_camera_parameters(new_vrp, target, vup)

    def _set_drawing_mode(self, mode: DrawingMode):
        self._state_manager.set_drawing_mode(mode)

    def _update_view_interaction(self):
        mode = self._state_manager.drawing_mode()
        if mode == DrawingMode.SELECT:
            self._view.set_drag_mode(QGraphicsView.RubberBandDrag)
        elif mode == DrawingMode.PAN:
            self._view.set_drag_mode(QGraphicsView.ScrollHandDrag)
        else:
            self._view.set_drag_mode(QGraphicsView.NoDrag)

    def _set_line_clipper(self, algorithm: LineClippingAlgorithm):
        self._state_manager.set_selected_line_clipper(algorithm)
        algo_name = (
            "Cohen-Sutherland"
            if algorithm == LineClippingAlgorithm.COHEN_SUTHERLAND
            else "Liang-Barsky"
        )
        self._set_status_message(f"Clipping de linha 2D: {algo_name}", 2000)

    def _on_zoom_slider_changed(self, value: int):
        min_slider, max_slider = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        min_scale, max_scale = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        if max_slider <= min_slider or max_scale <= min_scale or min_scale <= 0:
            return
        log_min, log_max = np.log(min_scale), np.log(max_scale)
        if abs(log_max - log_min) < 1e-9:
            return
        factor = (value - min_slider) / (max_slider - min_slider)
        target_scale = np.exp(log_min + factor * (log_max - log_min))
        self._view.set_scale(target_scale, center_on_mouse=False)

    def _update_view_controls(self):
        self._update_zoom_controls()
        self._update_rotation_controls()

    def _update_zoom_controls(self):
        current_scale = self._view.get_scale()
        min_s, max_s = self._view.VIEW_SCALE_MIN, self._view.VIEW_SCALE_MAX
        min_sl, max_sl = (
            self._ui_manager.SLIDER_RANGE_MIN,
            self._ui_manager.SLIDER_RANGE_MAX,
        )
        slider_val = min_sl
        if max_s > min_s and max_sl > min_sl and current_scale > 0 and min_s > 0:
            log_min, log_max = np.log(min_s), np.log(max_s)
            if abs(log_max - log_min) > 1e-9:
                clamped = np.clip(current_scale, min_s, max_s)
                log_sc = np.log(clamped)
                factor = (log_sc - log_min) / (log_max - log_min)
                slider_val = int(round(min_sl + factor * (max_sl - min_sl)))
        self._ui_manager.update_status_bar_zoom(current_scale, slider_val)

    def _update_rotation_controls(self):
        self._ui_manager.update_status_bar_rotation(self._view.get_rotation_angle())

    def _reset_view(self):
        self._view.reset_view()
        self._view.centerOn(QPointF(0, 0))
        self._set_status_message("Vista 2D resetada para origem.", 2000)

    def _delete_selected_items(self):
        selected = self._scene_controller.get_selected_data_objects()
        if not selected:
            self._set_status_message("Nenhum item selecionado.", 2000)
            return
        count = self._scene_controller.remove_data_objects(selected)
        if count > 0:
            self._set_status_message(f"{count} item(ns) excluído(s).", 2000)

    def _clear_scene_confirmed(self):
        self._drawing_controller.cancel_current_drawing()
        self._scene_controller.clear_scene()
        self._reset_view()
        self._reset_camera_3d()
        self._state_manager.mark_as_saved()
        self._state_manager.set_current_filepath(None)
        self._set_status_message("Nova cena criada.", 2000)

    def _prompt_clear_scene(self):
        self._drawing_controller.cancel_current_drawing()
        if self._check_unsaved_changes("limpar a cena"):
            self._clear_scene_confirmed()

    def _select_drawing_color(self):
        new_color = QColorDialog.getColor(
            self._state_manager.draw_color(), self, "Selecionar Cor"
        )
        if new_color.isValid():
            self._state_manager.set_draw_color(new_color)

    def _set_status_message(self, message: str, timeout: int = 3000):
        if hasattr(self, "_ui_manager") and self._ui_manager:
            self._ui_manager.update_status_bar_message(message)
            self._status_reset_timer.stop()
            if timeout > 0:
                self._status_reset_timer.start(timeout)

    def _update_window_title(self, *args):
        title = "Editor Gráfico 2D/3D - "
        fp = self._state_manager.current_filepath()
        title += os.path.basename(fp) if fp else "Nova Cena"
        if self._state_manager.has_unsaved_changes():
            title += " *"
        self.setWindowTitle(title)

    def _check_unsaved_changes(self, action_desc: str = "prosseguir") -> bool:
        if not self._state_manager.has_unsaved_changes():
            return True
        reply = QMessageBox.warning(
            self,
            "Alterações Não Salvas",
            f"A cena contém alterações não salvas. Deseja salvá-las antes de {action_desc}?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            return (
                hasattr(self, "_file_operation_service")
                and self._file_operation_service.save_current_file()
            )
        return reply == QMessageBox.Discard

    def _open_coordinate_input_dialog(self):
        self._drawing_controller.cancel_current_drawing()
        mode_map = {
            DrawingMode.POINT: "point",
            DrawingMode.LINE: "line",
            DrawingMode.POLYGON: "polygon",
            DrawingMode.BEZIER: "bezier",
            DrawingMode.BSPLINE: "bspline",
        }
        current_2d_mode = self._state_manager.drawing_mode()
        dialog_mode_str = mode_map.get(current_2d_mode, "polygon")
        dialog = CoordinateInputDialog(self, mode=dialog_mode_str)
        dialog.set_initial_color(self._state_manager.draw_color())
        if dialog.exec_() == QDialog.Accepted:
            validated_data = dialog.get_validated_data()
            if validated_data:
                try:
                    data_object_2d = self._create_data_object_from_dialog(
                        validated_data, dialog.mode
                    )
                    if data_object_2d:
                        self._scene_controller.add_object(data_object_2d)
                except (ValueError, TypeError) as e:
                    QMessageBox.warning(self, "Erro ao Criar Objeto 2D", str(e))

    def _create_data_object_from_dialog(
        self, data: Dict[str, Any], mode_str: str
    ) -> Optional[AnyDataObject]:
        color = data.get("color", QColor(Qt.black))
        coords = data.get("coords", [])
        if not coords:
            raise ValueError("Coordenadas ausentes nos dados do diálogo.")
        try:
            if mode_str == "point":
                return Point(coords[0][0], coords[0][1], color=color)
            if mode_str == "line":
                return Line(Point(*coords[0]), Point(*coords[1]), color=color)
            if mode_str == "polygon":
                poly_points = [Point(x, y, color=color) for x, y in coords]
                return Polygon(
                    poly_points,
                    is_open=data.get("is_open", False),
                    color=color,
                    is_filled=data.get("is_filled", False),
                )
            if mode_str == "bezier":
                bezier_points = [Point(x, y, color=color) for x, y in coords]
                return BezierCurve(bezier_points, color=color)
            if mode_str == "bspline":
                bspline_points = [Point(x, y, color=color) for x, y in coords]
                return BSplineCurve(
                    bspline_points, color=color, degree=BSplineCurve.DEFAULT_DEGREE
                )
            raise ValueError(f"Modo de diálogo 2D desconhecido: {mode_str}")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Erro ao criar objeto 2D '{mode_str}': {e}")

    def _open_transformation_dialog(self):
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
        is_3d = isinstance(data_object, DATA_OBJECT_TYPES_3D)
        self._transformation_controller.request_transformation(data_object, is_3d=is_3d)

    def _handle_load_obj_action(self):
        filepath, num_added, num_clipped_out, warnings = (
            self._file_operation_service.prompt_load_obj()
        )
        if filepath:
            self._report_load_results(filepath, num_added, num_clipped_out, warnings)
        elif warnings:
            self._set_status_message(
                warnings[0] if warnings else "Carregamento 2D cancelado.", 3000
            )

    def _report_load_results(
        self,
        obj_filepath: str,
        num_added: int,
        num_clipped_out: int,
        warnings: List[str],
    ):
        base_filename = (
            os.path.basename(obj_filepath) if obj_filepath else "desconhecido"
        )
        if num_added == 0 and num_clipped_out == 0 and not warnings:
            msg = f"Nenhum objeto 2D suportado encontrado ou adicionado de '{base_filename}'."
            current_status = (
                self._ui_manager.status_message_label.text()
                if self._ui_manager.status_message_label
                else ""
            )
            if "Falha ao ler" in current_status:
                self._set_status_message(current_status, 3000)
            else:
                QMessageBox.information(self, "Arquivo Vazio ou Não Suportado", msg)
                self._set_status_message(
                    "Carregamento 2D concluído (sem geometria adicionada).", 3000
                )
        else:
            final_message = (
                f"Carregado (2D): {num_added} objeto(s) de '{base_filename}'."
            )
            if num_clipped_out > 0:
                final_message += (
                    f" ({num_clipped_out} totalmente fora da viewport ou inválido(s))."
                )
            if warnings:
                max_warn_display = 15
                formatted_warns = "- " + "\n- ".join(warnings[:max_warn_display])
                if len(warnings) > max_warn_display:
                    formatted_warns += (
                        f"\n- ... ({len(warnings) - max_warn_display} mais)"
                    )
                QMessageBox.warning(
                    self,
                    "Carregado com Avisos (2D)",
                    f"{final_message}\n\nAvisos:\n{formatted_warns}",
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
        base_filename = os.path.basename(base_filepath)
        if not success and not warnings:
            self._set_status_message(
                f"Falha ao escrever arquivo(s) 2D para '{base_filename}'.", 3000
            )
            return
        if not success and warnings:
            msg = (
                f"Falha ao salvar dados 2D para '{base_filename}'.\n\nAvisos/Erros:\n- "
                + "\n- ".join(warnings)
            )
            QMessageBox.critical(self, "Erro ao Salvar Arquivo 2D", msg)
            self._set_status_message(f"Erro ao salvar '{base_filename}'.", 3000)
        elif success:
            obj_name = base_filename + ".obj"
            msg = (
                f"Cena 2D salva como '{obj_name}'"
                + (f" e '{base_filename}.mtl'" if has_mtl else "")
                + "."
            )
            if warnings:
                max_warn_display = 15
                formatted_warns = "\n\nAvisos:\n- " + "\n- ".join(
                    warnings[:max_warn_display]
                )
                if len(warnings) > max_warn_display:
                    formatted_warns += (
                        f"\n- ... ({len(warnings) - max_warn_display} mais)"
                    )
                QMessageBox.warning(
                    self, "Salvo com Avisos (2D)", f"{msg}{formatted_warns}"
                )
                msg += " (com avisos)"
            self._set_status_message(msg, 5000)

    def _toggle_viewport_visibility(self, checked: bool):
        self._clip_rect_item.setVisible(checked)
        self._ui_manager.update_viewport_action_state(checked)
        self._scene.update()

    def _update_clip_rect_item(self, rect: QRectF):
        normalized_rect = rect.normalized()
        if self._clip_rect_item.rect() != normalized_rect:
            self._clip_rect_item.setRect(normalized_rect)

    def _prompt_polygon_properties(self):
        type_reply = QMessageBox.question(
            self,
            "Tipo de Polígono 2D",
            "Deseja criar uma Polilinha (ABERTA)?\n\n"
            "- Sim: Polilinha (>= 2 pontos).\n"
            "- Não: Polígono Fechado (>= 3 pontos).\n\n"
            "(Clique com o botão direito para finalizar)",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No,
        )
        if type_reply == QMessageBox.Cancel:
            self._drawing_controller.set_pending_polygon_properties(False, False, True)
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
                    False, False, True
                )
                return
            is_filled = fill_reply == QMessageBox.Yes
        self._drawing_controller.set_pending_polygon_properties(is_open, is_filled)

    def _create_object_3d_at_center(self, obj: Objeto3D, name_str: str):
        """Adiciona um objeto 3D e tenta centralizar a câmera nele (simplificado)."""
        self._scene_controller.add_object(obj)  # Adiciona e projeta

        # Heurística para centralizar: move o target da câmera para o centro do objeto.
        # Para uma centralização "real", seria preciso ajustar o VRP ou o zoom/ortho_box_size.
        obj_center_3d_tuple = obj.get_center()
        new_target_qvector = QVector3D(
            obj_center_3d_tuple[0], obj_center_3d_tuple[1], obj_center_3d_tuple[2]
        )

        current_vrp = self._state_manager.camera_vrp()
        current_vup = self._state_manager.camera_vup()

        # Apenas atualiza o target, mantendo VRP e VUP.
        # Isso fará a câmera "olhar para" o centro do novo objeto.
        # Se o objeto estiver muito longe, pode ser necessário ajustar o VRP também.
        if (
            current_vrp - new_target_qvector
        ).lengthSquared() > tf3d.EPSILON:  # Evita VRP == Target
            self._state_manager.set_camera_parameters(
                current_vrp, new_target_qvector, current_vup
            )

        self._set_status_message(f"{name_str} 3D criado e câmera focada.", 2000)

    def _create_cube_3d(self):
        color = self._state_manager.draw_color()
        s = 50.0
        pts_data = [
            (-s / 2, -s / 2, -s / 2),
            (s / 2, -s / 2, -s / 2),
            (s / 2, s / 2, -s / 2),
            (-s / 2, s / 2, -s / 2),
            (-s / 2, -s / 2, s / 2),
            (s / 2, -s / 2, s / 2),
            (s / 2, s / 2, s / 2),
            (-s / 2, s / 2, s / 2),
        ]
        pts = [Ponto3D(x, y, z, color) for x, y, z in pts_data]
        segs = [
            (pts[0], pts[1]),
            (pts[1], pts[2]),
            (pts[2], pts[3]),
            (pts[3], pts[0]),
            (pts[4], pts[5]),
            (pts[5], pts[6]),
            (pts[6], pts[7]),
            (pts[7], pts[4]),
            (pts[0], pts[4]),
            (pts[1], pts[5]),
            (pts[2], pts[6]),
            (pts[3], pts[7]),
        ]
        cube = Objeto3D("Cubo", segs, color)
        self._create_object_3d_at_center(cube, "Cubo")

    def _create_pyramid_3d(self):
        color = self._state_manager.draw_color()
        base_size = 80.0
        height = 100.0
        s = base_size / 2.0
        pts_data = [(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0), (0, 0, height)]
        pts = [Ponto3D(x, y, z, color) for x, y, z in pts_data]
        segs = [
            (pts[0], pts[1]),
            (pts[1], pts[2]),
            (pts[2], pts[3]),
            (pts[3], pts[0]),
            (pts[0], pts[4]),
            (pts[1], pts[4]),
            (pts[2], pts[4]),
            (pts[3], pts[4]),
        ]
        pyramid = Objeto3D("Piramide", segs, color)
        self._create_object_3d_at_center(pyramid, "Pirâmide")

    def _open_camera_dialog(self):
        dialog = CameraDialog(
            self._state_manager.camera_vrp(),
            self._state_manager.camera_target(),
            self._state_manager.camera_vup(),
            parent=self,
        )
        if dialog.exec_() == QDialog.Accepted:
            vrp, target, vup = dialog.get_camera_parameters()
            self._state_manager.set_camera_parameters(vrp, target, vup)
            self._set_status_message("Câmera 3D atualizada.", 2000)

    def _reset_camera_3d(self):
        self._state_manager.set_camera_parameters(
            EditorStateManager.DEFAULT_CAMERA_VRP,
            EditorStateManager.DEFAULT_CAMERA_TARGET,
            EditorStateManager.DEFAULT_CAMERA_VUP,
        )
        # Também reseta o zoom ortográfico para o padrão
        self._state_manager.set_ortho_box_size(
            EditorStateManager.DEFAULT_ORTHO_BOX_SIZE
        )
        self._state_manager.set_fov_degrees(
            EditorStateManager.DEFAULT_FOV_DEGREES
        )  # Para perspectiva

        self._set_status_message("Câmera 3D e projeção resetadas.", 2000)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._drawing_controller.cancel_current_drawing()
        if self._check_unsaved_changes("fechar a aplicação"):
            event.accept()
        else:
            event.ignore()
