# io_handler.py
import os
from typing import List, Optional, Dict, Tuple

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt


class IOHandler:
    """Handles file dialogs and basic file reading/writing operations for OBJ and MTL."""

    def __init__(self, parent_widget: QWidget):
        """
        Initializes the IOHandler.
        Args:
            parent_widget: The parent widget (usually the main window) for dialogs.
        """
        self._parent = parent_widget
        self._last_dir: Optional[str] = None

    def prompt_load_obj(self) -> Optional[str]:
        """
        Opens a file dialog to select an OBJ file for loading.
        Returns:
            The selected file path, or None if cancelled.
        """
        filepath, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Carregar Arquivo OBJ",
            self._last_dir or "",
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath)
            return filepath

    def prompt_save_obj(self, default_filename: str = "untitled.obj") -> Optional[str]:
        """
        Opens a file dialog to select a base file path for saving OBJ and MTL files.
        The .obj extension will be ensured.
        Args:
            default_filename: The suggested filename in the dialog.
        Returns:
            The selected base file path (without extension guaranteed), or None if cancelled.
        """
        filepath, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Salvar Como Arquivo OBJ",
            os.path.join(self._last_dir or "", default_filename),
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath)
            base_path, _ = os.path.splitext(filepath)
            return base_path
        return None

    def read_obj_lines(
        self, filepath: str
    ) -> Optional[Tuple[List[str], Optional[str]]]:
        """
        Reads lines from an OBJ file, finds the mtllib reference.
        Args:
            filepath: The path to the OBJ file.
        Returns:
            A tuple containing:
              - List of relevant OBJ lines (stripped, non-empty, non-comment).
              - The filename specified in the mtllib line (if found), otherwise None.
            Returns None if the file cannot be read.
        """
        obj_lines: List[str] = []
        mtl_filename: Optional[str] = None
        try:
            with open(filepath, "r") as f:
                for line in f:
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith("#"):
                        continue
                    obj_lines.append(stripped_line)
                    parts = stripped_line.split()
                    if len(parts) > 1 and parts[0].lower() == "mtllib":
                        if mtl_filename is None:
                            mtl_filename = parts[1]
            return obj_lines, mtl_filename
        except FileNotFoundError:
            QMessageBox.critical(
                self._parent, "Erro", f"Arquivo OBJ não encontrado: {filepath}"
            )
            return None
        except Exception as e:
            QMessageBox.critical(
                self._parent,
                "Erro de Leitura OBJ",
                f"Não foi possível ler o arquivo {filepath}:\n{e}",
            )
            return None

    def read_mtl_file(self, filepath: str) -> Tuple[Dict[str, QColor], List[str]]:
        """
        Parses a Material Template Library (.mtl) file.
        Args:
            filepath: The path to the MTL file.
        Returns:
            A tuple containing:
             - A dictionary mapping material names to QColor objects.
             - A list of warning messages.
        """
        material_colors: Dict[str, QColor] = {}
        warnings: List[str] = []
        current_mtl_name: Optional[str] = None

        try:
            with open(filepath, "r") as f:
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith("#"):
                        continue

                    parts = stripped_line.split()
                    command = parts[0].lower()

                    if command == "newmtl":
                        if len(parts) > 1:
                            current_mtl_name = parts[1]
                            # Use the imported Qt now
                            material_colors[current_mtl_name] = QColor(
                                Qt.gray
                            )  # Default if no Kd
                        else:
                            warnings.append(
                                f"MTL Linha {line_num}: 'newmtl' sem nome de material."
                            )
                            current_mtl_name = None
                    elif command == "kd":  # Diffuse color
                        if current_mtl_name:
                            try:
                                r = float(parts[1])
                                g = float(parts[2])
                                b = float(parts[3])
                                q_r = int(max(0.0, min(1.0, r)) * 255)
                                q_g = int(max(0.0, min(1.0, g)) * 255)
                                q_b = int(max(0.0, min(1.0, b)) * 255)
                                material_colors[current_mtl_name] = QColor(
                                    q_r, q_g, q_b
                                )
                            except (IndexError, ValueError):
                                warnings.append(
                                    f"MTL Linha {line_num}: Ignorando cor 'Kd' malformada para material '{current_mtl_name}'."
                                )
                        else:
                            warnings.append(
                                f"MTL Linha {line_num}: Ignorando 'Kd' - nenhum material ativo."
                            )

        except FileNotFoundError:
            warnings.append(f"Arquivo MTL não encontrado: {filepath}")
        except Exception as e:
            warnings.append(f"Erro ao ler o arquivo MTL {filepath}: {e}")

        return material_colors, warnings

    def write_obj_and_mtl(
        self, base_filepath: str, obj_lines: List[str], mtl_lines: List[str]
    ) -> bool:
        """
        Writes the OBJ and MTL lines to corresponding files.
        Args:
            base_filepath: The base path for the files (e.g., 'mydir/myfile').
                           '.obj' and '.mtl' will be appended.
            obj_lines: Lines for the .obj file.
            mtl_lines: Lines for the .mtl file.
        Returns:
            True if both files were written successfully, False otherwise.
        """
        obj_filepath = base_filepath + ".obj"
        mtl_filepath = base_filepath + ".mtl"
        obj_success = False
        mtl_success = False

        try:
            with open(obj_filepath, "w") as f:
                for line in obj_lines:
                    f.write(line + "\n")
            obj_success = True
        except IOError as e:
            QMessageBox.critical(
                self._parent,
                "Erro de Escrita OBJ",
                f"Não foi possível escrever no arquivo {obj_filepath}:\n{e}",
            )
        except Exception as e:
            QMessageBox.critical(
                self._parent,
                "Erro Inesperado OBJ",
                f"Ocorreu um erro inesperado ao salvar em {obj_filepath}:\n{e}",
            )

        if not obj_success:
            return False

        if mtl_lines:
            try:
                with open(mtl_filepath, "w") as f:
                    for line in mtl_lines:
                        f.write(line + "\n")
                mtl_success = True
            except IOError as e:
                QMessageBox.critical(
                    self._parent,
                    "Erro de Escrita MTL",
                    f"Não foi possível escrever no arquivo {mtl_filepath}:\n{e}",
                )
            except Exception as e:
                QMessageBox.critical(
                    self._parent,
                    "Erro Inesperado MTL",
                    f"Ocorreu um erro inesperado ao salvar em {mtl_filepath}:\n{e}",
                )

            if not mtl_success:
                return False
        else:
            mtl_success = True

        return obj_success and mtl_success
