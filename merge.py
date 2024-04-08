from PyQt5.QtWidgets import (QWidget, QApplication, QMainWindow, QVBoxLayout,
    QHBoxLayout, QFrame, QPushButton, QPlainTextEdit, QGroupBox, QRadioButton,
    QSizePolicy, QGridLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QDialog, QProgressBar, QFileDialog, QMessageBox,
    QAbstractItemView)
import os
import json
import copy
from pathlib import Path
from functools import partial
from log import logger

class FileButton(QWidget):
    def __init__(self, button_label, select_prompt,
        format='JSON Files (*.json);;All Files(*)'):
        super().__init__()
        lay = QHBoxLayout(self)

        def button_cb():
            options = QFileDialog.Options()
            file_name, _ = QFileDialog.getOpenFileName(self,
                select_prompt, '', format, options=options)
            if not file_name:
                return
            self.label.setText(f"File: {file_name}")
            self.file = file_name

        button = QPushButton(button_label)
        lay.addWidget(button)
        button.pressed.connect(button_cb)

        self.label = QLabel("File: ")
        lay.addWidget(self.label)

        self.file = None

# tool for merging multiple label indexes
def merge_dialog():
    dialog = QDialog()
    dialog.setWindowTitle('Merge label indexes')
    dialog_lay = QVBoxLayout(dialog)

    orig_button = FileButton("Original index", "Select original index")
    dialog_lay.addWidget(orig_button)

    index_list = QListWidget()
    index_list.setSelectionMode(QAbstractItemView.SingleSelection)
    dialog_lay.addWidget(index_list)

    def add_cb():
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(dialog,
            "Select label index to add", '', 'JSON Files (*.json);;All Files(*)',
            options=options)
        if not file_name:
            return
        index_list.addItem(file_name)

    def del_cb():
        index_list.takeItem(index_list.currentRow())

    def merge_cb():
        orig_file = orig_button.file
        if not os.path.exists(orig_file):
            logger.info(f"No original index exists at {orig_file}")
            return
        with open(orig_file, encoding='utf-8') as f:
            j = json.load(f)
        orig_data = j
        
        new_index = copy.deepcopy(orig_data)
        modified_sigs = {}
        items = [index_list.item(x).text() for x in range(index_list.count())]
        for f in items:
            if not os.path.exists(f):
                logger.info(f"No index exists at {f}")
                return
            with open(f, encoding='utf-8') as f2:
                j = json.load(f2)
            mod_data = j
            for sig in mod_data.keys():
                # TODO have option to allow mismatched key in modified?
                if not sig in orig_data.keys():
                    logger.warn(f"Mismatched key in modified:"
                    f" {sig} in modified, not in original")
                    continue
                if mod_data[sig] == orig_data[sig]:
                    continue
                if sig in modified_sigs:
                    logger.warn(f"Modification collision: {f}"
                        f" and {modified_sigs[sig]} on {sig}")
                modified_sigs[sig] = f
                new_index[sig] = mod_data[sig]

        options = QFileDialog.Options()
        save_file_name, _ = QFileDialog.getSaveFileName(
            dialog, "Save merged index", "",
            "JSON Files (*.json);;All Files (*)",
            options=options)
        if save_file_name:
            with open(save_file_name, 'w') as f:
                json.dump(new_index, f)
            logger.info(f"Successfully wrote merged index to {save_file_name}")

    add_delframe = QFrame()
    add_delframe_lay = QHBoxLayout(add_delframe)
    dialog_lay.addWidget(add_delframe)

    add_button = QPushButton("Add index")
    dialog_lay.addWidget(add_button)
    add_button.pressed.connect(add_cb)

    del_button = QPushButton("Remove selected")
    dialog_lay.addWidget(del_button)
    del_button.pressed.connect(del_cb)

    merge_button = QPushButton("Attempt merge")
    dialog_lay.addWidget(merge_button)
    merge_button.pressed.connect(merge_cb)
    dialog.exec_()