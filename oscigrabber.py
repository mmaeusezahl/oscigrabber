#!python
#
# MIT License
#
# Copyright (c) 2021-2022 Max Mäusezahl
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

from asyncio.proactor_events import _ProactorBaseWritePipeTransport
import sys
import numpy as np
import pandas as pd
import pathlib

from datetime import datetime

from pyvisa import ResourceManager

from PyQt6.QtCore import QSize, QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox, QGridLayout, QLabel, \
    QLineEdit, QTextEdit, QVBoxLayout, QWidget, \
    QMainWindow, QTabWidget, QHBoxLayout, QGroupBox, QPushButton, QComboBox, \
    QCheckBox, QRadioButton, QSizePolicy
    
from pyqtgraph import GraphicsView, GraphicsLayout, mkColor, mkPen

#https://github.com/pyvisa/pyvisa-py/issues/96
class FatalInternalOscilloscopeError(EnvironmentError):
    pass

class Oscilloscope:
    def __init__(self):
        # On Windows you have to somehow install libUSB (i.e. by copying it 
        # to System32 folder)
        # Then use Zadig to replace the driver
        self.rm = ResourceManager("@py")

        self.num_channels = 2
        self.instr = None

    def list_resources(self):
        return filter(lambda x: "2391" in x, self.rm.list_resources())

    def safe_close(self):
        if not self.instr is None:
            try:
                self.instr.close()
            finally:
                self.instr = None

    def query(self, command):
        try:
            self.instr.write("*CLS")
            result = self.instr.query(command)[:-1]
            self.instr.write("*CLS")
            return result
        except Exception as ex:
            self.safe_close()
            raise FatalInternalOscilloscopeError from ex

    def write(self, command):
        try:
            self.instr.write("*CLS")
            self.instr.write(command)
            self.instr.write("*CLS")
        except Exception as ex:
            self.safe_close()
            raise FatalInternalOscilloscopeError from ex

        
    def query_binary_values(self):
        try:
            self.instr.write("*CLS")
            result = self.instr.query_binary_values(":WAVeform:DATA?", 
                                            datatype='H', 
                                            is_big_endian=False,
                                            expect_termination=True)
            self.instr.write("*CLS")
            return result
        except Exception as ex:
            self.safe_close()
            raise FatalInternalOscilloscopeError from ex

    def disconnect(self):
        self.safe_close()

    def connect(self, resource_string):
        self.safe_close()
        self.instr = self.rm.open_resource(resource_string)
        self.instr.timeout = 1000
        self.instr.write("*CLS")
        self.instr.write("*IDN?")
        self.read_num_channels()

    def get_identity(self):
        return self.query("*IDN?")

    def is_connected(self):
        return not self.instr is None

    def get_active_channels(self):
        result = []
        for ch in range(self.get_num_channels()):
            status = self.query(":STATUS? CHAN{}".format(ch + 1))
            result.append(status == "1")
        return result

    def read_num_channels(self):
        identity = self.get_identity()

        if "DSO-X 2002A" in identity:
            self.num_channels = 2
        elif "DSO-X 3024A" in identity:
            self.num_channels = 4
        else:
            self.num_channels = 2

    def get_num_channels(self):
        return self.num_channels

    def acquire(self, channels):
        active_channels = self.get_active_channels()

        acquire_channels = []
        
        for ch in range(self.get_num_channels()):
            if active_channels[ch] and ((channels is None) or channels[ch]):
                acquire_channels.append(ch)
        
        if len(acquire_channels) == 0:
            raise AttributeError("No active channel for acquisition.")

        oper = int(self.query(":OPERegister:CONDition?"))
        wasRunning = (oper & 0b1000) > 0 # 4th bit in the OPER Condition Register

        self.instr.timeout = 25000
        self.write(":DIG")

        result = {}

        for ch in acquire_channels:
            result[ch] = self.read_channel(ch)

        # Re-run the oscilloscope if it has been running before
        if wasRunning:
            self.write(":RUN")
            
        self.instr.timeout = 1000

        return result

    def read_channel(self, ch):
        self.write(":WAVeform:SOURce CHAN{}".format(ch + 1))
        self.write(":WAVeform:POINTs 1000000")
        self.write(":WAVeform:POINTs:MODE MAX")
        self.write(":WAVeform:FORMat WORD")
        self.write(":WAVeform:BYTeorder LSBFirst")
        preamble = self.query(":WAVeform:PREamble?")
        channel_range = self.query(":CHANnel{}:RANGe?".format(ch + 1))
        channel_offset = self.query(":CHANnel{}:OFFSet?".format(ch + 1))
        preamble = self.query(":WAVeform:PREamble?")
        raw_data = self.instr.query_binary_values(":WAVeform:DATA?", 
                                        datatype='H', 
                                        is_big_endian=False,
                                        expect_termination=True)

        raw_data = np.array(raw_data)
        maxVal = 2**16

        split_preamble = preamble.split(',')
        settings = {}
        settings['format'] = int(split_preamble[0])
        settings['type'] = int(split_preamble[1])
        settings['points'] = int(split_preamble[2])
        settings['count'] = int(split_preamble[3])
        settings['xincrement'] = float(split_preamble[4])
        settings['xorigin'] = float(split_preamble[5])
        settings['xreference'] = float(split_preamble[6])
        settings['yincrement'] = float(split_preamble[7])
        settings['yorigin'] = float(split_preamble[8])
        settings['yreference'] = float(split_preamble[9])

        settings['offset_V'] = float(channel_offset)
        settings['range_V'] = float(channel_range)

        settings['offset'] = ((maxVal/2 - settings['yreference']) * settings['yincrement'] + settings['yorigin'])
        settings['secperdiv'] = settings['points'] * settings['xincrement']/10
        settings['delay'] = ((settings['points']/2 - settings['xreference']) * settings['xincrement'] + settings['xorigin'])

        xdata = settings['xincrement'] * np.arange(0, settings['points']  - settings['xreference']) + settings['xorigin']
        ydata = settings['yincrement'] * (raw_data - settings['yreference']) + settings['yorigin']

        return xdata, ydata, settings, raw_data

