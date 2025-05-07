# graphics_editor/services/file_operation_service.py
import os
from typing import List, Optional, Tuple, Dict, Callable, Any

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QWidget, QApplication, QMessageBox
from PyQt5.QtGui import QColor

from ..io_handler import IOHandler
from ..object_manager import ObjectManager, DataObject
from ..state_manager import EditorStateManager
from ..controllers.scene_controller import SceneController
from ..controllers.drawing_controller import DrawingController


class FileOperationService(QObject):
    """
    Handles file operations like loading and saving OBJ files.
    """
    status_message_requested = pyqtSignal(str, int)

    def __init__(self,
                 parent_widget: QWidget,
                 io_handler: IOHandler,
                 object_manager: ObjectManager,
                 state_manager: EditorStateManager,
                 scene_controller: SceneController,
                 drawing_controller: DrawingController,
                 check_unsaved_changes_func: Callable[[str], bool],
                 clear_scene_confirmed_func: Callable[[], None]
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

    # --- Loading Operations ---

    def prompt_load_obj(self) -> Tuple[Optional[str], int, int, List[str]]:
        """
        Prompts the user to select an OBJ file and loads it.
        Returns: (filepath, num_added, num_clipped_out, warnings)
        filepath is None if loading was cancelled or failed early.
        """
        if not self.check_unsaved_changes("carregar um novo arquivo"):
            return None, 0, 0, ["Carregamento cancelado devido a alterações não salvas."]

        obj_filepath = self.io_handler.prompt_load_obj()
        if obj_filepath:
            return self.load_obj_file(obj_filepath, clear_before_load=True)
        return None, 0, 0, ["Nenhum arquivo selecionado para carregar."]

    def load_obj_file(self, obj_filepath: str, clear_before_load: bool = True) -> Tuple[str, int, int, List[str]]:
        """
        Loads and processes an OBJ file.
        Returns: (filepath, num_added, num_clipped_out, warnings)
        """
        self.status_message_requested.emit(f"Carregando {os.path.basename(obj_filepath)}...", 0)
        QApplication.processEvents()

        obj_lines, material_colors, mtl_warnings = self._read_obj_and_mtl_data(obj_filepath)
        if obj_lines is None: # Read failure
            self.status_message_requested.emit("Falha ao ler arquivo(s) OBJ/MTL.", 3000)
            return obj_filepath, 0, 0, mtl_warnings + ["Falha ao ler arquivo(s) OBJ/MTL."]

        parsed_objects, obj_warnings = self.object_manager.parse_obj_data(
            obj_lines, material_colors, self.state_manager.draw_color()
        )
        all_warnings = mtl_warnings + obj_warnings

        if clear_before_load:
            self.clear_scene_confirmed() # Clears scene and map via GraphicsEditor's method

        num_total_parsed = len(parsed_objects)
        for obj in parsed_objects:
            # Add without marking modified yet, GraphicsEditor will handle final state
            self.scene_controller.add_object(obj, mark_modified=False)

        # Count how many actually got added (might have been clipped out or other issues)
        num_added = len(self.scene_controller.get_all_data_objects())
        # This is an approximation, as clear_scene_confirmed might remove pre-existing objects.
        # If clear_before_load is true, num_added is the correct count of objects from this file.
        num_clipped_out_or_failed = num_total_parsed - num_added if clear_before_load else 0


        self.state_manager.set_current_filepath(obj_filepath)
        self.state_manager.mark_as_saved()  # Loaded file is considered saved

        return obj_filepath, num_added, num_clipped_out_or_failed, all_warnings


    def _read_obj_and_mtl_data(
        self, obj_filepath: str
    ) -> Tuple[Optional[List[str]], Dict[str, QColor], List[str]]:
        """Reads OBJ and associated MTL data via IOHandler."""
        all_warnings: List[str] = []
        material_colors: Dict[str, QColor] = {}
        read_result = self.io_handler.read_obj_lines(obj_filepath)

        if read_result is None: # IOHandler already showed critical error
            return None, {}, ["Falha ao ler arquivo OBJ."]
        
        obj_lines, mtl_filename_relative = read_result
        if mtl_filename_relative:
            obj_dir = os.path.dirname(obj_filepath)
            mtl_filepath_full = os.path.normpath(os.path.join(obj_dir, mtl_filename_relative))
            if os.path.exists(mtl_filepath_full):
                material_colors, mtl_read_warnings = self.io_handler.read_mtl_file(mtl_filepath_full)
                all_warnings.extend(mtl_read_warnings)
            else:
                all_warnings.append(f"Arquivo MTL '{mtl_filename_relative}' referenciado não encontrado.")
        return obj_lines, material_colors, all_warnings

    # --- Saving Operations ---

    def prompt_save_as_obj(self) -> bool:
        """Prompts for a new file path and saves the scene. Returns True on success."""
        self.drawing_controller.cancel_current_drawing()
        current_path = self.state_manager.current_filepath()
        default_name = os.path.basename(current_path) if current_path else "nova_cena.obj"
        
        base_filepath = self.io_handler.prompt_save_obj(default_name)
        if not base_filepath:
            self.status_message_requested.emit("Salvar cancelado.", 2000)
            return False

        success, warnings, has_mtl = self._save_to_file(base_filepath)
        
        # GraphicsEditor will call _report_save_results with this
        if success:
            self.state_manager.set_current_filepath(base_filepath + ".obj")
            self.state_manager.mark_as_saved()
            # Report result via editor
            self.parent_widget._report_save_results(base_filepath, True, warnings, has_mtl)
            return True
        else:
            self.status_message_requested.emit("Falha ao salvar.", 3000)
            self.parent_widget._report_save_results(base_filepath, False, warnings, has_mtl)
            return False

    def save_current_file(self) -> bool:
        """Saves to the current file path, or prompts if no path exists. Returns True on success."""
        current_path = self.state_manager.current_filepath()
        if not current_path:
            return self.prompt_save_as_obj()
        else:
            self.drawing_controller.cancel_current_drawing()
            base_filepath, _ = os.path.splitext(current_path)
            success, warnings, has_mtl = self._save_to_file(base_filepath)
            if success:
                self.state_manager.mark_as_saved()
            self.parent_widget._report_save_results(base_filepath, success, warnings, has_mtl)
            return success

    def _save_to_file(self, base_filepath: str) -> Tuple[bool, List[str], bool]:
        """
        Saves the current scene to the given base filepath.
        Returns: (success, warnings, has_mtl_been_written)
        """
        self.status_message_requested.emit(f"Salvando em {os.path.basename(base_filepath)}...", 0)
        QApplication.processEvents()

        scene_data_objects = self.scene_controller.get_all_data_objects()
        if not scene_data_objects:
            self.status_message_requested.emit("Nada para salvar (cena vazia).", 2000)
            obj_ok = self.io_handler.write_obj_and_mtl(base_filepath, ["# Cena Vazia"], None)
            return obj_ok, ["Cena vazia, arquivo OBJ salvo vazio."], False # Success, warning, no mtl

        mtl_filename_for_obj_ref = os.path.basename(base_filepath) + ".mtl"
        obj_lines, mtl_lines, gen_warnings = self.object_manager.generate_obj_data(
            scene_data_objects, mtl_filename_for_obj_ref
        )

        if obj_lines is None: # Generation error
            return False, gen_warnings + ["Falha ao gerar dados OBJ/MTL."], False

        write_success = self.io_handler.write_obj_and_mtl(base_filepath, obj_lines, mtl_lines)
        has_mtl = mtl_lines is not None and len(mtl_lines) > 0
        
        return write_success, gen_warnings, has_mtl
