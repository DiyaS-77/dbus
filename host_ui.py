import os

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from PyQt6.QtCore import Qt
from PyQt6.QtCore import QFileSystemWatcher
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QComboBox
from PyQt6.QtWidgets import QFileDialog
from PyQt6.QtWidgets import QGridLayout
from PyQt6.QtWidgets import QGroupBox
from PyQt6.QtWidgets import QHeaderView
from PyQt6.QtWidgets import QHBoxLayout
from PyQt6.QtWidgets import QInputDialog
from PyQt6.QtWidgets import QLabel
from PyQt6.QtWidgets import QLayout
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtWidgets import QListWidget
from PyQt6.QtWidgets import QListWidgetItem
from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtWidgets import QTabWidget
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtWidgets import QWidget

import style_sheet as styles
from libraries.bluetooth import constants
from libraries.bluetooth.bluez import BluetoothDeviceManager
from Utils.utils import get_controller_interface_details
from Utils.utils import validate_bluetooth_address


class TestApplication(QWidget):
    """Main GUI class for the Bluetooth Test Host."""

    def __init__(self, interface=None, back_callback=None, log=None, bluetoothd_log_file_path=None, pulseaudio_log_file_path=None, obexd_log_file_path=None, ofonod_log_file_path=None, hcidump_log_name=None):
        """Initialize the Test Host widget.

        Args:
            interface: Bluetooth adapter interface (e.g., hci0).
            back_callback: Optional callback to trigger on back action.
            log: Logger instance used for logging.
             bluetoothd_log_file_path: Path to bluetoothd log.
            pulseaudio_log_file_path: Path to PulseAudio log.
            obexd_log_file_path: Path to obexd log.
            ofonod_log_file_path: Path to ofonod log.
            hcidump_log_name: Name of hcidump log file.
        """
        super().__init__()
        self.bus=dbus.SystemBus()
        self.interface = interface
        self.log_path = log.log_path
        self.log = log
        self.bluetoothd_log_file_path = bluetoothd_log_file_path
        self.pulseaudio_log_file_path = pulseaudio_log_file_path
        self.obexd_log_file_path = obexd_log_file_path
        self.ofonod_log_file_path = ofonod_log_file_path
        self.hcidump_log_name = hcidump_log_name
        self.back_callback = back_callback
        self.bluetooth_device_manager = BluetoothDeviceManager(log=self.log, interface=self.interface)
        self.paired_devices = {}
        self.connected_devices = {}
        self.main_grid_layout = None
        self.gap_button = None
        self.profiles_list_widget = None
        self.profile_methods_widget = None
        self.profile_description_text_browser = None
        self.profile_methods_widget = None
        self.device_tab_widget = None
        self.grid = None
        self.refresh_button = None
        self.setup_dbus_signals()
        self.initialize_host_ui()


    def setup_dbus_signals(self):
        DBusGMainLoop(set_as_default=True)
        self.bus.add_signal_receiver(
            self.on_properties_changed,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            arg0="org.bluez.Device1",
            path_keyword="path"
        )

    def on_properties_changed(self, interface, changed, invalidated, path):
        if interface != "org.bluez.Device1" or "Paired" not in changed:
            return

        paired = changed["Paired"]
        device_address = path.split("dev_")[-1].replace("_", ":")

        if paired:
            self.log.info(f"[Signal] Device paired: {device_address}")
            self.add_paired_device_to_list(device_address)
            QMessageBox.information(self, "Pairing Successful", f"{device_address} was paired successfully.")
        else:
            self.log.info(f"[Signal] Pairing failed or device unpaired: {device_address}")
            QMessageBox.warning(self, "Pairing Failed", f"Pairing with {device_address} failed.")
            self.remove_device_from_list(device_address)

    def load_paired_devices(self):
        """Loads and displays all paired Bluetooth devices into the profiles list widget."""
        list_index = self.profiles_list_widget.count() - 1
        self.paired_devices = self.bluetooth_device_manager.get_paired_devices()
        unique_devices = set(self.paired_devices.keys())
        for device_address in unique_devices:
            device_item = QListWidgetItem(device_address)
            device_item.setFont(QFont("Courier New", 10))
            device_item.setForeground(Qt.GlobalColor.black)
            list_index += 1
            self.profiles_list_widget.insertItem(list_index, device_item)

    def add_controller_details_row(self, row, label, value):
        """Adds a new row to the controller details grid layout.

        Args:
            row: The row index in the grid layout where this entry should be placed.
            label: The text label to describe the data.
            value: The corresponding value to display alongside the label.
        """
        label_widget = QLabel(label)
        label_widget.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        label_widget.setObjectName("label_widget")
        label_widget.setStyleSheet(styles.color_style_sheet)
        value_widget = QLabel(value)
        value_widget.setObjectName("value_widget")
        value_widget.setFont(QFont("Arial", 10))
        value_widget.setStyleSheet(styles.color_style_sheet)
        self.grid.addWidget(label_widget, row, 0)
        self.grid.addWidget(value_widget, row, 1)

    def set_discoverable_mode(self, enable):
        """Enable or disable discoverable mode on the Bluetooth adapter.

        Args:
            enable: True to enable, False to disable.
        """
        if enable:
            self.set_discoverable_on_button.setEnabled(False)
            self.set_discoverable_off_button.setEnabled(True)
            self.bluetooth_device_manager.set_discoverable_mode(True)
            timeout = int(self.discoverable_timeout_input.text())
            if timeout > 0:
                self.discoverable_timeout_timer = QTimer()
                self.discoverable_timeout_timer.timeout.connect(lambda: self.set_discoverable_mode(False))
                self.discoverable_timeout_timer.setSingleShot(True)
                self.discoverable_timeout_timer.start(timeout * 1000)
            self.log.info("Discoverable mode is set to ON")
        else:
            self.set_discoverable_on_button.setEnabled(True)
            self.set_discoverable_off_button.setEnabled(False)
            self.bluetooth_device_manager.set_discoverable_mode(False)
            if hasattr(self, 'discoverable_timeout_timer'):
                self.discoverable_timeout_timer.stop()
            self.log.info("Discoverable mode is set to OFF")

    def start_device_discovery(self):
        """Start device discovery."""
        self.inquiry_timeout = int(self.inquiry_timeout_input.text()) * 1000
        if self.inquiry_timeout == 0:
            self.set_discovery_on_button.setEnabled(False)
            self.set_discovery_off_button.setEnabled(True)
            self.bluetooth_device_manager.start_discovery()
        else:
            self.timer = QTimer()
            self.timer.timeout.connect(self.handle_discovery_timeout)
            self.timer.timeout.connect(lambda: self.set_discovery_off_button.setEnabled(False))
            self.timer.start(self.inquiry_timeout)
            self.set_discovery_on_button.setEnabled(False)
            self.set_discovery_off_button.setEnabled(True)
            self.bluetooth_device_manager.start_discovery()
        self.log.info("Device discovery has started")

    def handle_discovery_timeout(self):
        """Handles the Bluetooth discovery timeout event"""
        self.timer.stop()
        self.bluetooth_device_manager.stop_discovery()
        self.log.info("Discovery stopped due to timeout.")
        self.display_discovered_devices()

    def stop_device_discovery(self):
        """Stops device Discovery"""
        self.set_discovery_off_button.setEnabled(False)
        self.timer = QTimer()
        if self.inquiry_timeout == 0:
            self.bluetooth_device_manager.stop_discovery()
            self.display_discovered_devices()
        else:
            self.timer.stop()
            self.bluetooth_device_manager.stop_discovery()
            self.display_discovered_devices()
            self.set_discovery_off_button.setEnabled(False)
        self.log.info("Device discovery has stopped")

    def display_discovered_devices(self):
        """Display discovered devices in a table with options to pair or connect."""
        self.timer.stop()
        bold_font = QFont()
        bold_font.setBold(True)
        small_font = QFont()
        small_font.setBold(True)
        small_font.setPointSize(8)
        discovered_devices = self.bluetooth_device_manager.get_discovered_devices()
        self.clear_device_discovery_results()
        self.table_widget = QTableWidget(0, 3)
        self.table_widget.setHorizontalHeaderLabels(["DEVICE NAME", "BD_ADDR", "PROCEDURES"])
        self.table_widget.setFont(bold_font)
        header = self.table_widget.horizontalHeader()
        header.setStyleSheet(styles.horizontal_header_style_sheet)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        vertical_header = self.table_widget.verticalHeader()
        vertical_header.setStyleSheet(styles.vertical_header_style_sheet)
        row = 0
        for device in discovered_devices:
            device_address = device["address"]
            device_name = device["alias"]
            device_path = device["path"]
            self.table_widget.insertRow(row)
            self.table_widget.setItem(row, 0, QTableWidgetItem(device_name))
            self.table_widget.setItem(row, 1, QTableWidgetItem(device_address))
            button_widget = QWidget()
            button_layout = QHBoxLayout()
            button_layout.setContentsMargins(0, 0, 0, 0)
            button_layout.setSpacing(5)
            pair_button = QPushButton("PAIR")
            pair_button.setObjectName("PairButton")
            pair_button.setFont(small_font)
            pair_button.setStyleSheet(styles.color_style_sheet)
            pair_button.clicked.connect(lambda _, addr = device_address: self.perform_device_action('pair', addr, load_profiles=False))
            button_layout.addWidget(pair_button)
            connect_button = QPushButton("CONNECT")
            connect_button.setObjectName("ConnectButton")
            connect_button.setFont(small_font)
            connect_button.setStyleSheet(styles.color_style_sheet)
            connect_button.clicked.connect(lambda _, addr = device_address: self.perform_device_action('connect', addr, load_profiles=False))
            button_layout.addWidget(connect_button)
            button_widget.setLayout(button_layout)
            self.table_widget.setCellWidget(row, 2, button_widget)
            row += 1
        self.profile_methods_layout.insertWidget(self.profile_methods_layout.count() - 1, self.table_widget)
        self.table_widget.show()
        self.set_discovery_off_button.setEnabled(False)

    def clear_device_discovery_results(self):
        """Removes the discovery table if it exists to avoid stacking."""
        if hasattr(self, 'table_widget') and self.table_widget:
            self.profile_methods_layout.removeWidget(self.table_widget)
            self.table_widget.deleteLater()
            self.table_widget = None

    def refresh_discovery_ui(self):
        """Refresh and clear the device discovery table."""
        if hasattr(self, 'table_widget') and self.table_widget:
            self.profile_methods_layout.removeWidget(self.table_widget)
            self.table_widget.deleteLater()
            self.table_widget = None
            self.inquiry_timeout_input.setText("0")
            self.refresh_button.setEnabled(False)
            self.set_discovery_on_button.setEnabled(True)
            self.set_discovery_off_button.setEnabled(False)
            self.refresh_button.setEnabled(True)
        self.log.info("Discovery UI refreshed successfully.")

    def reset_discoverable_timeout(self):
        """Reset discoverable timeout input to default (0)."""
        self.discoverable_timeout_input.setText("0")
        self.log.info("Discoverable timeout reset to 0.")

    def add_paired_device_to_list(self, device_address):
        """Adds a device to the paired devices list if not already present.

        Args:
            device_address: Bluetooth address of remote device.
        """
        for i in range(self.profiles_list_widget.count()):
            if self.profiles_list_widget.item(i).text().strip() == device_address:
                return
        device_item = QListWidgetItem(device_address)
        device_item.setFont(QFont("Courier New", 10))
        device_item.setForeground(Qt.GlobalColor.black)
        self.profiles_list_widget.addItem(device_item)

    def clear_layout(self, layout):
        """Delete all widgets and sub-layouts from a layout.

        Args:
            layout: Qt layout to be cleared.
        """
        if not isinstance(layout, QLayout):
            return
        while layout.count():
            item = layout.takeAt(0)
            if child_layout := item.layout():
                self.clear_layout(child_layout)
            elif widget := item.widget():
                widget.setParent(None)
                widget.deleteLater()

    def handle_profile_selection(self, profile_name=None):
        """Handles profile selection from either the list or a button.

        Args:
            profile_name: Currently selected item from the profiles list widget.
        """
        if profile_name is None:
            selected_item = self.profiles_list_widget.currentItem()
            if not selected_item:
                return
            selected_item_text = selected_item.text().strip()
        else:
            selected_item_text = profile_name.strip()
        self.clear_device_discovery_results()
        self.clear_layout(self.profile_methods_layout)
        if hasattr(self, 'device_tab_widget') and self.device_tab_widget:
            self.device_tab_widget.currentChanged.disconnect(self.handle_profile_tab_change)
            self.profile_methods_layout.removeWidget(self.device_tab_widget)
            self.device_tab_widget.hide()
            self.device_tab_widget.setParent(None)
            self.device_tab_widget.deleteLater()
            self.device_tab_widget = None
        QTimer.singleShot(0, lambda: (self.load_device_profile_tabs(selected_item_text)
        if validate_bluetooth_address(selected_item_text)else
        self.create_gap_profile_ui() if selected_item_text == "GAP"
        else None))

    def create_gap_profile_ui(self):
        """Build and display the widgets for the GAP profile."""
        bold_font = QFont()
        bold_font.setBold(True)
        label = QLabel("SetDiscoverable: ")
        label.setObjectName("SetDiscoverable")
        label.setFont(bold_font)
        label.setStyleSheet(styles.color_style_sheet)
        self.profile_methods_layout.addWidget(label)
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("SetDiscoverable Timeout: ")
        timeout_label.setObjectName("SetDiscoverableTimeout")
        timeout_label.setFont(bold_font)
        timeout_label.setStyleSheet(styles.color_style_sheet)
        self.discoverable_timeout_input = QLineEdit("0")
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.discoverable_timeout_input)
        self.profile_methods_layout.addLayout(timeout_layout)
        buttons_layout = QHBoxLayout()
        self.set_discoverable_on_button = QPushButton("ON")
        self.set_discoverable_on_button.setObjectName("SetDiscoverableOnButton")
        self.set_discoverable_on_button.setStyleSheet(styles.color_style_sheet)
        self.set_discoverable_off_button = QPushButton("OFF")
        self.set_discoverable_off_button.setObjectName("SetDiscoverableOffButton")
        self.set_discoverable_off_button.setStyleSheet(styles.color_style_sheet)
        self.set_discoverable_off_button.setEnabled(False)
        self.set_discoverable_on_button.clicked.connect(lambda: self.set_discoverable_mode(True))
        self.set_discoverable_off_button.clicked.connect(lambda: self.set_discoverable_mode(False))
        buttons_layout.addWidget(self.set_discoverable_on_button)
        buttons_layout.addWidget(self.set_discoverable_off_button)
        self.profile_methods_layout.addLayout(buttons_layout)
        self.refresh_button = QPushButton("REFRESH")
        self.refresh_button.setObjectName("RefreshButton")
        self.refresh_button.setStyleSheet(styles.color_style_sheet)
        self.refresh_button.clicked.connect(self.reset_discoverable_timeout)
        self.profile_methods_layout.addWidget(self.refresh_button)
        inquiry_label = QLabel("Inquiry:")
        inquiry_label.setObjectName("Inquiry")
        inquiry_label.setFont(bold_font)
        inquiry_label.setStyleSheet(styles.color_style_sheet)
        self.profile_methods_layout.addWidget(inquiry_label)
        inquiry_timeout_layout = QHBoxLayout()
        inquiry_timeout_label = QLabel("Inquiry Timeout:")
        inquiry_timeout_label.setObjectName("InquiryTimeoutLabel")
        inquiry_timeout_label.setFont(bold_font)
        inquiry_timeout_label.setStyleSheet(styles.color_style_sheet)
        self.inquiry_timeout_input = QLineEdit("0")
        inquiry_timeout_layout.addWidget(inquiry_timeout_label)
        inquiry_timeout_layout.addWidget(self.inquiry_timeout_input)
        self.profile_methods_layout.addLayout(inquiry_timeout_layout)
        discovery_buttons_layout = QHBoxLayout()
        self.set_discovery_on_button = QPushButton("START")
        self.set_discovery_on_button.setObjectName("SetDiscoveryOnButton")
        self.set_discovery_on_button.setStyleSheet(styles.color_style_sheet)
        self.set_discovery_on_button.clicked.connect(self.start_device_discovery)
        self.set_discovery_off_button = QPushButton("STOP")
        self.set_discovery_off_button.setObjectName("SetDiscoveryOffButton")
        self.set_discovery_off_button.setStyleSheet(styles.color_style_sheet)
        self.set_discovery_off_button.clicked.connect(self.stop_device_discovery)
        self.set_discovery_off_button.setEnabled(False)
        discovery_buttons_layout.addWidget(self.set_discovery_on_button)
        discovery_buttons_layout.addWidget(self.set_discovery_off_button)
        self.profile_methods_layout.addLayout(discovery_buttons_layout)
        capability_label = QLabel("Select Capability: ")
        capability_label.setFont(bold_font)
        self.capability_combobox = QComboBox()
        self.capability_combobox.setFont(QFont("Arial", 10))
        self.capability_combobox.addItems(["DisplayOnly", "DisplayYesNo", "KeyboardOnly", "NoInputNoOutput", "KeyboardDisplay"])
        self.capability_combobox.setCurrentText("NoInputNoOutput")
        register_agent_button = QPushButton("Register Agent")
        register_agent_button.setObjectName("RegisterAgent")
        register_agent_button.setFont(bold_font)
        register_agent_button.setStyleSheet(styles.color_style_sheet)
        register_agent_button.clicked.connect(self.register_agent)
        self.profile_methods_layout.addWidget(capability_label)
        self.profile_methods_layout.addWidget(self.capability_combobox)
        self.profile_methods_layout.addWidget(register_agent_button)
        unregister_agent_button = QPushButton("Unregister Agent")
        unregister_agent_button.setObjectName("UnregisterAgent")
        unregister_agent_button.setFont(bold_font)
        unregister_agent_button.setStyleSheet(styles.color_style_sheet)
        unregister_agent_button.clicked.connect(self.unregister_agent)
        self.profile_methods_layout.addWidget(unregister_agent_button)
        discovery_ui_refresh_button = QPushButton("REFRESH")
        discovery_ui_refresh_button.setObjectName("RefreshButton")
        discovery_ui_refresh_button.setStyleSheet(styles.color_style_sheet)
        discovery_ui_refresh_button.clicked.connect(self.refresh_discovery_ui)
        self.profile_methods_layout.addWidget(discovery_ui_refresh_button)
        self.profile_methods_layout.addStretch(1)

    def create_a2dp_profile_ui(self, device_address):
        """Builds a single A2DP panel combining source streaming and sink media control, based on the device's A2DP roles.

        Args:
            device_address: Bluetooth address of the remote device.
        """
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        a2dp_label = QLabel("<b>A2DP Functionality</b>")
        a2dp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        a2dp_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(a2dp_label)
        is_connected = self.bluetooth_device_manager.is_device_connected(device_address)
        if not is_connected:
            warning_label = QLabel("Device is not connected. Connect to enable A2DP profile.")
            warning_label.setObjectName("WarningLabel")
            warning_label.setFont(bold_font)
            warning_label.setStyleSheet(styles.color_style_sheet)
            layout.addWidget(warning_label)
            layout.addStretch(1)
            widget = QWidget()
            widget.setLayout(layout)
            return widget
        self.device_address_source = device_address
        self.device_address_sink = device_address
        role = self.bluetooth_device_manager.get_a2dp_role_for_device(device_address)
        if role == "sink":
            streaming_group = QGroupBox("Streaming Audio (A2DP Source)")
            streaming_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            streaming_layout = QVBoxLayout()
            streaming_layout.setSpacing(10)
            streaming_layout.setContentsMargins(10, 10, 10, 10)
            audio_layout = QHBoxLayout()
            audio_label = QLabel("Audio File:")
            audio_label.setFont(bold_font)
            audio_layout.addWidget(audio_label)
            self.audio_location_input = QLineEdit()
            self.audio_location_input.setReadOnly(True)
            self.audio_location_input.setFixedHeight(28)
            audio_layout.addWidget(self.audio_location_input)
            self.browse_audio_button = QPushButton("Browse")
            self.browse_audio_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.browse_audio_button.clicked.connect(self.select_audio_file)
            audio_layout.addWidget(self.browse_audio_button)
            streaming_layout.addLayout(audio_layout)
            streaming_buttons_layout = QHBoxLayout()
            streaming_buttons_layout.setSpacing(12)
            self.start_streaming_button = QPushButton("Start Streaming")
            self.start_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.start_streaming_button.clicked.connect(self.start_a2dp_streaming)
            streaming_buttons_layout.addWidget(self.start_streaming_button)
            self.stop_streaming_button = QPushButton("Stop Streaming")
            self.stop_streaming_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.stop_streaming_button.clicked.connect(self.stop_a2dp_streaming)
            self.stop_streaming_button.setEnabled(False)
            streaming_buttons_layout.addWidget(self.stop_streaming_button)
            streaming_layout.addLayout(streaming_buttons_layout)
            streaming_group.setLayout(streaming_layout)
            layout.addWidget(streaming_group)
        elif role == "source":
            media_control_group = QGroupBox("Media Control (A2DP Sink)")
            media_control_group.setFont(bold_font)
            media_control_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
            media_control_layout = QVBoxLayout()
            media_control_layout.setSpacing(12)
            media_control_layout.setContentsMargins(10, 10, 10, 10)
            control_buttons = QHBoxLayout()
            control_buttons.setSpacing(12)
            self.play_button = QPushButton("Play")
            self.play_button.setFont(bold_font)
            self.play_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.play_button.clicked.connect(lambda: self.send_media_control_command("play"))
            control_buttons.addWidget(self.play_button)
            self.pause_button = QPushButton("Pause")
            self.pause_button.setFont(bold_font)
            self.pause_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.pause_button.clicked.connect(lambda: self.send_media_control_command("pause"))
            control_buttons.addWidget(self.pause_button)
            self.next_button = QPushButton("Next")
            self.next_button.setFont(bold_font)
            self.next_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.next_button.clicked.connect(lambda: self.send_media_control_command("next"))
            control_buttons.addWidget(self.next_button)
            self.previous_button = QPushButton("Previous")
            self.previous_button.setFont(bold_font)
            self.previous_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.previous_button.clicked.connect(lambda: self.send_media_control_command("previous"))
            control_buttons.addWidget(self.previous_button)
            self.rewind_button = QPushButton("Rewind")
            self.rewind_button.setFont(bold_font)
            self.rewind_button.setStyleSheet(styles.bluetooth_profiles_button_style)
            self.rewind_button.clicked.connect(lambda: self.send_media_control_command("rewind"))
            control_buttons.addWidget(self.rewind_button)
            media_control_layout.addLayout(control_buttons)
            media_control_group.setLayout(media_control_layout)
            layout.addWidget(media_control_group)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def create_opp_profile_ui(self, device_address):
        """Builds and returns the OPP (Object Push Profile) panel for Bluetooth file transfer.

        Args:
            device_address: Bluetooth address of the remote device.
        """
        bold_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        opp_label = QLabel("<b>OPP Functionality</b>")
        opp_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        opp_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(opp_label)
        is_connected = self.bluetooth_device_manager.is_device_connected(device_address)
        if not is_connected:
            warning_label = QLabel("Device is not connected. Connect to enable OPP profile.")
            warning_label.setObjectName("WarningLabel")
            warning_label.setFont(bold_font)
            warning_label.setStyleSheet(styles.color_style_sheet)
            layout.addWidget(warning_label)
            layout.addStretch(1)
            widget = QWidget()
            widget.setLayout(layout)
            widget.setStyleSheet(styles.device_tab_widget_style_sheet)
            return widget
        opp_group = QGroupBox("File Transfer")
        opp_group.setStyleSheet(styles.bluetooth_profiles_groupbox_style)
        opp_layout = QVBoxLayout()
        opp_layout.setSpacing(10)
        opp_layout.setContentsMargins(10, 10, 10, 10)
        file_selection_layout = QHBoxLayout()
        file_label = QLabel("Select File:")
        file_label.setFont(bold_font)
        file_selection_layout.addWidget(file_label)
        self.opp_location_input = QLineEdit()
        self.opp_location_input.setReadOnly(True)
        self.opp_location_input.setFixedHeight(28)
        file_selection_layout.addWidget(self.opp_location_input)
        self.browse_opp_button = QPushButton("Browse")
        self.browse_opp_button.setFont(bold_font)
        self.browse_opp_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.browse_opp_button.clicked.connect(self.select_opp_file)
        file_selection_layout.addWidget(self.browse_opp_button)
        opp_layout.addLayout(file_selection_layout)
        button_layout = QHBoxLayout()
        self.send_file_button = QPushButton("Send File")
        self.send_file_button.setFont(bold_font)
        self.send_file_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.send_file_button.clicked.connect(self.send_file)
        button_layout.addWidget(self.send_file_button)
        self.receive_file_button = QPushButton("Receive File")
        self.receive_file_button.setFont(bold_font)
        self.receive_file_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.receive_file_button.clicked.connect(self.receive_file)
        button_layout.addWidget(self.receive_file_button)
        opp_layout.addLayout(button_layout)
        opp_group.setLayout(opp_layout)
        layout.addWidget(opp_group)
        layout.addStretch(1)
        widget = QWidget()
        widget.setLayout(layout)
        return widget

    def send_media_control_command(self, command):
        """Sends a media control command to the connected Bluetooth device.

        Args:
            command: The media control command to send (e.g., "play", "pause", "next", "previous").
        """
        self.bluetooth_device_manager.media_control(command, address=self.device_address_sink)
        self.log.info("Media command %s sent to device %s.", command, self.device_address_sink)

    def start_a2dp_streaming(self):
        """Start A2DP streaming to a selected Bluetooth sink device."""
        audio_path = self.audio_location_input.text().strip()
        if not audio_path or not os.path.exists(audio_path):
            QMessageBox.warning(self, "Invalid Audio File", "Please select a valid audio file to stream.")
            return
        self.log.info("Selected device address for streaming:%s", self.device_address_source)
        if not self.device_address_source:
            QMessageBox.warning(self, "No Device", "Please select a Bluetooth sink device to stream.")
            return
        self.start_streaming_button.setEnabled(False)
        self.stop_streaming_button.setEnabled(True)
        status = self.bluetooth_device_manager.start_a2dp_stream(self.device_address_source, audio_path)
        if status:
            self.log.info("A2DP streaming successfully started with file: %s", audio_path)
        else:
            self.log.error("Failed to start A2DP streaming with file: %s", audio_path)
            QMessageBox.critical(self, "Streaming Failed", "Failed to start streaming.")
            self.start_streaming_button.setEnabled(True)
            self.stop_streaming_button.setEnabled(False)

    def stop_a2dp_streaming(self):
        """Stop active A2DP streaming session."""
        try:
            self.bluetooth_device_manager.stop_a2dp_stream()
        except Exception as error:
            self.log.error("Failed to stop A2DP streaming for device: %s. Error: %s", self.device_address_source, error)
            QMessageBox.critical(self, "Stop Streaming Failed", "Failed to stop A2DP streaming.")
            return
        self.log.info("A2DP streaming stopped for device: %s", self.device_address_source)
        self.start_streaming_button.setEnabled(True)
        self.stop_streaming_button.setEnabled(False)

    def select_audio_file(self):
        """Open a file dialog for selecting an audio file."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(caption="Select Audio File", filter="WAV files (*.wav)")
        if file_path:
            if os.path.exists(file_path) and file_path.lower().endswith('.wav'):
                self.audio_location_input.setText(file_path)
                self.log.info("Audio file selected.")
            else:
                self.log.warning(f"Selected file is invalid or not a WAV file: {file_path}")
                QMessageBox.warning(self, "Invalid File", "The selected file does not exist or is not a valid WAV file.")

    def select_opp_file(self):
        """Open a file dialog to select a file to send via OPP."""
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(None, "Select File to Send via OPP", "", "All Files (*)")
        if file_path:
            if not os.path.exists(file_path):
                QMessageBox.critical(None, "Invalid File", "The selected file does not exist.")
                self.log.error("Selected OPP file does not exist: %s", file_path)
                return
            self.opp_location_input.setText(file_path)
            self.log.info("File selected to send via OPP")

    def send_file(self):
        """Send a selected file to a remote device using OPP."""
        file_path = self.opp_location_input.text()
        if not file_path or not self.device_address:
            QMessageBox.warning(None, "OPP", "Please select a device and a file.")
            return
        self.send_file_button.setEnabled(False)
        self.send_file_button.setText("Sending...")
        try:
            status = self.bluetooth_device_manager.send_file(self.device_address, file_path, profile="opp")
        except Exception as error:
            status = "error"
            self.log.info("UI error:%s", error)
        self.send_file_button.setEnabled(True)
        self.send_file_button.setText("Send File")
        if status == "complete":
            QMessageBox.information(None, "OPP", "File sent successfully!")
        elif status == "queued":
            QMessageBox.information(None, "OPP", "File transfer is queued. Please wait...")
        elif status == "unknown":
            QMessageBox.warning(None, "OPP", "File transfer status is unknown.")
        else:
            QMessageBox.warning(None, "OPP", "File transfer failed or was rejected.")

    def receive_file(self):
        """Start OPP receiver and handle file transfer."""
        try:
            received_file_path = self.bluetooth_device_manager.receive_file(user_confirm_callback=self.prompt_file_transfer_confirmation)
            if received_file_path:
                QMessageBox.information(None, "File Received", f"File received successfully:\n{received_file_path}")
            else:
                QMessageBox.warning(None, "File Transfer", "No file received or user declined the transfer.")
        except Exception as error:
            QMessageBox.critical(None, "Error", f"An error occurred during file reception:\n{str(error)}")

    def handle_profile_tab_change(self, index):
        """Handles actions to perform when the user switches between profile tabs in the UI.

        Args:
            index: The index of the newly selected tab in the profile tab widget.
        """
        if not hasattr(self, 'device_tab_widget') or index < 0:
            return
        selected_tab = self.device_tab_widget.tabText(index)
        if selected_tab == "A2DP":
            self.clear_layout(self.a2dp_tab_placeholder)
            layout = QVBoxLayout()
            a2dp_panel = self.create_a2dp_profile_ui(self.device_address)
            self.log.info(self.device_address)
            layout.addWidget(a2dp_panel)
            self.a2dp_tab_placeholder.setLayout(layout)
            self.a2dp_tab_placeholder.update()
        elif selected_tab == "OPP":
            self.clear_layout(self.opp_tab_placeholder)
            layout = QVBoxLayout()
            opp_tab = self.create_opp_profile_ui(self.device_address)
            layout.addWidget(opp_tab)
            self.opp_tab_placeholder.setLayout(layout)
            self.opp_tab_placeholder.update()

    def load_device_profile_tabs(self, device_address):
        """Loads and displays profile-related UI tabs for a specific Bluetooth device.

        Args:
            device_address: Bluetooth address of the remote device.
        """
        bold_font = QFont()
        bold_font.setBold(True)
        is_connected = self.bluetooth_device_manager.is_device_connected(device_address)
        self.device_address = device_address
        if not is_connected:
            warning_label = QLabel("Device is not connected. Connect to enable profile controls.")
            warning_label.setObjectName("WarningLabel")
            warning_label.setFont(bold_font)
            warning_label.setStyleSheet(styles.color_style_sheet)
            self.clear_layout(self.profile_methods_layout)
            self.profile_methods_layout.addWidget(warning_label)
            self.add_device_connection_controls(self.profile_methods_layout, device_address)
            return
        self.device_tab_widget = QTabWidget()
        self.device_tab_widget.setMaximumWidth(600)
        self.device_tab_widget.setFont(bold_font)
        self.device_tab_widget.setStyleSheet(styles.device_tab_widget_style_sheet)
        self.a2dp_tab_placeholder = QWidget()
        self.a2dp_tab_placeholder.setMaximumWidth(600)
        self.opp_tab_placeholder = QWidget()
        self.opp_tab_placeholder.setMaximumWidth(600)
        self.device_tab_widget.addTab(self.a2dp_tab_placeholder, "A2DP")
        self.device_tab_widget.addTab(self.opp_tab_placeholder, "OPP")
        self.device_tab_widget.currentChanged.connect(self.handle_profile_tab_change)
        self.clear_layout(self.profile_methods_layout)
        self.profile_methods_layout.addWidget(self.device_tab_widget)
        self.handle_profile_tab_change(self.device_tab_widget.currentIndex())
        self.add_device_connection_controls(self.profile_methods_layout, device_address)

    def add_device_connection_controls(self, layout, device_address):
        """Adds Connect, Disconnect, and Unpair buttons to the provided layout for the specified device.

        Args:
            layout: The layout to which the control buttons will be added.
            device_address: The Bluetooth address of the device the controls apply to.
        """
        bold_font = QFont()
        bold_font.setBold(True)
        button_layout = QHBoxLayout()
        self.is_connected = self.bluetooth_device_manager.is_device_connected(device_address)
        self.is_paired = device_address in self.bluetooth_device_manager.get_paired_devices()
        self.connect_button = QPushButton("Connect")
        self.connect_button.setFont(bold_font)
        self.connect_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.connect_button.setFixedWidth(100)
        self.connect_button.setEnabled(not self.is_connected)
        self.connect_button.clicked.connect(lambda: self.perform_device_action('connect', device_address, load_profiles=True))
        button_layout.addWidget(self.connect_button)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.setFont(bold_font)
        self.disconnect_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.disconnect_button.setFixedWidth(100)
        self.disconnect_button.setEnabled(self.is_connected)
        self.disconnect_button.clicked.connect(lambda: self.perform_device_action('disconnect', device_address, load_profiles=True))
        button_layout.addWidget(self.disconnect_button)
        self.unpair_button = QPushButton("Unpair")
        self.unpair_button.setFont(bold_font)
        self.unpair_button.setStyleSheet(styles.bluetooth_profiles_button_style)
        self.unpair_button.setFixedWidth(100)
        self.unpair_button.setEnabled(True)
        self.unpair_button.clicked.connect(lambda: self.perform_device_action('unpair', device_address, load_profiles=True))
        button_layout.addWidget(self.unpair_button)
        layout.addLayout(button_layout)

    def perform_device_action(self, action, device_address, load_profiles):
        """Perform a Bluetooth device action (connect, disconnect, pair, unpair) and handle the response.

        Args:
            action: The action to perform. Expected values: "connect", "disconnect", "pair", "unpair".
            device_address: The bluetooth address of the remote device.
            load_profiles: Indicates whether to load device profiles after a successful connect.
        """
        device_action =constants.device_action_map.get(action)
        if not device_action:
            self.log.error("Unknown action: %s", action)
            return
        method_name, response_handler = device_action
        method = getattr(self.bluetooth_device_manager, method_name)
        result = method(device_address)
        self.log.info("Performing %s on %s", method_name, device_address)
        if result:
            self.log.info(f"{device_address}: Device {action} successful.")
        else:
            self.log.info(f"{device_address}: Device {action} failed.")
        response_handler = getattr(self, response_handler)
        if action == "connect" and load_profiles:
            response_handler(device_address)
        elif action=="disconnect" or action=="unpair":
            response_handler(device_address)
        elif action=="pair" and self.bluetooth_device_manager.is_device_paired(device_address):
            response_handler(device_address)

    def remove_device_from_list(self, unpaired_device_address):
        """Removes a specific unpaired device from the profiles list (if present).

        Args:
            unpaired_device_address: Bluetooth address of the unpaired device.
        """
        for i in range(self.profiles_list_widget.count()):
            item_text = self.profiles_list_widget.item(i).text().strip()
            if item_text == unpaired_device_address:
                self.profiles_list_widget.takeItem(i)
                break

    def register_agent(self):
        """Register bluetooth pairing agent"""
        self.selected_capability = self.capability_combobox.currentText()
        self.log.info("Attempting to register agent with capability:%s", self.selected_capability)
        try:
            self.bluetooth_device_manager.register_agent(capability=self.selected_capability, ui_callback = self.handle_pairing_request)
            QMessageBox.information(self, "Agent Registered", f"Agent registered with capability: {self.selected_capability}")
        except Exception as error:
            self.log.info("Failed to register agent:%s", error)
            QMessageBox.critical(self, "Registration Failed", f"Could not register agent.\n{error}")

    def initialize_host_ui(self):
        """Create and display the main application GUI."""
        self.main_grid_layout = QGridLayout()
        bold_font = QFont()
        bold_font.setBold(True)
        # Grid 1: GAP button,Paired_devices, Controller details
        self.gap_button = QPushButton("GAP")
        self.gap_button.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.gap_button.setStyleSheet(styles.gap_button_style_sheet)
        self.gap_button.setFixedWidth(350)
        self.gap_button.setMinimumHeight(30)
        self.gap_button.clicked.connect(lambda: self.handle_profile_selection("GAP "))
        self.main_grid_layout.addWidget(self.gap_button, 0, 0, 1, 2)
        self.profiles_list_widget = QListWidget()
        self.profiles_list_widget.setFont(bold_font)
        self.profiles_list_widget.setContentsMargins(4, 4, 4, 4)
        self.profiles_list_widget.setStyleSheet(styles.profiles_list_style_sheet)
        self.profiles_list_widget.setFixedWidth(350)
        self.profiles_list_widget.itemSelectionChanged.connect(lambda: self.handle_profile_selection())
        paired_devices_label = QLabel("Paired Devices")
        paired_devices_label.setObjectName("PairedDevicesList")
        paired_devices_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        paired_devices_label.setStyleSheet(styles.color_style_sheet)
        paired_devices_layout = QVBoxLayout()
        paired_devices_layout.setContentsMargins(8, 8, 8, 8)
        paired_devices_layout.setSpacing(6)
        paired_devices_layout.addWidget(paired_devices_label)
        paired_devices_layout.addWidget(self.profiles_list_widget)
        paired_devices_widget = QWidget()
        paired_devices_widget.setLayout(paired_devices_layout)
        paired_devices_widget.setFixedWidth(350)
        paired_devices_widget.setStyleSheet(styles.panel_style_sheet)
        self.main_grid_layout.addWidget(paired_devices_widget, 1, 0, 4, 2)
        controller_details_widget = QWidget()
        controller_layout = QVBoxLayout(controller_details_widget)
        controller_details_widget.setFixedWidth(350)
        controller_details_widget.setStyleSheet(styles.panel_style_sheet)
        controller_label = QLabel("Controller Details")
        controller_label.setObjectName("ControllerDetails")
        controller_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        controller_label.setStyleSheet(styles.color_style_sheet)
        controller_layout.addWidget(controller_label)
        details = get_controller_interface_details(self.log, interface=self.interface, detail_level='extended_info')
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(10)
        self.grid.setVerticalSpacing(12)
        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 2)
        self.add_controller_details_row(0, "Controller Name", details.get("Name", "N/A"))
        self.add_controller_details_row(1, "Controller Address", details.get("BD_ADDR", "N/A"))
        self.add_controller_details_row(2, "Link Mode", details.get("Link mode", "N/A"))
        self.add_controller_details_row(3, "Link Policy", details.get("Link policy", "N/A"))
        self.add_controller_details_row(4, "HCI Version", details.get("HCI Version", "N/A"))
        self.add_controller_details_row(5, "LMP Version", details.get("LMP Version", "N/A"))
        self.add_controller_details_row(6, "Manufacturer", details.get("Manufacturer", "N/A"))
        controller_layout.addLayout(self.grid)
        self.main_grid_layout.addWidget(controller_details_widget, 5, 0, 8, 2)
        # Grid2: Profile description
        profile_description_label = QLabel("Profile Methods or Procedures:")
        profile_description_label.setObjectName("profile_description_label")
        profile_description_label.setFont(bold_font)
        profile_description_label.setStyleSheet(styles.color_style_sheet)
        self.main_grid_layout.addWidget(profile_description_label, 0, 2)
        self.profile_methods_layout = QVBoxLayout()
        self.profile_methods_widget = QWidget()
        self.profile_methods_widget.setObjectName("ProfileContainer")
        self.profile_methods_widget.setStyleSheet(styles.middle_panel_style_sheet)
        self.profile_methods_widget.setMinimumWidth(350)
        self.profile_methods_widget.setMaximumWidth(500)
        self.profile_methods_widget.setLayout(self.profile_methods_layout)
        self.main_grid_layout.addWidget(self.profile_methods_widget, 1, 2, 12, 2)
        back_button = QPushButton("Back")
        back_button.setFixedSize(100, 40)
        back_button.setStyleSheet(styles.back_button_style_sheet)
        back_button.clicked.connect(lambda: self.back_callback())
        back_layout = QHBoxLayout()
        back_layout.addWidget(back_button)
        back_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_grid_layout.addLayout(back_layout, 999, 5)
        self.main_grid_layout.setColumnStretch(0, 0)
        self.main_grid_layout.setColumnStretch(1, 0)
        self.main_grid_layout.setColumnStretch(2, 1)
        self.setLayout(self.main_grid_layout)
        self.load_paired_devices()
        self.setup_dump_logs_section()

    def setup_dump_logs_section(self):
        """Initializes the dump logs tab section with log viewers for Bluetoothd, Pulseaudio, HCI Dump, Obexd, and Ofonod."""
        bold_font = QFont()
        bold_font.setBold(True)
        dump_logs_label = QLabel("Dump Logs:")
        dump_logs_label.setFont(bold_font)
        dump_logs_label.setStyleSheet(styles.color_style_sheet)
        self.main_grid_layout.addWidget(dump_logs_label, 0, 4)
        self.dump_logs_text_browser = QTabWidget()
        self.dump_logs_text_browser.setFixedWidth(400)
        self.dump_logs_text_browser.setStyleSheet(styles.tab_style_sheet)
        self.dump_logs_text_browser.setUsesScrollButtons(True)
        self.main_grid_layout.addWidget(self.dump_logs_text_browser, 1, 4, 12, 2)
        self.setup_bluetoothd_log()
        self.setup_pulseaudio_log()
        self.setup_hcidump_log()
        self.setup_obexd_log()
        self.setup_ofonod_log()

    def setup_bluetoothd_log(self):
        """Sets up the Bluetoothd log viewer tab and connects it to the log file for live updates."""
        normal_font = QFont()
        normal_font.setBold(False)
        self.bluetoothd_log_text_browser = QTextEdit()
        self.bluetoothd_log_text_browser.setFont(normal_font)
        self.bluetoothd_log_text_browser.setMinimumWidth(50)
        self.bluetoothd_log_text_browser.setReadOnly(True)
        self.bluetoothd_log_text_browser.setStyleSheet(styles.transparent_textedit_style)
        self.dump_logs_text_browser.addTab(self.bluetoothd_log_text_browser, "Bluetoothd_Logs")
        self.bluetoothd_log_file_fd = open(self.bluetoothd_log_file_path, "r")
        if self.bluetoothd_log_file_fd:
            content = self.bluetoothd_log_file_fd.read()
            self.bluetoothd_log_text_browser.append(content)
            self.bluetoothd_file_position = self.bluetoothd_log_file_fd.tell()
        self.bluetoothd_file_watcher = QFileSystemWatcher()
        self.bluetoothd_file_watcher.addPath(self.bluetoothd_log_file_path)
        self.bluetoothd_file_watcher.fileChanged.connect(self.update_bluetoothd_log)

    def setup_pulseaudio_log(self):
        """Sets up the Pulseaudio log viewer tab and connects it to the log file for live updates."""
        normal_font = QFont()
        normal_font.setBold(False)
        self.pulseaudio_log_text_browser = QTextEdit()
        self.pulseaudio_log_text_browser.setFont(normal_font)
        self.pulseaudio_log_text_browser.setMinimumWidth(50)
        self.pulseaudio_log_text_browser.setReadOnly(True)
        self.pulseaudio_log_text_browser.setStyleSheet(styles.transparent_textedit_style)
        self.dump_logs_text_browser.addTab(self.pulseaudio_log_text_browser, "Pulseaudio_Logs")
        self.pulseaudio_log_file_fd = open(self.pulseaudio_log_file_path, "r")
        if self.pulseaudio_log_file_fd:
            content = self.pulseaudio_log_file_fd.read()
            self.pulseaudio_log_text_browser.append(content)
            self.pulseaudio_file_position = self.pulseaudio_log_file_fd.tell()
        self.pulseaudio_file_watcher = QFileSystemWatcher()
        self.pulseaudio_file_watcher.addPath(self.pulseaudio_log_file_path)
        self.pulseaudio_file_watcher.fileChanged.connect(self.update_pulseaudio_log)

    def setup_hcidump_log(self):
        """Sets up the Hcidump log viewer tab and connects it to the log file for live updates."""
        normal_font = QFont()
        normal_font.setBold(False)
        self.hci_dump_log_text_browser = QTextEdit()
        self.hci_dump_log_text_browser.setFont(normal_font)
        self.hci_dump_log_text_browser.setMinimumWidth(50)
        self.hci_dump_log_text_browser.setReadOnly(True)
        self.hci_dump_log_text_browser.setStyleSheet(styles.transparent_textedit_style)
        self.dump_logs_text_browser.addTab(self.hci_dump_log_text_browser, "HCI_Dump_Logs")
        self.hci_log_file_fd = open(self.hcidump_log_name, "r")
        if self.hci_log_file_fd:
            content = self.hci_log_file_fd.read()
            self.hci_dump_log_text_browser.append(content)
            self.hci_file_position = self.hci_log_file_fd.tell()
        self.hci_file_watcher = QFileSystemWatcher()
        self.hci_file_watcher.addPath(self.hcidump_log_name)
        self.hci_file_watcher.fileChanged.connect(self.update_hci_log)

    def setup_obexd_log(self):
        """Sets up the Obexd log viewer tab and connects it to the log file for live updates."""
        normal_font = QFont()
        normal_font.setBold(False)
        self.obexd_log_text_browser = QTextEdit()
        self.obexd_log_text_browser.setFont(normal_font)
        self.obexd_log_text_browser.setMinimumWidth(50)
        self.obexd_log_text_browser.setReadOnly(True)
        self.obexd_log_text_browser.setStyleSheet(styles.transparent_textedit_style)
        self.dump_logs_text_browser.addTab(self.obexd_log_text_browser, "Obexd_Logs")
        self.obexd_log_file_fd = open(self.obexd_log_file_path, "r")
        if self.obexd_log_file_fd:
            content = self.obexd_log_file_fd.read()
            self.obexd_log_text_browser.append(content)
            self.obexd_file_position = self.obexd_log_file_fd.tell()
        self.obexd_file_watcher = QFileSystemWatcher()
        self.obexd_file_watcher.addPath(self.obexd_log_file_path)
        self.obexd_file_watcher.fileChanged.connect(self.update_obexd_log)

    def setup_ofonod_log(self):
        """Sets up the Ofonod log viewer tab and connects it to the log file for live updates."""
        normal_font = QFont()
        normal_font.setBold(False)
        self.ofonod_log_text_browser = QTextEdit()
        self.ofonod_log_text_browser.setFont(normal_font)
        self.ofonod_log_text_browser.setMinimumWidth(50)
        self.ofonod_log_text_browser.setReadOnly(True)
        self.ofonod_log_text_browser.setStyleSheet(styles.transparent_textedit_style)
        self.dump_logs_text_browser.addTab(self.ofonod_log_text_browser, "Ofonod_Logs")
        self.ofonod_log_file_fd = open(self.ofonod_log_file_path, "r")
        if self.ofonod_log_file_fd:
            content = self.ofonod_log_file_fd.read()
            self.ofonod_log_text_browser.append(content)
            self.ofonod_file_position = self.ofonod_log_file_fd.tell()
        self.ofonod_file_watcher = QFileSystemWatcher()
        self.ofonod_file_watcher.addPath(self.ofonod_log_file_path)
        self.ofonod_file_watcher.fileChanged.connect(self.update_ofonod_log)

    def update_bluetoothd_log(self):
        """Updates the bluetoothd log display with new log entries.
        Reads the bluetoothd log file from the last known position and appends the new content to bluetoothd
        log text browser."""
        if self.bluetoothd_log_file_fd:
            self.bluetoothd_log_file_fd.seek(self.bluetoothd_file_position)
            content = self.bluetoothd_log_file_fd.read()
            self.bluetoothd_file_position = self.bluetoothd_log_file_fd.tell()
            self.bluetoothd_log_text_browser.append(content)

    def update_pulseaudio_log(self):
        """Updates the pulseaudio log display with new log entries.
        Reads the pulseaudio log file from the last known position and appends the new content to pulseaudio
        log text browser."""
        if self.pulseaudio_log_file_fd:
            self.pulseaudio_log_file_fd.seek(self.pulseaudio_file_position)
            content = self.pulseaudio_log_file_fd.read()
            self.pulseaudio_file_position = self.pulseaudio_log_file_fd.tell()
            self.pulseaudio_log_text_browser.append(content)

    def update_hci_log(self):
        """Updates the hcidump log display with new log entries.
        Reads the hci log file from the last known position and appends the new content to hci dump
        log text browser."""
        if self.hci_log_file_fd:
            self.hci_log_file_fd.seek(self.hci_file_position)
            content = self.hci_log_file_fd.read()
            self.hci_file_position = self.hci_log_file_fd.tell()
            self.hci_dump_log_text_browser.append(content)

    def update_obexd_log(self):
        """Updates the obexd log display with new log entries.
        Reads the obexd log file from the last known position and appends the new content to obexd
        log text browser."""
        if self.obexd_log_file_fd:
            self.obexd_log_file_fd.seek(self.obexd_file_position)
            content = self.obexd_log_file_fd.read()
            self.obexd_file_position = self.obexd_log_file_fd.tell()
            self.obexd_log_text_browser.append(content)

    def update_ofonod_log(self):
        """Updates the ofonod log display with new log entries.
        Reads the ofonod log file from the last known position and appends the new content to ofonod
        log text browser."""
        if self.ofonod_log_file_fd:
            self.ofonod_log_file_fd.seek(self.ofonod_file_position)
            content = self.ofonod_log_file_fd.read()
            self.ofonod_file_position = self.ofonod_log_file_fd.tell()
            self.ofonod_log_text_browser.append(content)

    def prompt_file_transfer_confirmation(self, file_path):
        """Prompt user to confirm a file transfer and return their decision.

        Args:
            file_path: The full path of the incoming file.
        """
        file_name = os.path.basename(file_path)
        msg_box = QMessageBox()
        msg_box.setWindowTitle("Incoming File")
        msg_box.setText(f"Accept incoming file?\n\n{file_name}")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setIcon(QMessageBox.Icon.Question)
        result = msg_box.exec()
        return result == QMessageBox.StandardButton.Yes

    def unregister_agent(self):
        """Unregister bluetooth pairing agent."""
        self.log.info("Attempting to unregister the Bluetooth agent...")
        try:
            self.bluetooth_device_manager.unregister_agent()
            QMessageBox.information(self, "Agent Unregistered", "Bluetooth agent was successfully unregistered.")
        except Exception as error:
            self.log.error("Failed to unregister agent: %s", error)
            QMessageBox.critical(self, "Unregistration Failed", f"Could not unregister agent.")

    def handle_pairing_request(self, request_type, device, uuid=None, passkey=None):
        """Handle various incoming Bluetooth pairing requests and user interactions.

        Args:
            request_type: The type of pairing request.
            device: The D-Bus object path of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.

        Returns:
            PIN , Passkey, True, or None based on request type and user interaction.
        """
        self.log.info(f"Handling pairing request: {request_type} for {device}")
        device_address = device.split("dev_")[-1].replace("_", ":")
        #if self.selected_capability == "NoInputNoOutput" and self.bluetooth_device_manager.is_device_paired(device_address):
          #  self.add_paired_device_to_list(device_address)
          #  self.log.info("Pairing successful with %s", device_address)
        handler_name = constants.pairing_request_handlers.get(request_type)
        if not handler_name:
            self.log.warning(f"Unknown pairing request type: {request_type}")
            return None
        handler = getattr(self, handler_name)
        return handler(device_address, uuid, passkey)

    def handle_pin_request(self, device_address, uuid=None, passkey=None):
        """Handle PIN code input from the user for pairing.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.

        Returns:
             PIN entered by the user.
        """
        pin, user_response = QInputDialog.getText(self, "Pairing Request", f"Enter PIN for device {device_address}:")
        if user_response and pin:
            return pin
        self.log.info("User cancelled or provided no PIN for device %s", device_address)

    def handle_passkey_request(self, device_address, uuid=None, passkey=None):
        """Handle passkey input from the user for pairing.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.

        Returns:
            passkey_value: The passkey entered by the user, or False if cancelled.
        """
        passkey_value, user_response = QInputDialog.getInt(self, "Pairing Request", f"Enter passkey for device {device_address}:")
        if not user_response:
            self.log.info("User cancelled passkey input for device %s", device_address)
            return False
        #QMessageBox.information(self, "Pairing Successful", f"{device_address} was paired.")
        #self.add_paired_device_to_list(device_address)
        return passkey_value

    def handle_confirm_request(self, device_address, uuid=None, passkey=None):
        """Handle passkey confirmation dialog for pairing.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.

        Returns:
            True if user confirms, False otherwise.
        """
        reply = QMessageBox.question(self, "Confirm Pairing", f"Device {device_address} requests to pair with passkey: {uuid}\nAccept?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            #QMessageBox.information(self, "Pairing Successful", f"{device_address} was paired.")
            #self.add_paired_device_to_list(device_address)
            return True
        QMessageBox.information(self, "Pairing Failed", f"Pairing with {device_address} failed.")
        self.log.info("User rejected pairing confirmation request")
        return False

    def handle_authorize_request(self, device_address, uuid=None, passkey=None):
        """Handle authorization request for allowing a Bluetooth service.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.

        Returns:
            True if user authorizes, False if denied.
        """
        reply = QMessageBox.question(self, "Authorize Service",
            f"Device {device_address} wants to use service {uuid}\nAllow?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            QMessageBox.information(self, "Connection Successful", f"{device_address} was connected.")
            return True
        self.log.warning("User denied service authorization for device %s", device_address)
        return False

    def display_pin_or_passkey(self, device_address, value, label):
        """Display a PIN or passkey to the user for manual entry on the Bluetooth device.

        Args:
            device_address: The address of the Bluetooth device.
            value: The PIN or passkey value to display.
            label: The label to display ('PIN' or 'Passkey').
        """
        if value is None:
            self.log.warning(f"{label} requested but no value provided for device {device_address}.")
            return
        QMessageBox.information(self, f"Display {label}", f"Enter this {label.lower()} on {device_address}: {value}")

        QMessageBox.information(self, f"Display {label}", f"Enter this {label.lower()} on {device_address}: {value}")

    def handle_display_pin_request(self, device_address, uuid=None, passkey=None):
        """Handle display PIN request during pairing.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.
        """
        self.display_pin_or_passkey(device_address, uuid, "PIN")

    def handle_display_passkey_request(self, device_address, uuid=None, passkey=None):
        """Handle display passkey request during pairing.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.
        """
        self.display_pin_or_passkey(device_address, passkey, "Passkey")

    def handle_cancel_request(self, device_address, uuid=None, passkey=None):
        """Handle cancellation of the pairing process.

        Args:
            device_address: The address of the Bluetooth device.
            uuid: The UUID of the Bluetooth service or PIN to display.
            passkey: The passkey for confirmation or display.
        """
        QMessageBox.warning(self, "Pairing Cancelled", f"Pairing with {device_address} was cancelled.")