class OsciPlotWidget(QWidget):
    def __init__(self):
        super().__init__()
        
        self.default_colors = [
            mkColor(242, 201, 19),
            mkColor(30, 242, 19),
            mkColor(45, 19, 242),
            mkColor(242, 19, 164)
        ]

        self.data = None
        self.plotdata = None
        self.init_gui()
    
    def init_gui(self):
        layout = QVBoxLayout(self)

        top_box = QGroupBox("Plotting Settings", self)
        layout.addWidget(top_box)
        
        top_layout = QHBoxLayout(top_box)
        
        self.btn_reset = QPushButton("Reset Zoom", self)
        self.btn_reset.clicked.connect(self.reset_view)
        top_layout.addWidget(self.btn_reset)
        top_layout.addSpacing(10)

        self.chb_norm = QCheckBox("Normalize Data", self)
        self.chb_norm.setChecked(False)
        self.chb_norm.stateChanged.connect(self.reload_data)
        top_layout.addWidget(self.chb_norm)
        top_layout.addSpacing(10)
        
        self.chb_ind_plots = QCheckBox("Individual Plots", self)
        self.chb_ind_plots.setChecked(False)
        self.chb_ind_plots.stateChanged.connect(self.reset_data)
        top_layout.addWidget(self.chb_ind_plots)

        top_layout.addStretch()

        self.plot_view = GraphicsView()
        self.plot_layout = GraphicsLayout()                                                   
        self.plot_view.setCentralItem(self.plot_layout)
        self.plot_widgets = []
        self.plot_widgets.append(self.plot_layout.addPlot(0,0))
        self.plot_widgets[0].setDownsampling(1,True,'peak')
        self.plot_widgets[0].setClipToView(True)
        self.plot_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout.addWidget(self.plot_view)

    def reset_view(self):
        if self.plotdata == None:
            return
        
        for p in self.plot_widgets:
            p.enableAutoRange()
        
    def reset_data(self):
        if self.plotdata == None:
            return
        
        self.set_data(self.data)

    def init_correct_plot_panes(self):
        if self.data != None and self.chb_ind_plots.isChecked() and len(self.data) != len(self.plot_widgets):
            for p in self.plot_widgets:
                self.plot_layout.removeItem(p)
            self.plot_widgets = []

            for i in range(len(self.data)):
                self.plot_widgets.append(self.plot_layout.addPlot(i,0))
                self.plot_widgets[-1].setDownsampling(1,True,'peak')
                self.plot_widgets[-1].setClipToView(True)
                self.plot_widgets[-1].setXLink(self.plot_widgets[0])

        elif (not self.chb_ind_plots.isChecked()) and (self.data == None or len(self.data) != 1):
            for p in self.plot_widgets:
                self.plot_layout.removeItem(p)
            self.plot_widgets = []

            self.plot_widgets.append(self.plot_layout.addPlot(0,0))
            self.plot_widgets[-1].setDownsampling(1,True,'peak')
            self.plot_widgets[-1].setClipToView(True)

    def normalized(self, ydata):
        if self.chb_norm.isChecked():
            ydata = ydata - min(ydata)
            ydata = ydata / max(ydata)
        return ydata

    def reload_data(self):
        if self.plotdata == None:
            return
        
        for plot_index, ch_data in enumerate(self.data):
            xdata, ydata, ch_index = ch_data
            ydata = self.normalized(ydata)
            self.plotdata[plot_index].setData(xdata, ydata)
            
        for p in self.plot_widgets:
            if self.chb_norm.isChecked():
                p.setLabel('left', "Normalized Voltage<br/>(U-U<sub>min</sub>)/(U<sub>max</sub>-U<sub>min</sub>)")
            else:
                p.setLabel('left', "Voltage U in V")

    def set_data(self, new_data):
        self.data = new_data
        self.plotdata = []

        self.init_correct_plot_panes()

        for p in self.plot_widgets:
            p.clear()

        for plot_index, ch_data in enumerate(self.data):
            xdata, ydata, ch_index = ch_data
            ydata = self.normalized(ydata)
            pen = mkPen(self.default_colors[ch_index], width=2)
            
            if self.chb_ind_plots.isChecked():
                self.plotdata.append(self.plot_widgets[plot_index].plot(xdata, ydata, pen=pen))
            else:
                self.plotdata.append(self.plot_widgets[0].plot(xdata, ydata, pen=pen))
        
        for p in self.plot_widgets:
            p.layout.setContentsMargins(0, 0, 0, 0)
            p.showGrid(x = True, y = True, alpha = 0.3)
            if self.chb_norm.isChecked():
                p.setLabel('left', "Normalized Voltage<br/>(U-U<sub>min</sub>)/(U<sub>max</sub>-U<sub>min</sub>)")
            else:
                p.setLabel('left', "Voltage U in V")
            p.setLabel('bottom', "Time t in s")
            p.autoRange()

