# graphics_editor/controllers/scene_controller.py
import math
from typing import List, Tuple, Dict, Union, Optional, Callable
from enum import Enum
from PyQt5.QtWidgets import (
    QGraphicsScene,
    QGraphicsItem,
    QMessageBox,
    QGraphicsPathItem,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
)
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QRectF, QLineF, QPointF
from PyQt5.QtGui import (
    QColor,
    QPen,
    QBrush,
    QPolygonF,
    QPainterPath,
    QVector3D,
    QMatrix4x4,
)

from ..models import Point, Line, Polygon, BezierCurve, BSplineCurve  # Modelos 2D
from ..models.point3D import Point3D  # Modelo 3D
from ..models.geometric_shape_3D import GeometricShape3D  # Modelo 3D
from ..models import __all__ as model_names_list  # Para obter todos os nomes de modelos

_models_module = __import__("graphics_editor.models", fromlist=model_names_list)
# Tipos de dados que SceneController pode manipular (2D e 3D)
DATA_OBJECT_TYPES_ALL = tuple(
    getattr(_models_module, name) for name in model_names_list
)
DATA_OBJECT_TYPES_2D = (Point, Line, Polygon, BezierCurve, BSplineCurve)
DATA_OBJECT_TYPES_3D = (Point3D, GeometricShape3D)

AnyDataObject = Union[
    Point, Line, Polygon, BezierCurve, BSplineCurve, Point3D, GeometricShape3D
]

from ..state_manager import EditorStateManager, LineClippingAlgorithm, ProjectionMode
from ..utils import clipping as clp  # Clipping 2D
from ..utils import transformations_3d as tf3d  # Transformações e projeção 3D

SC_ORIGINAL_OBJECT_KEY = Qt.UserRole + 1
SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY = Qt.UserRole + 2
SC_CURRENT_REPRESENTATION_KEY = Qt.UserRole + 3
SC_IS_PROJECTED_3D_KEY = Qt.UserRole + 4


class BezierClipStatus(Enum):
    """
    Enumeração que representa o status de recorte de uma curva de Bézier em relação à janela de visualização.

    Atributos:
        FULLY_INSIDE: Curva completamente dentro da janela de visualização
        FULLY_OUTSIDE: Curva completamente fora da janela de visualização
        PARTIALLY_INSIDE: Curva parcialmente dentro da janela de visualização
    """

    FULLY_INSIDE = 1
    FULLY_OUTSIDE = 2
    PARTIALLY_INSIDE = 3


