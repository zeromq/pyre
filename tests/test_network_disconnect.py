import os
import time
import logging
import subprocess
import pyre


# The test needs the device name of the active network interface.
# The device name can be found under `DEVICE` column after running `nmcli c`.
# The device name should be set to the variable bellow, or as the `DEVICE` env variable.
NMCLI_DEVICE: str = None

NMCLI_LINETERMINATOR = "\n"
NMCLI_DELIMITER = "  "


logger = logging.getLogger(__name__)


def _network_device() -> str:
    return NMCLI_DEVICE or os.environ.get("DEVICE", None)


def _network_device_is_enabled(device: str) -> bool:
    result = subprocess.run(["nmcli", "c"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stderr.decode("ascii")
    output = result.stdout.decode("ascii")
    rows = [[val.strip() for val in row.split(NMCLI_DELIMITER)  if val.strip()] for row in output.split(NMCLI_LINETERMINATOR) if row.strip()]
    head, rows = rows[0], rows[1:]
    devices = [dict(zip(head, row)) for row in rows]
    return any(d["DEVICE"] == device for d in devices)


def _network_device_enable(device: str, enable: bool):
    if _network_device_is_enabled(device) == enable:
        return
    cmd = 'connect' if enable else 'disconnect'
    result = subprocess.run(["nmcli", "d", cmd, f"{device}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert result.returncode == 0, result.stderr.decode("ascii")
    time.sleep(3)
    while _network_device_is_enabled(device) != enable:
        pass
    logger.debug("Device \"{device}\" was {cmd}ed")


def test_network_disconnect(group="best-group"):

    device = _network_device()

    if device is None:
        logger.warn("Skipping test. Please specify an active network interface to use for testing.")
        return

    _network_device_enable(device, enable=True)

    try:
        pyre_node = pyre.Pyre(name="foo")
        pyre_node.join(group)
        pyre_node.start()
        logger.debug("Pyre started")

        _network_device_enable(device, enable=False)

        pyre_node.leave(group)
        logger.debug("Pyre left group")

        pyre_node.stop()
        logger.debug("Pyre stopped")

        del pyre_node
        logger.debug("Pyre destroyed")

    except KeyboardInterrupt:
        pass

    finally:
        _network_device_enable(device, enable=True)


if __name__ == '__main__':
    test_network_disconnect()
