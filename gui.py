from PyQt5.QtCore import (Qt, QBuffer)
from PyQt5.QtWidgets import (QWidget, QApplication, QMainWindow, QVBoxLayout,
    QHBoxLayout, QFrame, QPushButton, QPlainTextEdit, QGroupBox, QRadioButton,
    QSizePolicy, QGridLayout, QLineEdit, QLabel, QListWidget, QListWidgetItem,
    QComboBox, QDialog, QProgressBar, QFileDialog, QMessageBox,
    QAbstractItemView)
from PyQt5.QtMultimedia import (QMediaPlayer, QMediaContent)
from functools import partial
import pygame
import PyQt5
import sys
import io
import os
from log import display_handler, logger
from core import PonySorter_B
from utils import key_shift, qwertymap0, qwertymap1, qwertymap2

class PonySorter_B_GUI(QMainWindow):
    def __init__(self, conf):
        super().__init__()
        self.menu_bar = self.menuBar()
        self.conf = conf
        file_menu = self.menu_bar.addMenu("File")

        load_episode = file_menu.addAction("Load source audio (episode)")
        load_episode.triggered.connect(self.load_episode_dialog)
        load_episode.setShortcut('Ctrl+1')

        self.last_save = ''
        self.filter_settings = {
            'min_noise': 'Clean'
        }
        self.line_idx = 0
        self.line_view_idx = 0

        save_action = file_menu.addAction("Save")
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save)

        save_as = file_menu.addAction("Save project as")
        save_as.setShortcut('Ctrl+Shift+S')
        save_as.triggered.connect(self.save_as_dialog)

        def load_dialog():
            options=QFileDialog.Options()
            file_name, _ = QFileDialog.getOpenFileName(self,
                'Load project', '',
                'JSON Files (*.json);;All Files (*)', options=options)
            if file_name:
                self.load_from_project(file_name)

        load = file_menu.addAction("Load project")
        load.setShortcut('Ctrl+O')
        load.triggered.connect(load_dialog)

        def update_progress(i):
            self.progress_bar.setValue(i)

        def export_audio():
            exp_dir = self.conf.get('exp_dir', 'export')
            os.makedirs(exp_dir, exist_ok=True)
            self.core.export_audio(exp_dir, update_progress,
                sig_to_proc=[self.core.loaded_sig])
            self.core.export_audacity_labels(exp_dir, update_progress,
                sig_to_proc=[self.core.loaded_sig])
            logger.info(f'Finished export')

        def export_all_audio():
            exp_dir = self.conf.get('exp_dir', 'export')
            os.makedirs(exp_dir, exist_ok=True)
            self.core.export_audio(exp_dir, update_progress)
            self.core.export_audacity_labels(exp_dir, update_progress)
            logger.info(f'Finished export')

        #def export_audacity_labels():
        #    exp_dir = self.conf.get('exp_dir', 'export')
        #    os.makedirs(exp_dir, exist_ok=True)
        #    self.core.export_audacity_labels(exp_dir)
        #    logger.info(f'Exported audacity labels to {exp_dir}')

        export_action = file_menu.addAction("Export data for current episode")
        export_action.setShortcut('Ctrl+E')
        export_action.triggered.connect(export_audio)
        
        export_all_action = file_menu.addAction("Export data for all") 
        export_all_action.setShortcut('Ctrl+Shift+E')
        export_all_action.triggered.connect(export_all_audio)

        #export_aud_action = file_menu.addAction("Export audacity labels") 
        #export_aud_action.setShortcut('Ctrl+Shift+E')
        #export_aud_action.triggered.connect(export_audacity_labels)

        def filter_set_cb(key):
            self.filter_settings['min_noise'] = key
            self.rebuild_filter()

        def filter_dialog():
            dialog = QDialog()
            dialog.setWindowTitle('Filter')
            filter_lay = QVBoxLayout(dialog)

            filter_box, filter_field = self.labeled_field(
                "Min noise", QComboBox())
            noise_filters = ['Clean', 'Noisy', 'Very Noisy']
            for i,f in enumerate(noise_filters):
                filter_field.addItem(f)
                if f == self.filter_settings['min_noise']:
                    filter_field.setCurrentIndex(i)

            filter_field.currentTextChanged.connect(filter_set_cb)
            filter_lay.addWidget(filter_box)

            dialog.exec_()

        filter_action = self.menu_bar.addAction("Filter")
        filter_action.triggered.connect(filter_dialog)
        filter_action.setShortcut('Ctrl+F')

        main = QFrame()
        self.setCentralWidget(main)
        hlayout = QHBoxLayout(main)

        self.setWindowTitle('PonySorter B')
        self.setFixedWidth(2000)

        non_browser = QFrame()
        hlayout.addWidget(non_browser)
        vlayout = QVBoxLayout(non_browser)

        self.rebuild_filter()

        vlayout.addWidget(self.selection_section())

        def noisy_callback(n):
            if self.line_ct == 0:
                return
            if n == 'Clean':
                n = ''
            r = self.core.edit_line(self.line_idx, None, 
                {'parse': {'noise': n}})

        # Line data editing
        noise_box = QGroupBox()
        noise_lay = QHBoxLayout(noise_box) 
        noise_lay.setAlignment(Qt.AlignRight)
        noisy_settings = ['Clean','Noisy','Very Noisy']
        self.noisy_buttons = {}
        for i,n in enumerate(noisy_settings):
            n_button = QRadioButton(n)
            n_button.clicked.connect(partial(noisy_callback, n))
            self.noisy_buttons[n] = n_button
            noise_lay.addWidget(n_button)
        self.fix_noisy_buttons()
        vlayout.addWidget(noise_box)

        line_data_bar = QFrame()
        vlayout.addWidget(line_data_bar)
        line_data_lay = QHBoxLayout(line_data_bar)
        line_data_lay.setAlignment(Qt.AlignLeft)

        character_box, self.character_field = self.labeled_field(
            "Character", QLineEdit())
        self.character_field.setEnabled(False)
        line_data_lay.addWidget(character_box)

        mood_box, self.mood_field = self.labeled_field(
            "Mood", QLineEdit()
        )
        self.mood_field.setEnabled(False)
        line_data_lay.addWidget(mood_box)

        # Transcript considered out of scope.
        # Substantial modifications would require export filename modifications as well.
        #transcript_box, self.transcript_field = self.labeled_field(
            #"Transcript", QLineEdit()) 
        #vlayout.addWidget(transcript_box)

        self.ts_display = QLabel(f'Start: {0.0:.9f}')
        self.te_display = QLabel(f'End: {0.0:.9f}')
        time_frame = QFrame()
        time_lay = QVBoxLayout(time_frame)
        time_lay.addWidget(self.ts_display)
        time_lay.addWidget(self.te_display)
        line_data_lay.addWidget(time_frame)

        self.file_display = QLabel('File: <FILE>')
        vlayout.addWidget(self.file_display)

        # Log display
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        log_group_box = QGroupBox("Log")
        log_group_box_lay = QVBoxLayout(log_group_box)
        log_group_box_lay.addWidget(self.log_display)
        display_handler.set_handler(self.set_display)
        vlayout.addWidget(log_group_box)

        self.core = PonySorter_B(conf)
        self.line_ct = 0

        self.progress_bar = QProgressBar()
        vlayout.addWidget(self.progress_bar)

        def line_browser_select():
            idx = self.line_browser.currentRow()
            self.set_view_idx(idx)
            self.load_line_cb()

        self.line_browser = QListWidget()
        self.line_browser.setFixedWidth(600)
        self.line_browser.setSelectionMode(QAbstractItemView.SingleSelection)
        self.line_browser.itemSelectionChanged.connect(line_browser_select)
        hlayout.addWidget(self.line_browser)

        if len(conf['default_project']):
            self.load_from_project(conf['default_project'])

    def rebuild_filter(self): 
        if self.filter_settings['min_noise'] == 'Clean':
            self.filter_map = None
            if hasattr(self, 'core'):
                self.rebuild_line_browser()
                self.load_line_cb()
            return
        elif self.filter_settings['min_noise'] == 'Noisy':
            filtered_lines = [
                i for (i,l) in enumerate(self.core.lines) if 
                l['original_noise'] in ['Noisy','Very Noisy']]
        elif self.filter_settings['min_noise'] == 'Very Noisy':
            filtered_lines = [
                i for (i,l) in enumerate(self.core.lines) if 
                l['original_noise'] == 'Very Noisy']
        self.filter_map = {}
        for i,i2 in enumerate(filtered_lines):
            self.filter_map[i] = i2
            if i2 == self.line_view_idx:
                self.set_view_idx(i)
        if self.line_view_idx > len(self.filter_map):
            self.set_view_idx(0)
        self.rebuild_line_browser()
        self.load_line_cb()

    def set_view_idx(self, i):
        self.line_view_idx = i
        self.line_idx = self.filter_index(i)
        self.line_browser.setCurrentRow(self.line_view_idx)

    def filter_index(self, view_idx):
        if self.filter_map is None:
            return view_idx
        else:
            if len(self.filter_map):
                return self.filter_map[view_idx]
            else:
                return None
        
    def save_as_dialog(self):
        if not hasattr(self.core, 'lines'):
            logger.info('Nothing to save')
            return
        options = QFileDialog.Options()
        default_save = 'save.json'
        if len(self.conf['default_project']):
            default_save = self.conf['default_project']
        file_name, _ = QFileDialog.getSaveFileName(
            self, "Save project", default_save,
            "JSON Files (*.json);;All Files (*)",
            options=options)
        if file_name:
            self.save_project(file_name)


    def save(self):
        if not len(self.last_save):
            self.save_as_dialog()
        else:
            self.save_project(self.last_save)

    def save_project(self, file_name):
        if not os.path.exists(file_name):
            reply = QMessageBox.question(self, 'Set as default project',
            'Set this project as default on startup?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply:
                self.conf['default_project'] = file_name
        add_data = {
            'line_view_idx': self.line_view_idx,
            'filter_settings': self.filter_settings
        }
        self.core.save_progress(file_name, add_data)
        self.last_save = file_name
        logger.info(f'Saved to {file_name}')
    
    def load_from_project(self, f):
        if not os.path.exists(f):
            logger.warn(
                f'Did not find default project {self.conf["default_project"]}')
            return
        logger.info(f'Loading project {f}')
        add_data, save_dict = self.core.load_progress(f)
        if add_data is None:
            logger.error(f'Failed to load from project {f}')
            return
        try:
            self.load_selection(save_dict['loaded_sig'], None)
        except KeyError:
            logger.error(f'Failed to load from project {f}')
            return

        self.set_view_idx(add_data.get('line_view_idx', self.line_view_idx))
        if 'filter_settings' in add_data:
            self.filter_settings = add_data.get('filter_settings')
        self.rebuild_filter()
        self.load_line_cb()
        logger.info(f'Loaded {f}')

    def fix_noisy_buttons(self):
        for i,t in enumerate(self.noisy_buttons.items()):
            k,v = t
            n_key = qwertymap2[i]
            v.setText(v.text()+f' ({n_key})')
            v.setShortcut(n_key)

    def rebuild_line_browser(self):
        assert hasattr(self.core, 'lines')
        self.line_browser.clear()
        if self.filter_map is None:
            for l in self.core.lines:
                self.line_browser.addItem(l['label'])
        else:
            for actual_idx in self.filter_map.values():
                l = self.core.lines[actual_idx]
                self.line_browser.addItem(l['label'])

    def load_selection(self, sig, update_fn):
        if sig is None:
            return
        logger.info(f'Loading {sig}')
        self.line_ct = self.core.load_sig(sig, update_fn)
        if self.line_ct == 0:
            return

        self.rebuild_filter()
        self.rebuild_line_browser()

        self.line_idx = 0
        self.line_view_idx = 0
        self.load_line_cb()

    def load_episode_dialog(self):
        dialog = QDialog()
        dialog.setWindowTitle('Load source audio (episode)')
        layout = QVBoxLayout(dialog)

        # Season/episodes
        season_box, self.season_field = self.labeled_field(
            "Season", QComboBox())
        ep_box, self.ep_field = self.labeled_field(
            "Episode", QComboBox())
        season_ep_frame = QFrame()
        season_ep_lay = QVBoxLayout(season_ep_frame)
        season_ep_lay.addWidget(season_box)
        season_ep_lay.addWidget(ep_box)

        # Seasons
        seasons = []
        episodes = {}
        for sig in self.core.get_season_ep_sigs():
            season_num = int(sig[1:3])
            if not season_num in episodes:
                episodes[season_num] = []
            episodes[season_num].append(sig)
            if season_num in seasons:
                continue
            seasons.append(season_num)
            self.season_field.addItem(str(season_num))

        # Load episode callback
        def load_episodes(i):
            self.ep_field.clear()
            for ep in episodes[seasons[i]]:
                ep_num = int(ep[4:6])
                self.ep_field.addItem(str(ep_num), ep)

        self.season_field.currentIndexChanged.connect(load_episodes)
        if len(seasons):
            load_episodes(0)

        layout.addWidget(season_ep_frame)

        bot_row = QFrame()
        layout.addWidget(bot_row)
        bot_lay = QHBoxLayout(bot_row)

        progress_bar = QProgressBar()
        layout.addWidget(progress_bar)

        def update_progress(i):
            progress_bar.setValue(i)

        def load_selection():
            sig = self.ep_field.currentData()
            self.load_selection(sig, update_progress)
            dialog.accept()

        load_button = QPushButton("Load")
        load_button.clicked.connect(load_selection)
        bot_lay.addWidget(load_button)

        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        bot_lay.addWidget(cancel_button)
        dialog.exec_()

    def labeled_field(self, label, widget):
        group_box = QGroupBox(label)
        group_box_lay = QVBoxLayout(group_box)
        group_box_lay.setContentsMargins(4,4,4,4)
        group_box_lay.addWidget(widget)
        return group_box, widget

    def set_display(self, text):
        self.log_display.setPlainText(text)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum())

    def build_nav_buttons(self, segments=None, line=None):
        new_nav_buttons = QGroupBox("Selection")
        new_nav_buttons.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Maximum)
        new_nav_buttons_lay = QGridLayout(new_nav_buttons)

        def select_callback(tag):
            self.core.edit_line(self.line_idx, tag, None)

        def preview_callback(tag):
            assert hasattr(self, 'segments')
            with io.BytesIO() as data:
                self.segments[tag].export(data, format='wav')
                self._sound = pygame.mixer.Sound(data)
                self._sound.play()

        if segments is None: 
            n_buttons = 4
            for i in range(n_buttons): 
                select = QRadioButton(f"Select")
                preview = QPushButton(f"Preview")
                new_nav_buttons_lay.addWidget(preview, i, 0)
                new_nav_buttons_lay.addWidget(select, i, 1)
            if hasattr(self, 'nav_buttons'):
                self.nav_buttons.deleteLater()
        else:
            assert line is not None
            n_buttons = len(segments)
            for i,v in enumerate(segments.items()): 
                tag, segment = v

                preview_key = qwertymap0[i]
                preview = QPushButton(f"Preview {tag} ({preview_key})")
                preview.setShortcut(preview_key)
                preview.clicked.connect(partial(preview_callback, tag))

                select_key = qwertymap1[i]
                select = QRadioButton(f"Select {tag} ({select_key})")
                select.setShortcut(select_key)
                select.clicked.connect(partial(select_callback, tag))
                if tag == line['selected_tag']:
                    select.setChecked(True)
                new_nav_buttons_lay.addWidget(preview, i, 0)
                new_nav_buttons_lay.addWidget(select, i, 1)
            if hasattr(self, 'nav_buttons'):
                self.nav_buttons.deleteLater()
        self.select_layout.insertWidget(1, new_nav_buttons, stretch=3)
        self.nav_buttons = new_nav_buttons

    def selection_section(self):
        section = QFrame()
        self.select_layout = QHBoxLayout(section)

        def nav_back():
            if self.line_view_idx >= 1:
                assert self.line_ct > 0
                self.set_view_idx(self.line_view_idx - 1)
                self.load_line_cb()
        def nav_forward():
            if self.filter_map is None:
                if self.line_view_idx < (self.line_ct - 1):
                    self.set_view_idx(self.line_view_idx + 1)
                    self.load_line_cb()
            else:
                if self.line_view_idx < (len(self.filter_map) - 1):
                    self.set_view_idx(self.line_view_idx + 1)
                    self.load_line_cb()

        back_arrow = QPushButton('<') 
        back_arrow.clicked.connect(nav_back)
        back_arrow.maximumWidth = 40
        back_arrow.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        back_arrow.setShortcut('<')
        forward_arrow = QPushButton('>') 
        forward_arrow.clicked.connect(nav_forward)
        forward_arrow.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        forward_arrow.setShortcut('>')
        self.select_layout.addWidget(back_arrow)
        self.build_nav_buttons()
        self.select_layout.addWidget(forward_arrow)
        return section

    def load_line_cb(self):
        if self.line_idx is None:
            self.character_field.setText('')
            self.mood_field.setText('')
            self.ts_display.setText('')
            self.te_display.setText('')
            self.file_display.setText('')
            for n in self.noisy_buttons.values():
                n.setChecked(False)
                n.setEnabled(False)
            self.build_nav_buttons()
            return
        # No-op, some stray events emit invalid idx
        if self.line_idx > len(self.core.lines):
            return
        self.line_browser.setCurrentRow(self.line_view_idx)
        sources, line, preview_segments = self.core.load_line(self.line_idx)
        self.character_field.setText(line['parse']['char'])
        self.mood_field.setText(line['parse']['emotion'])
        self.ts_display.setText(f"Start: {float(line['ts']):.7f}")
        self.te_display.setText(f"End: {float(line['te']):.7f}")
        self.file_display.setText(f"File: {line['label']}")
        noise = line['parse']['noise']
        # Should mark original
        if not len(noise):
            self.noisy_buttons['Clean'].setChecked(True)
        else:
            self.noisy_buttons[noise].setChecked(True)
        for k,v in self.noisy_buttons.items():
            v.setEnabled(True)
            if k == line['original_noise'] or (
                not len(line['original_noise']) and k == 'Clean'):
                v.setText(k+'*') 
            else:
                v.setText(k)

        # Qt seems to internally reset a radio button's shortcuts every time
        # the text is set, due to the ampersand shortcut trick,
        # so this is required to fix the shortcuts after changing lines.
        self.fix_noisy_buttons()

        self.segments = preview_segments
        self.build_nav_buttons(preview_segments, line)

    def closeEvent(self, event):
        if self.core.dirty_flag:
            close = QMessageBox.question(self, 
                'Save before exit',
                'Unsaved changes. Save before exiting?',
                 QMessageBox.Save | QMessageBox.No | QMessageBox.Cancel,
                 QMessageBox.Cancel)
            if close == QMessageBox.Save:
                self.save()
            elif close == QMessageBox.Cancel:
                event.ignore()
                return
            event.accept()

def gui_main(conf):
    pygame.mixer.init()
    app = QApplication(sys.argv)

    w = PonySorter_B_GUI(conf)
    w.show()
    app.exec()
    pygame.quit()