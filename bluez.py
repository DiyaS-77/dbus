def setup_pairing_signal_listener(self, callback):
    """Setup D-Bus signal listener for pairing status changes."""
    self.pairing_status_callback = callback
    self.bus.add_signal_receiver(
        self.on_properties_changed,
        dbus_interface="org.freedesktop.DBus.Properties",
        signal_name="PropertiesChanged",
        arg0="org.bluez.Device1",
        path_keyword="path")

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
