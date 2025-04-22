# graphics_editor/io_handler.py
import os
from typing import List, Optional, Dict, Tuple

from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget
from PyQt5.QtGui import QColor
from PyQt5.QtCore import Qt, QStandardPaths


class IOHandler:
    """
    Gerencia diálogos de arquivo e leitura/escrita de arquivos OBJ e MTL.
    """

    def __init__(self, parent_widget: QWidget):
        """Inicializa com o widget pai para diálogos."""
        self._parent = parent_widget
        # Start in user's documents or home directory
        self._last_dir: str = QStandardPaths.writableLocation(
            QStandardPaths.DocumentsLocation
        ) or os.path.expanduser("~")

    def prompt_load_obj(self) -> Optional[str]:
        """Abre diálogo para selecionar um arquivo OBJ."""
        filepath, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Abrir Arquivo OBJ",
            self._last_dir,
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath)  # Update last directory
            return filepath
        return None

    def prompt_save_obj(
        self, default_filename: str = "sem_titulo.obj"
    ) -> Optional[str]:
        """
        Abre diálogo para selecionar um caminho BASE para salvar OBJ/MTL.
        Retorna o caminho base (sem extensão garantida), ou None se cancelado.
        """
        # Ensure default filename has .obj extension
        if default_filename and not default_filename.lower().endswith(".obj"):
            default_filename += ".obj"

        # Construct full default path for the dialog
        full_default_path = os.path.join(self._last_dir, default_filename)

        filepath, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Salvar Como Arquivo OBJ",
            full_default_path,
            "Wavefront OBJ (*.obj);;Todos os Arquivos (*)",
            # Use native OS dialog options (like overwrite confirmation)
            options=QFileDialog.Options(),
        )
        if filepath:
            self._last_dir = os.path.dirname(filepath)
            # Return the base path chosen by the user (without guaranteed extension)
            # The caller (_save_to_file) will manage extensions (.obj, .mtl)
            base_path, _ = os.path.splitext(filepath)
            if not base_path:  # Handle case where user might type only ".obj"
                QMessageBox.warning(
                    self._parent, "Nome Inválido", "Nome de arquivo inválido."
                )
                return None
            return base_path  # Return path without extension
        return None  # User cancelled

    def read_obj_lines(
        self, filepath: str
    ) -> Optional[Tuple[List[str], Optional[str]]]:
        """
        Lê linhas relevantes de um arquivo OBJ e encontra a referência mtllib.

        Returns:
            Tupla: (linhas_obj, nome_mtl) ou None em caso de erro de leitura/IO.
                   nome_mtl é o nome do arquivo referenciado em 'mtllib', se encontrado.
        """
        obj_lines: List[str] = []
        mtl_filename: Optional[str] = None
        # Try common encodings
        encodings_to_try = ["utf-8", "iso-8859-1", "cp1252", "latin-1"]
        content = None
        detected_encoding = None

        try:
            # Attempt to read with different encodings
            for enc in encodings_to_try:
                try:
                    with open(filepath, "r", encoding=enc) as f:
                        content = f.readlines()
                    detected_encoding = enc  # Success
                    break
                except UnicodeDecodeError:
                    continue  # Try next encoding
                except (
                    Exception
                ) as e_inner:  # Catch other file errors (permissions etc.)
                    raise e_inner

            if content is None:
                raise IOError(
                    f"Não foi possível decodificar usando: {', '.join(encodings_to_try)}."
                )

            # Process successfully read lines
            for line in content:
                stripped_line = line.strip()
                # Skip empty lines and comments
                if not stripped_line or stripped_line.startswith("#"):
                    continue

                obj_lines.append(stripped_line)
                parts = stripped_line.split()
                # Find the first 'mtllib' directive (case-insensitive)
                if (
                    len(parts) > 1
                    and parts[0].lower() == "mtllib"
                    and mtl_filename is None  # Only take the first one found
                ):
                    # Reconstruct filename potentially containing spaces
                    mtl_filename = " ".join(parts[1:])

            return obj_lines, mtl_filename

        except FileNotFoundError:
            QMessageBox.critical(
                self._parent, "Erro", f"Arquivo OBJ não encontrado:\n{filepath}"
            )
            return None
        except IOError as e:
            QMessageBox.critical(
                self._parent,
                "Erro de Leitura OBJ",
                f"Não foi possível ler/decodificar:\n'{os.path.basename(filepath)}'\n{e}",
            )
            return None
        except Exception as e:  # Catch any other unexpected error during processing
            QMessageBox.critical(
                self._parent,
                "Erro Inesperado OBJ",
                f"Erro ao processar '{os.path.basename(filepath)}':\n{e}",
            )
            return None

    def read_mtl_file(self, filepath: str) -> Tuple[Dict[str, QColor], List[str]]:
        """
        Analisa um arquivo MTL, focando em 'newmtl' e 'Kd' (cor difusa).

        Returns:
            Tupla: (dicionario_cores, lista_avisos)
                   dicionario_cores: {material_name: QColor}
                   lista_avisos: List of warnings encountered during parsing.
        """
        material_colors: Dict[str, QColor] = {}
        warnings: List[str] = []
        current_mtl_name: Optional[str] = None
        mtl_basename = os.path.basename(filepath)
        encodings_to_try = ["utf-8", "iso-8859-1", "cp1252", "latin-1"]
        content = None
        detected_encoding = None

        try:
            # Attempt to read with different encodings
            for enc in encodings_to_try:
                try:
                    with open(filepath, "r", encoding=enc) as f:
                        content = f.readlines()
                    detected_encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
                except Exception as e_inner:
                    raise e_inner

            if content is None:
                raise IOError(
                    f"Não foi possível decodificar usando: {', '.join(encodings_to_try)}."
                )

            # Process MTL lines
            for line_num, line in enumerate(content, 1):
                stripped_line = line.strip()
                if not stripped_line or stripped_line.startswith("#"):
                    continue

                parts = stripped_line.split()
                if not parts:
                    continue  # Should be caught by strip, but belts-and-braces
                command = parts[0].lower()

                if command == "newmtl":
                    if len(parts) > 1:
                        # Join remaining parts for names with spaces
                        current_mtl_name = " ".join(parts[1:])
                        # Initialize with default color (gray), might be overwritten by Kd
                        if current_mtl_name not in material_colors:
                            material_colors[current_mtl_name] = QColor(Qt.gray)
                        # Silently overwrite if material is redefined
                        # else: warnings.append(f"MTL Linha {line_num}: Material '{current_mtl_name}' redefinido.")
                    else:
                        warnings.append(f"MTL Linha {line_num}: 'newmtl' sem nome.")
                        current_mtl_name = None  # Reset current material

                # Diffuse Color (Kd R G B) - Primary color used
                elif command == "kd" and current_mtl_name:
                    if len(parts) >= 4:
                        try:
                            # Parse RGB values as floats [0,1]
                            r = max(0.0, min(1.0, float(parts[1])))
                            g = max(0.0, min(1.0, float(parts[2])))
                            b = max(0.0, min(1.0, float(parts[3])))
                            # Convert to QColor (0-255)
                            q_r, q_g, q_b = int(r * 255), int(g * 255), int(b * 255)
                            material_colors[current_mtl_name] = QColor(q_r, q_g, q_b)
                        except ValueError:
                            warnings.append(
                                f"MTL Linha {line_num}: Valores Kd inválidos para '{current_mtl_name}'."
                            )
                    else:
                        warnings.append(
                            f"MTL Linha {line_num}: Kd malformado para '{current_mtl_name}'."
                        )

                # Ignore other MTL commands (Ka, Ks, Ns, d, Tr, illum, map_*, etc.)

        except FileNotFoundError:
            # Don't show popup here, let caller decide based on whether MTL was required
            warnings.append(f"Arquivo MTL '{mtl_basename}' não encontrado.")
        except IOError as e:
            warnings.append(f"Erro de leitura/decodificação MTL '{mtl_basename}': {e}")
        except Exception as e:
            warnings.append(f"Erro inesperado ao ler MTL '{mtl_basename}': {e}")

        return material_colors, warnings

    def write_obj_and_mtl(
        self, base_filepath: str, obj_lines: List[str], mtl_lines: Optional[List[str]]
    ) -> bool:
        """
        Escreve as linhas OBJ e (se houver) MTL nos arquivos correspondentes.
        Overwrites existing files without confirmation (confirmation handled by getSaveFileName).

        Args:
            base_filepath: Caminho base (e.g., 'meudir/arquivo'). Extensions (.obj, .mtl) will be added.
            obj_lines: List of strings for the OBJ file content.
            mtl_lines: List of strings for the MTL file content (or None).

        Returns:
            True se a escrita foi bem sucedida (ou se não havia MTL para salvar), False se ocorreu erro de escrita.
        """
        obj_filepath = base_filepath + ".obj"
        mtl_filepath = base_filepath + ".mtl"
        obj_success = False
        mtl_success = True  # Assume success if no MTL needs saving

        # --- Write OBJ File ---
        try:
            with open(obj_filepath, "w", encoding="utf-8") as f:
                # Join lines with newline and add a final newline
                f.write("\n".join(obj_lines) + "\n")
            obj_success = True
        except IOError as e:
            QMessageBox.critical(
                self._parent,
                "Erro de Escrita OBJ",
                f"Não foi possível escrever:\n'{os.path.basename(obj_filepath)}'\n{e}",
            )
            return False  # Critical failure
        except Exception as e:
            QMessageBox.critical(
                self._parent,
                "Erro Inesperado OBJ",
                f"Erro ao salvar OBJ:\n'{os.path.basename(obj_filepath)}'\n{e}",
            )
            return False

        # --- Write MTL File (if necessary) ---
        if mtl_lines:
            mtl_success = False  # Reset, now needs to succeed
            try:
                with open(mtl_filepath, "w", encoding="utf-8") as f:
                    f.write("\n".join(mtl_lines) + "\n")
                mtl_success = True
            except IOError as e:
                QMessageBox.critical(
                    self._parent,
                    "Erro de Escrita MTL",
                    f"Não foi possível escrever MTL:\n'{os.path.basename(mtl_filepath)}'\n{e}",
                )
                # OBJ might have been saved, but MTL failed. Return False for overall failure.
            except Exception as e:
                QMessageBox.critical(
                    self._parent,
                    "Erro Inesperado MTL",
                    f"Erro ao salvar MTL:\n'{os.path.basename(mtl_filepath)}'\n{e}",
                )
                # Return False as MTL saving failed.

        # Return True only if OBJ saved and (if required) MTL also saved
        return obj_success and mtl_success
