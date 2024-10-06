import sys
import time
from dataclasses import fields, dataclass
import hid

DEFAULT_VENDOR_ID = 0x4156
DEFAULT_PRODUCT_ID = 0x0003

USAGE_PAGE = 0xFF60
USAGE = 0x61
REPORT_LENGTH = 32


# fmt:off
@dataclass(slots=True, frozen=True)
class RequestIds:
    id_current_layer:   tuple[int] = (0x40,)
    id_current_cc:      tuple[int] = (0x41,)
    id_current_channel: tuple[int] = (0x42,)
    id_layer_0:         tuple[int] = (0x30,)
    id_layer_1:         tuple[int] = (0x31,)
    id_layer_2:         tuple[int] = (0x32,)
    id_layer_3:         tuple[int] = (0x33,)
    id_layer_4:         tuple[int] = (0x34,)
    id_layer_5:         tuple[int] = (0x35,)
    id_layer_6:         tuple[int] = (0x36,)
    id_layer_7:         tuple[int] = (0x37,)
    id_layer_8:         tuple[int] = (0x38,)
    id_layer_9:         tuple[int] = (0x39,)
# fmt:on

REQUEST_IDS = RequestIds()


def list_qmk_devices():
    device_interfaces = hid.enumerate()
    raw_hid_interfaces = [i for i in device_interfaces if i["usage_page"] == USAGE_PAGE and i["usage"] == USAGE]
    devices = list()
    for interface in raw_hid_interfaces:
        try:
            layer = send_raw_report(REQUEST_IDS.id_current_layer, interface["vendor_id"], interface["product_id"])
            if not layer or layer == "255":
                continue
        except Exception as e:
            print(interface["product_string"], e)
            continue
        devices.append(
            {"name": interface["product_string"], "vid": interface["vendor_id"], "pid": interface["product_id"]}
        )
    return devices


def send_raw_report(data, vendor_id=DEFAULT_VENDOR_ID, product_id=DEFAULT_PRODUCT_ID):

    def get_raw_hid_interface():
        device_interfaces = hid.enumerate(vendor_id, product_id)
        raw_hid_interfaces = [i for i in device_interfaces if i["usage_page"] == USAGE_PAGE and i["usage"] == USAGE]

        if len(raw_hid_interfaces) == 0:
            return None

        my_interface = hid.Device(path=raw_hid_interfaces[0]["path"])

        if __name__ == "__main__":
            print(f"Manufacturer: {my_interface.manufacturer}")
            print(f"Product: {my_interface.product}")

        return my_interface

    interface = get_raw_hid_interface()

    if interface is None:
        print("No device found")
        if __name__ == "__main__":
            sys.exit(1)
        return

    # First byte must be an unused code in via.h "enum via_command_id"
    request_data = [0x00] * (REPORT_LENGTH + 1)
    request_data[1 : len(data) + 1] = data
    request_report = bytes(request_data)
    report = None
    try:
        interface.write(request_report)
        response_report = interface.read(REPORT_LENGTH, timeout=1000)
        if data == REQUEST_IDS.id_current_cc or data == REQUEST_IDS.id_current_layer:
            report = "".join([str(response_report[1]), str(response_report[0])])
            report = str(int(report))
        elif data == REQUEST_IDS.id_current_channel:
            report = "".join([str(response_report[1]), str(response_report[0])])
            report = str(int(report) + 1)
        else:
            report = response_report
    except Exception as e:
        print(e)
    finally:
        interface.close()

    return report


if __name__ == "__main__":
    print("Good response devices:", list_qmk_devices())
    # while True:
    #     request = REQUEST_IDS.id_current_layer
    #     print(
    #         "Request:", [field.name for field in fields(REQUEST_IDS) if getattr(REQUEST_IDS, field.name) == request][0]
    #     )
    #     response = send_raw_report(request)
    #     print("Response:", response)
    #     time.sleep(1)