class OsciSnapshot(QMainWindow):
    def __init__(self):
        super().__init__()

        self.default_colors = [
            mkColor(242, 201, 19),
            mkColor(30, 242, 19),
            mkColor(45, 19, 242),
            mkColor(242, 19, 164)
        ]

        self.num_channels = 2
        self.last_result = None
        self.last_load_dir = None
        self.target_directory = pathlib.Path.home()

        self.osci = Oscilloscope()

        self.init_gui()
        self.update_device_list()
        self.update_buttons_after_connect_state_changed()
        self.btn_save.setEnabled(False)
    
    def init_gui(self):
        self.central_widget = QWidget()
        self.central_layout = QHBoxLayout()
        self.central_widget.setLayout(self.central_layout)
        self.setCentralWidget(self.central_widget)

        self.tab_widget = QTabWidget()
        self.central_layout.addWidget(self.tab_widget)

        self.acquisition_tab = QWidget()
        self.acquisition_tab_layout = QHBoxLayout()
        self.acquisition_tab.setLayout(self.acquisition_tab_layout)
        self.tab_widget.addTab(self.acquisition_tab, "Acquisition")

        self.left_widget = QWidget()
        self.left_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.left_widget_layout = QVBoxLayout()
        self.left_widget.setLayout(self.left_widget_layout)
        self.acquisition_tab_layout.addWidget(self.left_widget, stretch=0)

        self.connection_group = QGroupBox("Device")
        self.connection_group_layout = QVBoxLayout()
        self.connection_group.setLayout(self.connection_group_layout)
        self.left_widget_layout.addWidget(self.connection_group)

        self.btn_scan_devices = QPushButton("Scan Devices")
        self.btn_scan_devices.clicked.connect(lambda : self.update_device_list())
        self.connection_group_layout.addWidget(self.btn_scan_devices)

        self.cmb_device_list = QComboBox()
        self.cmb_device_list.setMinimumWidth(150)
        self.connection_group_layout.addWidget(self.cmb_device_list)
        
        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.btn_connect_clicked)
        self.connection_group_layout.addWidget(self.btn_connect)

        self.channels_group = QGroupBox("Channels")
        self.channels_group_layout = QVBoxLayout()
        self.channels_group.setLayout(self.channels_group_layout)
        self.left_widget_layout.addWidget(self.channels_group)

        self.btn_acquire = QPushButton("Acquire")
        self.btn_acquire.clicked.connect(self.acquire)
        self.channels_group_layout.addWidget(self.btn_acquire)

        self.chb_all_channels = QRadioButton("All Active Channels")
        self.chb_all_channels.setChecked(True)
        self.channels_group_layout.addWidget(self.chb_all_channels)
        self.chb_only_channels = QRadioButton("Only Theese Channels:")
        self.chb_only_channels.toggled.connect(self.chb_only_channels_toggled)
        self.channels_group_layout.addWidget(self.chb_only_channels)

        self.chb_channels = None
        self.chb_channels_widget = QWidget()
        self.chb_channels_widget_layout = QVBoxLayout()
        self.chb_channels_widget.setLayout(self.chb_channels_widget_layout)
        self.channels_group_layout.addWidget(self.chb_channels_widget)
        self.init_chb_channels()
        
        self.saving_group = QGroupBox("Saving")
        self.saving_group_layout = QGridLayout()
        self.saving_group.setLayout(self.saving_group_layout)
        self.left_widget_layout.addWidget(self.saving_group)

        self.btn_select_folder = QPushButton("Select Target Directory")
        self.btn_select_folder.clicked.connect(self.btn_select_folder_clicked)
        self.saving_group_layout.addWidget(self.btn_select_folder, 0, 0, 1, 2)
        
        self.saving_group_layout.addWidget(QLabel("Filename:"), 1, 0)
        self.txb_filename = QLineEdit()
        input_validator = QRegularExpressionValidator(QRegularExpression("[0-9a-zA-Zäöüß_\-. ]*"), self.txb_filename)
        self.txb_filename.setValidator(input_validator)
        self.saving_group_layout.addWidget(self.txb_filename, 1, 1)
        
        self.saving_group_layout.addWidget(QLabel("Comment:"), 2, 0, 1, 2)
        self.txb_comment = QTextEdit()
        self.txb_comment.sizeHint = lambda : QSize(50,50)
        self.txb_comment.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.saving_group_layout.addWidget(self.txb_comment, 3, 0, 1, 2)
        
        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.btn_save_clicked)
        self.saving_group_layout.addWidget(self.btn_save, 4, 0, 1, 2)

        self.left_widget_layout.addStretch()
        
        self.acquisition_plot_widget = OsciPlotWidget()
        self.acquisition_plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.acquisition_tab_layout.addWidget(self.acquisition_plot_widget, stretch=1)

        self.review_tab = QWidget()
        self.review_tab_layout = QHBoxLayout()
        self.review_tab.setLayout(self.review_tab_layout)
        self.tab_widget.addTab(self.review_tab, "Review")

        self.review_left_widget = QWidget()
        self.review_left_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.review_left_widget_layout = QVBoxLayout()
        self.review_left_widget.setLayout(self.review_left_widget_layout)
        self.review_tab_layout.addWidget(self.review_left_widget, stretch=0)

        self.loading_group = QGroupBox("Loading")
        self.loading_group_layout = QVBoxLayout()
        self.loading_group.setLayout(self.loading_group_layout)
        self.review_left_widget_layout.addWidget(self.loading_group)

        self.btn_load = QPushButton("Load CSV...")
        self.btn_load.clicked.connect(self.btn_load_clicked)
        self.loading_group_layout.addWidget(self.btn_load)
        
        self.txb_review_comment = QTextEdit()
        self.txb_review_comment.sizeHint = lambda : QSize(200,200)
        self.txb_review_comment.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.txb_review_comment.setEnabled(False)
        self.loading_group_layout.addWidget(self.txb_review_comment)
        
        self.review_left_widget_layout.addStretch()

        self.review_plot_widget = OsciPlotWidget()
        self.review_plot_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.review_tab_layout.addWidget(self.review_plot_widget, stretch=1)

        self.setWindowTitle("Oscilloscope Snapshot")

    def chb_only_channels_toggled(self, _):
        self.update_chb_channels_enabled()

    def btn_select_folder_clicked(self):
        new_dir = QFileDialog.getExistingDirectory(None, "Target Directory", str(self.target_directory))
        
        if len(new_dir) == 0:
            return

        self.target_directory = pathlib.Path(new_dir).resolve()

    def btn_save_clicked(self):
        filename = self.txb_filename.text().strip()
        if len(filename) == 0:
            self.show_error("Filename can't be empty (or whitespace only).")
            return
        
        if not filename.endswith(".csv"):
            filename = filename + ".csv"
        
        full_file = self.target_directory.joinpath(filename)

        if full_file.exists():
            button_reply = QMessageBox.question(self,"File Exists", 
                                "Do you want to overwrite the file?", 
                                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No,)
            
            if button_reply == QMessageBox.StandardButton.No:
                return
        
        comment = self.txb_comment.toPlainText().strip().replace('\n', ' ').replace('\r', '')

        columns = {}
        info_strings = []
        for ch in self.last_result.keys():
            xdata, ydata, settings, _ = self.last_result[ch]
            if len(columns) == 0:
                columns['time in s'] = xdata
            columns['channel {} in V'.format(ch + 1)] = ydata

            
            info_string = "Channel {}: ".format(ch + 1)
            info_string = info_string + "Range={}V, ".format(settings["range_V"])
            info_string = info_string + "Offset={}V\n".format(settings["offset_V"])

            info_strings.append(info_string)
        
        with open(full_file, "w") as f:
            f.write("Saved on: {}\n".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            for info_string in info_strings:
                f.write(info_string)
            f.write("Comment: {}\n\n".format(comment))

        df = pd.DataFrame(data = columns)
        df.to_csv(full_file, index=False, mode="a")

    def btn_load_clicked(self):
        if self.last_load_dir is None:
            self.last_load_dir = self.target_directory

        load_file, _ = QFileDialog.getOpenFileName(None, "Load CSV file", str(self.last_load_dir), "CSV-Files (*.csv)")

        if len(load_file) == 0:
            return
        
        load_file = pathlib.Path(load_file).absolute()
        self.last_load_dir = load_file.parent

        first_empty_line = 1
        header = ""
        with open(load_file, "r") as f:
            next_line = f.readline()
            while len(next_line.strip()) > 0:
                header += next_line
                first_empty_line = first_empty_line + 1
                next_line = f.readline()
        
        df = pd.read_csv(load_file, skiprows=first_empty_line)
        
        try:
            new_data = []
            xdata = df["time in s"]

            for ch in range(4):
                column_name = "channel {} in V".format(ch + 1)
                if column_name in df.columns:
                    ydata = df[column_name]
                    new_data.append((xdata, ydata, ch))

            self.review_plot_widget.set_data(new_data)

            self.txb_review_comment.setPlainText(header)

        except:
            self.show_error("Incorrect CSV format")

    def btn_connect_clicked(self):
        if self.osci.is_connected():
            self.disconnect()
        else:
            self.connect()

    def show_error(self, ex):
        error_dialog = QMessageBox()
        error_dialog.setWindowTitle("Error")
        error_dialog.setText(repr(ex))
        error_dialog.setIcon(QMessageBox.Icon.Critical)
        error_dialog.exec()

    def acquire(self):
        channels = None
        if self.chb_only_channels.isChecked():
            channels = []

            for ch in range(self.num_channels):
                channels.append(self.chb_channels[ch].isChecked())

        try:
            result = self.osci.acquire(channels)
            self.last_result = result
            self.btn_save.setEnabled(True)
            
            new_data = []
            for ch in result.keys():
                xdata, ydata, settings, raw_data = result[ch]
                new_data.append((xdata, ydata, ch))

            self.acquisition_plot_widget.set_data(new_data)

        except FatalInternalOscilloscopeError as ex:
            self.update_buttons_after_connect_state_changed()
            self.show_error(ex)
            return
        except Exception as ex:
            self.show_error(ex)
            return

    def update_chb_channels_enabled(self):
        self.chb_channels_widget.setEnabled(self.chb_only_channels.isChecked())

    def init_chb_channels(self):
        if not self.chb_channels is None:
            for chb in self.chb_channels:
                self.chb_channels_widget_layout.removeWidget(chb)
            self.chb_channels.clear()

        self.chb_channels = []
        for ch in range(self.num_channels):
            chb_new = QCheckBox("Channel {}".format(ch + 1))
            self.chb_channels_widget_layout.addWidget(chb_new)
            self.chb_channels.append(chb_new)

        self.update_chb_channels_enabled()

    def update_device_list(self):
        res = self.osci.list_resources()
        self.cmb_device_list.clear()
        self.cmb_device_list.addItems(res)

    def update_buttons_after_connect_state_changed(self):
        if self.osci.is_connected():
            self.btn_connect.setText("Disconnect")
            self.channels_group.setEnabled(True)
        else:
            self.btn_connect.setText("Connect")
            self.channels_group.setEnabled(False)
        
        self.init_chb_channels()
        self.update_chb_channels_enabled()

    def disconnect(self):
        self.osci.disconnect()
        self.update_buttons_after_connect_state_changed()

    def connect(self):
        self.osci.connect(self.cmb_device_list.currentText())
        self.num_channels = self.osci.get_num_channels()
        self.update_buttons_after_connect_state_changed()

def main():
    app = QApplication(sys.argv)
    main_window = OsciSnapshot()
    main_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()