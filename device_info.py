from device_scanner import query, safe_get

NA = "N/A"

_objects = {}
_drivers = None
_driver_error = None


def clear_cache():
    """Vide les caches des périphériques et des pilotes."""
    global _drivers, _driver_error
    _objects.clear()
    _drivers = None
    _driver_error = None


def _text(value, unit=""):
    if value is None or value == "":
        return NA
    return f"{value} {unit}".strip()


def _gb(size_in_bytes):
    try:
        return round(int(size_in_bytes) / 1024**3, 1)
    except (TypeError, ValueError, OverflowError):
        return None


def _mbps(bits_per_second):
    try:
        value = int(bits_per_second)
    except (TypeError, ValueError, OverflowError):
        return None
    return round(value / 1_000_000) if 0 < value <= 10**12 else None


def _date(wmi_date):
    value = str(wmi_date or "")
    if len(value) < 8 or not value[:8].isdigit():
        return None
    return f"{value[6:8]}/{value[4:6]}/{value[:4]}"


def _disk(obj):
    serial = safe_get(obj, "SerialNumber")
    serial = str(serial).strip(" .") if serial else None

    return {
        "Taille": _text(_gb(safe_get(obj, "Size")), "Go"),
        "Interface": _text(safe_get(obj, "InterfaceType")),
        "Partitions": _text(safe_get(obj, "Partitions")),
        "Numéro de série": _text(serial),
        "Firmware": _text(safe_get(obj, "FirmwareRevision")),
    }


def _network(obj):
    return {
        "Adresse MAC": _text(safe_get(obj, "MACAddress")),
        "Nom de la connexion": _text(safe_get(obj, "NetConnectionID")),
        "Vitesse": _text(_mbps(safe_get(obj, "Speed")), "Mb/s"),
    }


def _video(obj):
    ram = safe_get(obj, "AdapterRAM")

    try:
        ram_mb = round(int(ram) / 1024**2) if ram is not None else None
    except (TypeError, ValueError, OverflowError):
        ram_mb = None

    width = safe_get(obj, "CurrentHorizontalResolution")
    height = safe_get(obj, "CurrentVerticalResolution")

    resolution = f"{width}x{height}" if width and height else None

    return {
        "Mémoire vidéo": _text(ram_mb, "Mo"),
        "Résolution": _text(resolution),
        "Fréquence d'affichage": _text(
            safe_get(obj, "CurrentRefreshRate"), "Hz"
        ),
        "Processeur vidéo": _text(safe_get(obj, "VideoProcessor")),
    }


SPECIFIC = {
    "Disque": ("Win32_DiskDrive", _disk),
    "Réseau": ("Win32_NetworkAdapter", _network),
    "Reseau": ("Win32_NetworkAdapter", _network),
    "Affichage": ("Win32_VideoController", _video),
}


def _find(wmi_class, device_id):
    if wmi_class not in _objects:
        _objects[wmi_class] = {
            str(safe_get(obj, "PNPDeviceID", "") or "").upper(): obj
            for obj in query(wmi_class)
        }

    return _objects[wmi_class].get(str(device_id or "").upper())


def _find_driver(device_id):
    global _drivers, _driver_error

    if _drivers is None:
        try:
            fields = (
                "DeviceID,DriverVersion,DriverDate,"
                "DriverProviderName,InfName"
            )

            _drivers = {
                str(safe_get(obj, "DeviceID", "") or "").upper(): obj
                for obj in query("Win32_PnPSignedDriver", fields)
            }

        except RuntimeError as error:
            _drivers = {}
            _driver_error = str(error)

    return _drivers.get(str(device_id or "").upper())


def _fill_driver(device):
    obj = _find_driver(device.device_id)

    if obj is None:
        if _driver_error:
            device.details["Pilote"] = (
                f"Indisponible ({_driver_error})"
            )
        return

    provider = safe_get(obj, "DriverProviderName")
    version = safe_get(obj, "DriverVersion")

    device.driver = f"{provider or ''} {version or ''}".strip() or NA

    date = _date(safe_get(obj, "DriverDate"))

    if date and date != "21/06/2006":
        device.details["Date du pilote"] = date

    inf_name = safe_get(obj, "InfName")

    if inf_name:
        device.details["Fichier INF"] = str(inf_name)


def get_details(device):
    try:
        specific = SPECIFIC.get(device.category)

        if specific:
            wmi_class, builder = specific
            obj = _find(wmi_class, device.device_id)

            if obj is not None:
                device.details.update(builder(obj))

    except Exception as error:
        device.details["Erreur de détails"] = str(error)

    try:
        _fill_driver(device)
    except Exception as error:
        device.details["Pilote"] = f"Indisponible ({error})"

    if device.description and device.description != device.name:
        device.details["Description"] = device.description

    if device.device_id:
        device.details["Identifiant matériel"] = device.device_id

    if device.manufacturer and device.manufacturer != NA:
        device.details.setdefault("Fabricant", device.manufacturer)

    if device.driver and device.driver != NA:
        device.details["Pilote"] = device.driver

    device.details = {
        label: value
        for label, value in device.details.items()
        if value is not None and value != "" and value != NA
    }

    return device
