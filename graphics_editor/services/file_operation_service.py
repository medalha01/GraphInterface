# graphics_editor/services/file_operation_service.py
import os
from typing import List, Optional, Tuple, Dict, Callable, Any

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.QtGui import QColor

from ..io_handler import IOHandler
from ..object_manager import (
    ObjectManager,
    DataObject as DataObject2D,
)  # Alias para clareza
from ..state_manager import EditorStateManager
from ..controllers.scene_controller import SceneController
from ..controllers.drawing_controller import (
    DrawingController,
)  # Para cancelar desenho 2D


class FileOperationService(QObject):
    """
    Serviço responsável por gerenciar operações de arquivo do editor gráfico,
    com foco em arquivos OBJ/MTL para objetos 2D.

    Responsabilidades:
    - Carregar arquivos OBJ/MTL (para dados 2D).
    - Salvar a cena atual (objetos 2D) em arquivos OBJ/MTL.
    - Gerenciar o estado de salvamento da cena.
    - Tratar avisos e erros durante operações de arquivo.
    """

    status_message_requested = pyqtSignal(str, int)  # (mensagem, timeout_ms)

    def __init__(
        self,
        parent_widget: QWidget,
        io_handler: IOHandler,
        object_manager: ObjectManager,  # Gerenciador de objetos 2D
        state_manager: EditorStateManager,
        scene_controller: SceneController,
        drawing_controller: DrawingController,  # Para cancelar desenho 2D
        check_unsaved_changes_func: Callable[[str], bool],
        clear_scene_confirmed_func: Callable[[], None],
    ):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        self.io_handler = io_handler
        self.object_manager = object_manager
        self.state_manager = state_manager
        self.scene_controller = scene_controller
        self.drawing_controller = drawing_controller
        self.check_unsaved_changes = check_unsaved_changes_func
        self.clear_scene_confirmed = clear_scene_confirmed_func

    def prompt_load_obj(self) -> Tuple[Optional[str], int, int, List[str]]:
        """
        Solicita ao usuário selecionar um arquivo OBJ para carregar (objetos 2D).

        Returns:
            Tuple[Optional[str], int, int, List[str]]: (caminho_arquivo, num_adicionados, num_clipados, avisos)
        """
        self.drawing_controller.cancel_current_drawing()  # Cancela desenho 2D ativo
        if not self.check_unsaved_changes("carregar um novo arquivo"):
            return (
                None,
                0,
                0,
                ["Carregamento cancelado devido a alterações não salvas."],
            )

        obj_filepath = self.io_handler.prompt_load_obj()  # Diálogo focado em OBJ 2D
        if obj_filepath:
            return self.load_obj_file(obj_filepath, clear_before_load=True)
        return None, 0, 0, ["Nenhum arquivo selecionado para carregar."]

    def load_obj_file(
        self, obj_filepath: str, clear_before_load: bool = True
    ) -> Tuple[str, int, int, List[str]]:
        """
        Carrega um arquivo OBJ (2D) e seus materiais associados.

        Args:
            obj_filepath: Caminho do arquivo OBJ.
            clear_before_load: Se True, limpa a cena (2D e 3D) antes de carregar.

        Returns:
            Tuple[str, int, int, List[str]]: (caminho_arquivo, num_adicionados, num_clipados, avisos)
        """
        self.status_message_requested.emit(
            f"Carregando {os.path.basename(obj_filepath)}...", 0
        )
        QApplication.processEvents()  # Processa eventos para atualizar UI

        obj_lines, material_colors, mtl_warnings = self._read_obj_and_mtl_data(
            obj_filepath
        )
        if obj_lines is None:  # Erro crítico na leitura do OBJ
            self.status_message_requested.emit("Falha ao ler arquivo(s) OBJ/MTL.", 3000)
            return (
                obj_filepath,
                0,
                0,
                mtl_warnings + ["Falha ao ler arquivo(s) OBJ/MTL."],
            )

        # ObjectManager analisa e cria objetos 2D
        parsed_2d_objects, obj_parse_warnings = self.object_manager.parse_obj_data(
            obj_lines, material_colors, self.state_manager.draw_color()
        )
        all_warnings = mtl_warnings + obj_parse_warnings

        if clear_before_load:
            self.clear_scene_confirmed()  # Limpa todos os objetos da cena (2D e 3D)

        num_total_parsed = len(parsed_2d_objects)
        num_successfully_added = 0

        for obj_2d in parsed_2d_objects:
            # Adiciona à cena; SceneController trata clipping visual
            graphics_item = self.scene_controller.add_object(
                obj_2d, mark_modified=False
            )
            if graphics_item:
                num_successfully_added += 1

        num_clipped_or_failed = num_total_parsed - num_successfully_added

        if num_successfully_added > 0:
            self.state_manager.mark_as_modified()  # Cena alterada

        self.state_manager.set_current_filepath(
            obj_filepath
        )  # Define como arquivo atual
        self.state_manager.mark_as_saved()  # Considera arquivo carregado como "salvo" inicialmente

        return (
            obj_filepath,
            num_successfully_added,
            num_clipped_or_failed,
            all_warnings,
        )

    def _read_obj_and_mtl_data(
        self, obj_filepath: str
    ) -> Tuple[Optional[List[str]], Dict[str, QColor], List[str]]:
        """Lê dados do arquivo OBJ e seu MTL associado (para 2D)."""
        all_warnings: List[str] = []
        material_colors: Dict[str, QColor] = {}
        read_result = self.io_handler.read_obj_lines(obj_filepath)

        if read_result is None:
            return None, {}, ["Falha ao ler arquivo OBJ."]

        obj_lines, mtl_filename_relative = read_result
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            mtl_filepath_full = os.path.normpath(
                os.path.join(obj_dir, mtl_filename_relative)
            )
            if os.path.exists(mtl_filepath_full):
                material_colors, mtl_read_warnings = self.io_handler.read_mtl_file(
                    mtl_filepath_full
                )
                all_warnings.extend(mtl_read_warnings)
            else:
                all_warnings.append(
                    f"Arquivo MTL '{mtl_filename_relative}' referenciado não encontrado."
                )
        return obj_lines, material_colors, all_warnings

    def prompt_save_as_obj(self) -> bool:
        """Solicita local para salvar a cena como OBJ (objetos 2D)."""
        self.drawing_controller.cancel_current_drawing()
        current_path = self.state_manager.current_filepath()
        default_name = (
            os.path.basename(current_path) if current_path else "nova_cena_2d.obj"
        )

        base_filepath = self.io_handler.prompt_save_obj(
            default_name
        )  # Diálogo focado em 2D
        if not base_filepath:
            self.status_message_requested.emit("Salvar (2D) cancelado.", 2000)
            return False

        success, warnings, has_mtl = self._save_to_file(base_filepath)
        if success:
            self.state_manager.set_current_filepath(base_filepath + ".obj")
            self.state_manager.mark_as_saved()
            if hasattr(self.parent_widget, "_report_save_results"):
                self.parent_widget._report_save_results(
                    base_filepath, True, warnings, has_mtl
                )
            return True
        else:
            self.status_message_requested.emit("Falha ao salvar (2D).", 3000)
            if hasattr(self.parent_widget, "_report_save_results"):
                self.parent_widget._report_save_results(
                    base_filepath, False, warnings, has_mtl, is_generation_error=True
                )
            return False

    def save_current_file(self) -> bool:
        """Salva a cena atual no arquivo OBJ atual (objetos 2D)."""
        current_path = self.state_manager.current_filepath()
        if not current_path:  # Se não há caminho, age como "Salvar Como"
            return self.prompt_save_as_obj()
        else:
            self.drawing_controller.cancel_current_drawing()
            base_filepath, _ = os.path.splitext(current_path)  # Remove extensão .obj
            success, warnings, has_mtl = self._save_to_file(base_filepath)
            if success:
                self.state_manager.mark_as_saved()
            if hasattr(self.parent_widget, "_report_save_results"):
                self.parent_widget._report_save_results(
                    base_filepath, success, warnings, has_mtl
                )
            return success

    def _save_to_file(self, base_filepath: str) -> Tuple[bool, List[str], bool]:
        """
        Salva a cena atual (objetos 2D) em arquivos OBJ e MTL.

        Args:
            base_filepath: Caminho base para os arquivos (sem extensão).

        Returns:
            Tuple[bool, List[str], bool]: (sucesso, avisos, mtl_gerado)
        """
        self.status_message_requested.emit(
            f"Salvando 2D em {os.path.basename(base_filepath)}...", 0
        )
        QApplication.processEvents()

        # Pega apenas objetos 2D para salvar
        scene_2d_data_objects = [
            obj
            for obj in self.scene_controller.get_all_original_data_objects()
            if isinstance(obj, DataObject2D)  # Garante que é um tipo de objeto 2D
        ]

        if not scene_2d_data_objects:
            self.status_message_requested.emit(
                "Nada para salvar (cena 2D vazia).", 2000
            )
            # Cria um arquivo OBJ vazio válido
            empty_obj_lines = ["# Arquivo OBJ (Editor Gráfico 2D)", "# Cena Vazia"]
            obj_ok = self.io_handler.write_obj_and_mtl(
                base_filepath, empty_obj_lines, None
            )
            return obj_ok, ["Cena 2D vazia, arquivo OBJ salvo vazio."], False

        mtl_filename_for_obj_ref = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, gen_warnings = self.object_manager.generate_obj_data(
            scene_2d_data_objects, mtl_filename_for_obj_ref
        )

        if obj_lines is None:  # Erro crítico na geração dos dados
            return False, gen_warnings + ["Falha ao gerar dados OBJ/MTL."], False

        write_success = self.io_handler.write_obj_and_mtl(
            base_filepath, obj_lines, mtl_lines
        )
        has_mtl = (
            mtl_lines is not None and len(mtl_lines) > 3
        )  # Verifica se MTL tem mais que cabeçalhos

        return write_success, gen_warnings, has_mtl
