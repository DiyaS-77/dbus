def register_pairing_status_callback(self, status_update_handler):
    """
    Registers a handler to receive Bluetooth pairing status updates via D-Bus signals.

    This sets up a listener for the 'PropertiesChanged' signal on the 'org.bluez.Device1' interface.
    When the 'Paired' property changes (either paired or unpaired), the provided handler is called.

    Args:
        status_update_handler (function): A callable that accepts two arguments:
            - device_address (str): The Bluetooth address of the device.
            - paired (bool): True if the device is now paired, False if unpaired or pairing failed.
    """
    self.pairing_status_callback = status_update_handler
    self.bus.add_signal_receiver(
        self._on_properties_changed,
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
    if hasattr(self, "pairing_status_callback") and callable(self.pairing_status_callback):
        self.pairing_status_callback(device_address, paired)



def setup_dbus_signals(self):
    self.bluetooth_device_manager.setup_pairing_signal_listener(self.handle_pairing_status_update)

def handle_pairing_status_update(self, device_address, paired):
    if paired:
        self.log.info(f"[Signal] Device paired: {device_address}")
        self.add_paired_device_to_list(device_address)
        QMessageBox.information(self, "Pairing Successful", f"{device_address} was paired successfully.")
    else:
        self.log.info(f"[Signal] Pairing failed or device unpaired: {device_address}")
        QMessageBox.warning(self, "Pairing Failed", f"Pairing with {device_address} failed.")
        self.remove_device_from_list(device_address)