class SceneController(QObject):
    """
    Controlador responsável por gerenciar a cena gráfica e suas interações.

    Esta classe coordena a exibição e manipulação de objetos gráficos na cena,
    incluindo operações de recorte, atualização e gerenciamento de estado.

    Atributos:
        scene_modified: Sinal emitido quando a cena é modificada
    """

    scene_modified = pyqtSignal(bool)

    def __init__(
        self,
        scene: QGraphicsScene,
        state_manager: EditorStateManager,
        parent: Optional[QObject] = None,
    ):
        """
        Inicializa o controlador da cena.

        Args:
            scene: A cena gráfica a ser controlada
            state_manager: Gerenciador de estado do editor
            parent: Objeto pai opcional
        """
        super().__init__(parent)
        self._scene = scene
        self._state_manager = state_manager
        self._id_to_item_map: Dict[int, QGraphicsItem] = {}

        self._clip_rect_tuple_2d: clp.ClipRect = clp.qrectf_to_cliprect(
            self._state_manager.clip_rect()
        )
        self._line_clipper_func_2d: Callable[
            [clp.Point2D, clp.Point2D, clp.ClipRect],
            Optional[Tuple[clp.Point2D, clp.Point2D]],
        ] = self._get_2d_line_clipper_function()
        self.bezier_clipping_samples_per_segment: int = 20
        self.bspline_clipping_samples: int = 100

        self._state_manager.clip_rect_changed.connect(
            self._on_2d_clipping_params_changed
        )
        self._state_manager.line_clipper_changed.connect(
            self._on_2d_clipping_params_changed
        )
        self._state_manager.camera_params_changed.connect(
            self.refresh_all_object_clipping_and_projection
        )
        self._state_manager.projection_params_changed.connect(
            self.refresh_all_object_clipping_and_projection
        )

    def _on_2d_clipping_params_changed(self, *args):
        self._clip_rect_tuple_2d = clp.qrectf_to_cliprect(
            self._state_manager.clip_rect()
        )
        self._line_clipper_func_2d = self._get_2d_line_clipper_function()
        self.refresh_all_object_clipping_and_projection()

    def refresh_all_object_clipping_and_projection(self):
        """
        Atualiza o recorte de todos os objetos na cena.
        """
        original_objects_to_refresh = list(self.get_all_original_data_objects())
        for original_data_object in original_objects_to_refresh:
            self.update_object_item(original_data_object, mark_modified=False)
        self._scene.update()

    def _get_2d_line_clipper_function(
        self,
    ) -> Callable[
        [clp.Point2D, clp.Point2D, clp.ClipRect],
        Optional[Tuple[clp.Point2D, clp.Point2D]],
    ]:
        algo = self._state_manager.selected_line_clipper()
        if algo == LineClippingAlgorithm.COHEN_SUTHERLAND:
            return clp.cohen_sutherland
        else:
            return clp.liang_barsky

    def _get_bezier_segment_clip_status(
        self, segment_cps: List[Point], clip_rect_tuple: clp.ClipRect
    ) -> BezierClipStatus:
        """
        Determina o status de recorte de um segmento de curva de Bézier.

        Args:
            segment_cps: Lista de pontos de controle do segmento
            clip_rect_tuple: Tupla com as coordenadas da janela de recorte

        Returns:
            Status de recorte do segmento (FULLY_INSIDE, FULLY_OUTSIDE ou PARTIALLY_INSIDE)
        """
        xmin, ymin, xmax, ymax = clip_rect_tuple
        all_inside = True
        codes = [
            clp._compute_cohen_sutherland_code(p.x, p.y, clip_rect_tuple)
            for p in segment_cps
        ]
        for code in codes:
            if code != clp.INSIDE:
                all_inside = False
                break
        if all_inside:
            return BezierClipStatus.FULLY_INSIDE
        combined_code_for_all_outside_check = codes[0]
        for i in range(1, len(codes)):
            combined_code_for_all_outside_check &= codes[i]
        if combined_code_for_all_outside_check != 0:
            bbox = BezierCurve.segment_bounding_box(segment_cps)
            if bbox and (
                bbox[2] < xmin or bbox[0] > xmax or bbox[3] < ymin or bbox[1] > ymax
            ):
                return BezierClipStatus.FULLY_OUTSIDE
        return BezierClipStatus.PARTIALLY_INSIDE

    def _clip_bezier_segment_recursive(
        self, segment_cps: List[Point], clip_rect_tuple: clp.ClipRect, depth: int
    ) -> List[List[Point]]:
        """
        Recorta recursivamente um segmento de curva de Bézier.

        Args:
            segment_cps: Lista de pontos de controle do segmento
            clip_rect_tuple: Tupla com as coordenadas da janela de recorte
            depth: Profundidade atual da recursão

        Returns:
            Lista de listas de pontos de controle dos segmentos visíveis após o recorte
        """
        visible_segments_cps: List[List[Point]] = []
        if (
            depth > BezierCurve.MAX_SUBDIVISION_DEPTH
            or BezierCurve.segment_control_polygon_length(segment_cps)
            < BezierCurve.SUBDIVISION_THRESHOLD
        ):
            status_small_segment = self._get_bezier_segment_clip_status(
                segment_cps, clip_rect_tuple
            )
            if status_small_segment != BezierClipStatus.FULLY_OUTSIDE:
                visible_segments_cps.append(segment_cps)
            return visible_segments_cps
        status = self._get_bezier_segment_clip_status(segment_cps, clip_rect_tuple)
        if status == BezierClipStatus.FULLY_INSIDE:
            visible_segments_cps.append(segment_cps)
        elif status == BezierClipStatus.PARTIALLY_INSIDE:
            cps1, cps2 = BezierCurve.subdivide_segment(segment_cps)
            visible_segments_cps.extend(
                self._clip_bezier_segment_recursive(cps1, clip_rect_tuple, depth + 1)
            )
            visible_segments_cps.extend(
                self._clip_bezier_segment_recursive(cps2, clip_rect_tuple, depth + 1)
            )
        return visible_segments_cps

    def _clip_or_project_data_object(
        self, original_data_object: AnyDataObject
    ) -> Tuple[Optional[AnyDataObject], bool]:
        """
        Recorta um objeto de dados de acordo com a janela de visualização.

        Args:
            original_data_object: Objeto a ser recortado

        Returns:
            Tupla contendo o objeto recortado (ou None se completamente fora da janela)
            e um booleano indicando se o tipo de exibição foi alterado
        """
        display_object: Optional[AnyDataObject] = None
        display_type_changed = False

        if isinstance(original_data_object, DATA_OBJECT_TYPES_2D):
            clip_rect_2d = self._clip_rect_tuple_2d
            line_clipper_2d = self._line_clipper_func_2d
            try:
                if isinstance(original_data_object, Point):
                    coords = original_data_object.get_coords()
                    if clp.clip_point(coords, clip_rect_2d):
                        display_object = original_data_object
                elif isinstance(original_data_object, Line):
                    p1c, p2c = (
                        original_data_object.start.get_coords(),
                        original_data_object.end.get_coords(),
                    )
                    clipped_line_coords = line_clipper_2d(p1c, p2c, clip_rect_2d)
                    if clipped_line_coords:
                        display_object = Line(
                            Point(*clipped_line_coords[0]),
                            Point(*clipped_line_coords[1]),
                            original_data_object.color,
                        )
                elif isinstance(original_data_object, Polygon):
                    clipped_poly_coords = clp.sutherland_hodgman(
                        original_data_object.get_coords(), clip_rect_2d
                    )
                    min_pts_required = 2 if original_data_object.is_open else 3
                    if len(clipped_poly_coords) >= min_pts_required:
                        clipped_points_models = [
                            Point(x, y, original_data_object.color)
                            for x, y in clipped_poly_coords
                        ]
                        display_object = Polygon(
                            clipped_points_models,
                            is_open=original_data_object.is_open,
                            color=original_data_object.color,
                            is_filled=original_data_object.is_filled,
                        )
                elif isinstance(original_data_object, BezierCurve):
                    all_visible_cps_lists: List[List[Point]] = []
                    for i in range(original_data_object.get_num_segments()):
                        segment_cps = original_data_object.get_segment_control_points(i)
                        if segment_cps:
                            visible_sub_cps = self._clip_bezier_segment_recursive(
                                segment_cps, clip_rect_2d, 0
                            )
                            all_visible_cps_lists.extend(visible_sub_cps)
                    if all_visible_cps_lists:
                        sampled_points_for_display: List[QPointF] = []
                        for cps_list_for_segment in all_visible_cps_lists:
                            temp_bezier = BezierCurve(
                                cps_list_for_segment, original_data_object.color
                            )
                            segment_samples = temp_bezier.sample_curve(
                                self.bezier_clipping_samples_per_segment
                            )
                            if (
                                sampled_points_for_display
                                and segment_samples
                                and math.isclose(
                                    sampled_points_for_display[-1].x(),
                                    segment_samples[0].x(),
                                )
                                and math.isclose(
                                    sampled_points_for_display[-1].y(),
                                    segment_samples[0].y(),
                                )
                            ):
                                sampled_points_for_display.extend(segment_samples[1:])
                            elif segment_samples:
                                sampled_points_for_display.extend(segment_samples)
                        if len(sampled_points_for_display) >= 2:
                            model_points_for_polygon = [
                                Point(qp.x(), qp.y(), original_data_object.color)
                                for qp in sampled_points_for_display
                            ]
                            display_object = Polygon(
                                model_points_for_polygon,
                                is_open=True,
                                color=original_data_object.color,
                            )
                            display_type_changed = True
                elif isinstance(original_data_object, BSplineCurve):
                    sampled_coords = original_data_object.get_curve_points(
                        self.bspline_clipping_samples
                    )
                    if sampled_coords:
                        clipped_bsp_coords = clp.sutherland_hodgman(
                            sampled_coords, clip_rect_2d
                        )
                        if len(clipped_bsp_coords) >= 2:
                            points_for_polygon = [
                                Point(x, y, original_data_object.color)
                                for x, y in clipped_bsp_coords
                            ]
                            display_object = Polygon(
                                points_for_polygon,
                                is_open=True,
                                color=original_data_object.color,
                            )
                            display_type_changed = True
            except Exception as e:
                print(
                    f"Erro durante o recorte 2D de {type(original_data_object).__name__}: {e}"
                )
                return None, False
        elif isinstance(original_data_object, DATA_OBJECT_TYPES_3D):
            vrp = self._state_manager.camera_vrp()
            target = self._state_manager.camera_target()
            vup = self._state_manager.camera_vup()
            view_matrix = tf3d.create_view_matrix(vrp, target, vup)
            proj_matrix: np.ndarray
            if self._state_manager.projection_mode() == ProjectionMode.ORTHOGRAPHIC:
                s = self._state_manager.ortho_box_size() / 2.0
                aspect = self._state_manager.aspect_ratio()
                near, far = (
                    self._state_manager.near_plane(),
                    self._state_manager.far_plane(),
                )
                proj_matrix = tf3d.create_orthographic_projection_matrix(
                    -s * aspect, s * aspect, -s, s, near, far
                )
            else:
                fov_y_deg = self._state_manager.fov_degrees()
                aspect = self._state_manager.aspect_ratio()
                near, far = (
                    self._state_manager.near_plane(),
                    self._state_manager.far_plane(),
                )
                proj_matrix = tf3d.create_perspective_projection_matrix(
                    fov_y_deg, aspect, near, far
                )

            scene_rect_for_viewport = self._state_manager.clip_rect()
            # Passa os quatro parâmetros para viewport_transform_matrix
            viewport_rect_params = (
                scene_rect_for_viewport.x(),
                scene_rect_for_viewport.y(),
                scene_rect_for_viewport.width(),
                scene_rect_for_viewport.height(),
            )
            model_matrix = tf3d.create_identity_matrix_3d()

            if isinstance(original_data_object, Point3D):
                p_coords_3d = original_data_object.get_coords()
                q_point_f_2d = tf3d.project_point_3d_to_qpointf(
                    p_coords_3d,
                    model_matrix,
                    view_matrix,
                    proj_matrix,
                    viewport_rect_params,
                )
                if q_point_f_2d:
                    display_object = Point(
                        q_point_f_2d.x(), q_point_f_2d.y(), original_data_object.color
                    )
                    display_type_changed = True
            elif isinstance(original_data_object, GeometricShape3D):
                display_object = original_data_object
                display_type_changed = True
        return display_object, display_type_changed

    def _get_required_qgraphicsitem_type(
        self, display_data_object: AnyDataObject, is_projected_3d_flag: bool
    ) -> Optional[type]:
        """
        Determina o tipo de QGraphicsItem apropriado para exibir o objeto.

        Args:
            display_data_object: Objeto de dados a ser exibido

        Returns:
            Classe QGraphicsItem apropriada para o tipo de objeto
        """
        if is_projected_3d_flag:
            if isinstance(display_data_object, Point):
                return QGraphicsEllipseItem
            elif isinstance(display_data_object, GeometricShape3D):
                return QGraphicsPathItem
            return None
        if isinstance(display_data_object, Point):
            return QGraphicsEllipseItem
        if isinstance(display_data_object, Line):
            return QGraphicsLineItem
        if isinstance(display_data_object, Polygon):
            return (
                QGraphicsPathItem
                if display_data_object.is_open
                else QGraphicsPolygonItem
            )
        if isinstance(display_data_object, BezierCurve):
            return QGraphicsPathItem
        if isinstance(display_data_object, BSplineCurve):
            return QGraphicsPathItem
        return None

    def add_object(
        self, original_data_object: AnyDataObject, mark_modified: bool = True
    ) -> Optional[QGraphicsItem]:
        """
        Adiciona um novo objeto à cena.

        Args:
            original_data_object: Objeto a ser adicionado
            mark_modified: Se True, marca a cena como modificada

        Returns:
            Item gráfico criado ou None se a operação falhar
        """
        if not isinstance(original_data_object, DATA_OBJECT_TYPES_ALL):
            QMessageBox.warning(
                None,
                "Erro Interno",
                f"Tentativa de adicionar objeto de tipo não suportado: {type(original_data_object)}",
            )
            return None
        item_id = id(original_data_object)
        if item_id in self._id_to_item_map:
            return self._id_to_item_map[item_id]
        is_3d_original = isinstance(original_data_object, DATA_OBJECT_TYPES_3D)
        display_data_for_item_creation, display_type_changed_flag = (
            self._clip_or_project_data_object(original_data_object)
        )
        if display_data_for_item_creation:
            try:
                graphics_item: Optional[QGraphicsItem] = None
                if is_3d_original:
                    if isinstance(display_data_for_item_creation, Point):
                        graphics_item = (
                            display_data_for_item_creation.create_graphics_item()
                        )
                    elif isinstance(original_data_object, GeometricShape3D):
                        projected_lines = (
                            self._get_projected_lines_for_GeometricShape3D(
                                original_data_object
                            )
                        )
                        if projected_lines:
                            graphics_item = original_data_object.create_graphics_item(
                                projected_lines
                            )
                else:
                    graphics_item = (
                        display_data_for_item_creation.create_graphics_item()
                    )
                if graphics_item:
                    graphics_item.setData(SC_ORIGINAL_OBJECT_KEY, original_data_object)
                    graphics_item.setData(
                        SC_CURRENT_REPRESENTATION_KEY, display_data_for_item_creation
                    )
                    graphics_item.setData(SC_IS_PROJECTED_3D_KEY, is_3d_original)
                    is_poly_from_2d_curve = isinstance(
                        original_data_object, (BezierCurve, BSplineCurve)
                    ) and isinstance(display_data_for_item_creation, Polygon)
                    graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, is_poly_from_2d_curve
                    )
                    self._scene.addItem(graphics_item)
                    self._id_to_item_map[item_id] = graphics_item
                    if mark_modified:
                        self.scene_modified.emit(True)
                    return graphics_item
            except Exception as e:
                QMessageBox.critical(
                    None,
                    "Erro ao Adicionar Item",
                    f"Falha ao criar item gráfico para {type(original_data_object).__name__}: {e}\n"
                    f"Objeto de display: {type(display_data_for_item_creation)}",
                )
        if mark_modified:
            self.scene_modified.emit(True)
        return None

    def _get_projected_lines_for_GeometricShape3D(
        self, GeometricShape3D: GeometricShape3D
    ) -> List[QLineF]:
        projected_lines: List[QLineF] = []
        vrp = self._state_manager.camera_vrp()
        target = self._state_manager.camera_target()
        vup = self._state_manager.camera_vup()
        view_m = tf3d.create_view_matrix(vrp, target, vup)
        proj_m: np.ndarray
        if self._state_manager.projection_mode() == ProjectionMode.ORTHOGRAPHIC:
            s = self._state_manager.ortho_box_size() / 2.0
            aspect = self._state_manager.aspect_ratio()
            near, far = (
                self._state_manager.near_plane(),
                self._state_manager.far_plane(),
            )
            proj_m = tf3d.create_orthographic_projection_matrix(
                -s * aspect, s * aspect, -s, s, near, far
            )
        else:
            fov_y = self._state_manager.fov_degrees()
            aspect = self._state_manager.aspect_ratio()
            near, far = (
                self._state_manager.near_plane(),
                self._state_manager.far_plane(),
            )
            proj_m = tf3d.create_perspective_projection_matrix(fov_y, aspect, near, far)

        scene_r = self._state_manager.clip_rect()
        # Passa os quatro parâmetros para viewport_transform_matrix
        viewport_rect_params = (
            scene_r.x(),
            scene_r.y(),
            scene_r.width(),
            scene_r.height(),
        )
        model_m = tf3d.create_identity_matrix_3d()

        for p1_3d, p2_3d in GeometricShape3D.segments:
            q_p1 = tf3d.project_point_3d_to_qpointf(
                p1_3d.get_coords(), model_m, view_m, proj_m, viewport_rect_params
            )
            q_p2 = tf3d.project_point_3d_to_qpointf(
                p2_3d.get_coords(), model_m, view_m, proj_m, viewport_rect_params
            )
            if q_p1 and q_p2:
                line_2d_coords = ((q_p1.x(), q_p1.y()), (q_p2.x(), q_p2.y()))
                clipped_2d_seg = self._line_clipper_func_2d(
                    line_2d_coords[0], line_2d_coords[1], self._clip_rect_tuple_2d
                )
                if clipped_2d_seg:
                    projected_lines.append(
                        QLineF(QPointF(*clipped_2d_seg[0]), QPointF(*clipped_2d_seg[1]))
                    )
        return projected_lines

    def remove_data_objects(
        self, data_objects_to_remove: List[AnyDataObject], mark_modified: bool = True
    ) -> int:
        """
        Remove uma lista de objetos da cena.

        Args:
            data_objects_to_remove: Lista de objetos a serem removidos
            mark_modified: Se True, marca a cena como modificada

        Returns:
            Número de objetos removidos com sucesso
        """
        removed_count = 0
        for data_obj in data_objects_to_remove:
            item_id = id(data_obj)
            graphics_item = self._id_to_item_map.pop(item_id, None)
            if graphics_item and graphics_item.scene():
                self._scene.removeItem(graphics_item)
                removed_count += 1
        if removed_count > 0 and mark_modified:
            self.scene_modified.emit(True)
        return removed_count

    def clear_scene(self, mark_modified: bool = True):
        """
        Remove todos os objetos da cena.

        Args:
            mark_modified: Se True, marca a cena como modificada
        """
        items_to_remove = list(self._id_to_item_map.values())
        for item in items_to_remove:
            if item and item.scene():
                self._scene.removeItem(item)
        cleared_count = len(self._id_to_item_map)
        self._id_to_item_map.clear()
        if mark_modified:
            self.scene_modified.emit(cleared_count > 0)

    def update_object_item(
        self, original_modified_data_object: AnyDataObject, mark_modified: bool = True
    ):
        """
        Atualiza a representação visual de um objeto na cena.

        Args:
            original_modified_data_object: Objeto modificado a ser atualizado
            mark_modified: Se True, marca a cena como modificada
        """
        if not isinstance(original_modified_data_object, DATA_OBJECT_TYPES_ALL):
            return
        item_id = id(original_modified_data_object)
        current_graphics_item = self._id_to_item_map.get(item_id)
        is_3d_original = isinstance(original_modified_data_object, DATA_OBJECT_TYPES_3D)
        new_display_representation, display_type_changed = (
            self._clip_or_project_data_object(original_modified_data_object)
        )

        if not current_graphics_item or not current_graphics_item.scene():
            if new_display_representation:
                self.add_object(original_modified_data_object, mark_modified)
            elif mark_modified:
                self.scene_modified.emit(True)
            return
        try:
            if new_display_representation is None:
                if current_graphics_item.scene():
                    self._scene.removeItem(current_graphics_item)
                if item_id in self._id_to_item_map:
                    del self._id_to_item_map[item_id]
                if mark_modified:
                    self.scene_modified.emit(True)
            else:
                required_qitem_type = self._get_required_qgraphicsitem_type(
                    new_display_representation, is_3d_original
                )
                needs_replacement = not isinstance(
                    current_graphics_item,
                    required_qitem_type if required_qitem_type else type(None),
                )
                current_repr_obj = current_graphics_item.data(
                    SC_CURRENT_REPRESENTATION_KEY
                )
                if type(current_repr_obj) != type(new_display_representation):
                    needs_replacement = True
                if display_type_changed:
                    needs_replacement = True
                if needs_replacement:
                    if current_graphics_item.scene():
                        self._scene.removeItem(current_graphics_item)
                    new_graphics_item: Optional[QGraphicsItem] = None
                    if is_3d_original:
                        if isinstance(new_display_representation, Point):
                            new_graphics_item = (
                                new_display_representation.create_graphics_item()
                            )
                        elif isinstance(
                            original_modified_data_object, GeometricShape3D
                        ):
                            projected_lines = (
                                self._get_projected_lines_for_GeometricShape3D(
                                    original_modified_data_object
                                )
                            )
                            if projected_lines:
                                new_graphics_item = (
                                    original_modified_data_object.create_graphics_item(
                                        projected_lines
                                    )
                                )
                    else:
                        new_graphics_item = (
                            new_display_representation.create_graphics_item()
                        )
                    if new_graphics_item:
                        new_graphics_item.setData(
                            SC_ORIGINAL_OBJECT_KEY, original_modified_data_object
                        )
                        new_graphics_item.setData(
                            SC_CURRENT_REPRESENTATION_KEY, new_display_representation
                        )
                        new_graphics_item.setData(
                            SC_IS_PROJECTED_3D_KEY, is_3d_original
                        )
                        is_poly_from_curve_upd = isinstance(
                            original_modified_data_object, (BezierCurve, BSplineCurve)
                        ) and isinstance(new_display_representation, Polygon)
                        new_graphics_item.setData(
                            SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, is_poly_from_curve_upd
                        )
                        self._scene.addItem(new_graphics_item)
                        self._id_to_item_map[item_id] = new_graphics_item
                    else:
                        if item_id in self._id_to_item_map:
                            del self._id_to_item_map[item_id]
                else:
                    current_graphics_item.prepareGeometryChange()
                    current_graphics_item.setData(
                        SC_CURRENT_REPRESENTATION_KEY, new_display_representation
                    )
                    current_graphics_item.setData(
                        SC_IS_PROJECTED_3D_KEY, is_3d_original
                    )
                    is_poly_from_curve_upd2 = isinstance(
                        original_modified_data_object, (BezierCurve, BSplineCurve)
                    ) and isinstance(new_display_representation, Polygon)
                    current_graphics_item.setData(
                        SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY, is_poly_from_curve_upd2
                    )
                    obj_for_3d_geom_update = (
                        original_modified_data_object
                        if is_3d_original
                        and isinstance(original_modified_data_object, GeometricShape3D)
                        else None
                    )
                    self._update_graphics_item_geometry(
                        current_graphics_item,
                        new_display_representation,
                        is_3d_original,
                        obj_for_3d_geom_update,
                    )
                    self._apply_style_to_item(
                        current_graphics_item,
                        new_display_representation,
                        is_3d_original,
                    )
                    current_graphics_item.update()
                if mark_modified:
                    self.scene_modified.emit(True)
        except Exception as e:
            QMessageBox.critical(
                None,
                "Erro ao Atualizar Item",
                f"Falha ao atualizar item {type(original_modified_data_object).__name__}: {e}",
            )

    def _update_graphics_item_geometry(
        self,
        item: QGraphicsItem,
        display_data_obj: AnyDataObject,
        is_projected_3d_flag: bool,
        original_3d_obj_for_path: Optional[GeometricShape3D] = None,
    ):
        """
        Atualiza a geometria de um item gráfico baseado nos dados de exibição.

        Args:
            item: Item gráfico a ser atualizado
            display_data: Dados que definem a nova geometria
        """
        try:
            if is_projected_3d_flag:
                if isinstance(display_data_obj, Point) and isinstance(
                    item, QGraphicsEllipseItem
                ):
                    size, offset = Point.GRAPHICS_SIZE, Point.GRAPHICS_SIZE / 2.0
                    item.setRect(
                        QRectF(
                            display_data_obj.x - offset,
                            display_data_obj.y - offset,
                            size,
                            size,
                        )
                    )
                elif isinstance(
                    original_3d_obj_for_path, GeometricShape3D
                ) and isinstance(item, QGraphicsPathItem):
                    projected_lines = self._get_projected_lines_for_GeometricShape3D(
                        original_3d_obj_for_path
                    )
                    new_path = QPainterPath()
                    if projected_lines:
                        for line_f in projected_lines:
                            new_path.moveTo(line_f.p1())
                            new_path.lineTo(line_f.p2())
                    item.setPath(new_path)
            else:
                if isinstance(display_data_obj, Point) and isinstance(
                    item, QGraphicsEllipseItem
                ):
                    size, offset = Point.GRAPHICS_SIZE, Point.GRAPHICS_SIZE / 2.0
                    item.setRect(
                        QRectF(
                            display_data_obj.x - offset,
                            display_data_obj.y - offset,
                            size,
                            size,
                        )
                    )
                elif isinstance(display_data_obj, Line) and isinstance(
                    item, QGraphicsLineItem
                ):
                    item.setLine(
                        QLineF(
                            display_data_obj.start.to_qpointf(),
                            display_data_obj.end.to_qpointf(),
                        )
                    )
                elif isinstance(display_data_obj, Polygon):
                    is_poly_from_curve = (
                        item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY) is True
                    )
                    if display_data_obj.is_open or is_poly_from_curve:
                        if isinstance(item, QGraphicsPathItem):
                            new_path = QPainterPath()
                            if display_data_obj.points:
                                new_path.moveTo(display_data_obj.points[0].to_qpointf())
                                for p_model in display_data_obj.points[1:]:
                                    new_path.lineTo(p_model.to_qpointf())
                            item.setPath(new_path)
                    else:
                        if isinstance(item, QGraphicsPolygonItem):
                            item.setPolygon(
                                QPolygonF(
                                    [p.to_qpointf() for p in display_data_obj.points]
                                )
                            )
                elif isinstance(
                    display_data_obj, (BezierCurve, BSplineCurve)
                ) and isinstance(item, QGraphicsPathItem):
                    temp_item_for_path_creation = (
                        display_data_obj.create_graphics_item()
                    )
                    if isinstance(temp_item_for_path_creation, QGraphicsPathItem):
                        item.setPath(temp_item_for_path_creation.path())
        except Exception as e:
            print(
                f"ERRO em _update_graphics_item_geometry para {type(display_data_obj)}/{type(item)}: {e}"
            )

    def _apply_style_to_item(
        self,
        item: QGraphicsItem,
        display_data_obj_being_shown: AnyDataObject,
        is_projected_3d_flag: bool,
    ):
        """
        Aplica o estilo visual a um item gráfico.

        Args:
            item: Item gráfico a ser estilizado
            display_data: Dados que definem o estilo
        """
        original_data_object = item.data(SC_ORIGINAL_OBJECT_KEY)
        if not hasattr(original_data_object, "color"):
            return
        color = (
            original_data_object.color
            if original_data_object.color.isValid()
            else QColor(Qt.black)
        )
        pen = QPen(Qt.NoPen)
        brush = QBrush(Qt.NoBrush)
        if is_projected_3d_flag:
            if isinstance(original_data_object, Point3D):
                pen = QPen(color, 1)
                brush = QBrush(color)
            elif isinstance(original_data_object, GeometricShape3D):
                pen = QPen(color, GeometricShape3D.GRAPHICS_LINE_WIDTH, Qt.SolidLine)
                pen.setJoinStyle(Qt.RoundJoin)
                pen.setCapStyle(Qt.RoundCap)
        else:
            if isinstance(display_data_obj_being_shown, Point):
                pen = QPen(color, 1)
                brush = QBrush(color)
            elif isinstance(display_data_obj_being_shown, Line):
                pen = QPen(color, Line.GRAPHICS_WIDTH, Qt.SolidLine)
            elif isinstance(display_data_obj_being_shown, Polygon):
                is_poly_representing_clipped_curve = (
                    item.data(SC_IS_CLIPPED_BEZIER_AS_POLYGON_KEY) is True
                )
                pen = QPen(color, Polygon.GRAPHICS_BORDER_WIDTH)
                pen.setStyle(Qt.SolidLine)
                if (
                    not display_data_obj_being_shown.is_open
                    and not is_poly_representing_clipped_curve
                    and display_data_obj_being_shown.is_filled
                ):
                    brush.setStyle(Qt.SolidPattern)
                    fill_color = QColor(color)
                    fill_color.setAlphaF(Polygon.GRAPHICS_FILL_ALPHA)
                    brush.setColor(fill_color)
            elif isinstance(display_data_obj_being_shown, BezierCurve):
                pen = QPen(color, BezierCurve.GRAPHICS_WIDTH, Qt.SolidLine)
                pen.setJoinStyle(Qt.RoundJoin)
                pen.setCapStyle(Qt.RoundCap)
            elif isinstance(display_data_obj_being_shown, BSplineCurve):
                pen = QPen(color, BSplineCurve.GRAPHICS_WIDTH, Qt.SolidLine)
                pen.setJoinStyle(Qt.RoundJoin)
                pen.setCapStyle(Qt.RoundCap)
        if hasattr(item, "setPen"):
            item.setPen(pen)
        if hasattr(item, "setBrush"):
            item.setBrush(brush)

    def get_all_original_data_objects(self) -> List[AnyDataObject]:
        return [
            item.data(SC_ORIGINAL_OBJECT_KEY)
            for item in self._id_to_item_map.values()
            if item.data(SC_ORIGINAL_OBJECT_KEY)
            and isinstance(item.data(SC_ORIGINAL_OBJECT_KEY), DATA_OBJECT_TYPES_ALL)
        ]

    def get_selected_data_objects(self) -> List[AnyDataObject]:
        return [
            item.data(SC_ORIGINAL_OBJECT_KEY)
            for item in self._scene.selectedItems()
            if item.data(SC_ORIGINAL_OBJECT_KEY)
            and isinstance(item.data(SC_ORIGINAL_OBJECT_KEY), DATA_OBJECT_TYPES_ALL)
        ]
