import dbus
import dbus.service
from libraries.bluetooth import constants


class Agent(dbus.service.Object):
    """D-Bus Bluetooth Agent implementation for handling pairing requests."""

    def __init__(self, bus, path, ui_callback, log):
        """Initializes the Agent Object.

        Args:
             bus: D-Bus Connection to register the agent.
             path: Object path for the D-Bus object.
             ui_callback: Callback function to interact with the UI.
             log: Logger instance.
        """
        super().__init__(bus, path)
        self.ui_callback = ui_callback
        self.log = log

    @dbus.service.method(constants.agent, in_signature="o", out_signature="s")
    def RequestPinCode(self, device):
        """Request a PIN code for pairing.

        Args:
            device: D-Bus object path of the remote  device.

        Returns:
            Pin entered by user or False.
        """
        pin = self.ui_callback("pin", device)
        if pin:
            self.log.info("RequestPinCode reply = %s", pin)
            return pin
        else:
            self.log.info("User rejected or did not provide PIN for %s", device)
            return False

    @dbus.service.method(constants.agent, in_signature="o", out_signature="u")
    def RequestPasskey(self, device):
        """Request a numeric passkey for pairing.

        Args:
            device: D-Bus object path of the remote device.

        Returns:
            Passkey entered by the user or False.
        """
        passkey = self.ui_callback("passkey", device)
        if passkey is not None:
            self.log.info("RequestPasskey reply = %s", passkey)
            return dbus.UInt32(passkey)
        else:
            self.log.info("User rejected or did not provide passkey for %s", device)
            return False

    @dbus.service.method(constants.agent, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device, passkey):
        """Request confirmation of a displayed passkey from the user.

        Args:
            device: D-Bus object path of the remote device.
            passkey: Passkey displayed for verification.

        Returns:
            False if rejected by user.
        """
        response = self.ui_callback("confirm", device, passkey)
        self.log.info("RequestConfirmation response = %s", response)
        if response:
            self.log.info("User confirmed pairing with %s", device)
            return
        else:
            self.log.info("User rejected pairing with %s", device)
            return False

    @dbus.service.method(constants.agent, in_signature="os", out_signature="")
    def AuthorizeService(self, device, uuid):
        """Request authorization from the user for a specific Bluetooth service.

        Args:
            device: D-Bus object path of remote device.
            uuid: UUID of the service requiring authorization.

        Returns:
            False if rejected by user.
        """
        response = self.ui_callback("authorize", device, uuid)
        if response:
            self.log.info("User authorized service %s for device %s", uuid, device)
        else:
            self.log.info("User denied service %s for device %s", uuid, device)
            return False

    @dbus.service.method(constants.agent, in_signature="ouq", out_signature="")
    def DisplayPasskey(self, device, passkey, entered):
        """Display a passkey to the user during pairing.

        Args:
            device: D-Bus object path of the remote device.
            passkey: Passkey to be displayed.
            entered: Number of digits entered so far.

        Returns:
            False if rejected by user.
        """
        response = self.ui_callback("display_passkey", device, passkey=passkey, entered=entered)
        if response:
            self.log.info("Displayed passkey for %s successfully", device)
        else:
            self.log.info("User rejected confirmation for %s", device)
            return False

    @dbus.service.method(constants.agent, in_signature="os", out_signature="")
    def DisplayPinCode(self, device, pincode):
        """Display a PIN code to the user during pairing.

        Args:
            device: D-Bus Object path of the remote device.
            pincode: The pincode to display.

        Returns:
            False if rejected by user.
        """
        response = self.ui_callback("display_pin", device, uuid=pincode)
        if response:
            self.log.info("PIN displayed to user for %s", device)
        else:
            self.log.info("User rejected PIN display for %s", device)
            return False

    @dbus.service.method(constants.agent, in_signature="o", out_signature="")
    def Cancel(self, device):
        """Handle cancellation of the pairing process.

        Args:
            device: D-Bus Object path of remote device.

        Returns:
            False if rejected by user.
        """
        response = self.ui_callback("cancel", device)
        if response:
            self.log.info("User cancelled the pairing for %s", device)
        else:
            self.log.warning("UI callback for cancel failed or returned None for device: %s", device)
            return False
