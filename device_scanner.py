from device import Device

# Type Windows -> categorie francaise
CLASSES = {
    "DiskDrive": "Disque",
    "CDROM": "Lecteur CD/DVD",
    "Net": "Reseau",
    "Bluetooth": "Bluetooth",
    "MEDIA": "Audio",
    "Display": "Affichage",
    "Monitor": "Ecran",
    "Keyboard": "Clavier",
    "Mouse": "Souris",
    "USB": "USB",
    "Camera": "Camera",
    "Image": "Camera",
    "Printer": "Imprimante",
    "PrintQueue": "Imprimante",
    "WPD": "Appareil portable",
    "Battery": "Batterie",
    "Biometric": "Biometrie",
    "Ports": "Ports",
}

# Code d'erreur Windows -> etat. Tout autre code = probleme.
ETATS = {0: "OK", 22: "Desactive"}
_wmi = None  # connexion WMI, creer au premier appel

#poser une question a WMI
def query(wmi_class, fields="*"):
    """Interroge une classe WMI et retourne la liste des objets trouves. Leve RuntimeError avec un message clair en cas de probleme."""
    global _wmi
    try:
        if _wmi is None: #Si pas encore connecter, il se connecte a WMI une seule fois
            import win32com.client 
            #Cette bibliotheque fournie par pywin32, permet a Python de communiquer avec certaines interfaces Windows, notamment via COM. C'est le moyen utiliser ici pour acceder a WMI.
            _wmi = win32com.client.GetObject("winmgmts:\\\\.\\root\\cimv2") #veut dire : ordinateur local (.), espace de noms root\cimv2 (celui du materiel)
        return list(_wmi.ExecQuery(f"SELECT {fields} FROM {wmi_class}")) #la requete ressemble a du SQL, le langage souvent utiliser pour interroger des bdd. Mais ici on utilise le langage de requetes de WMI, appeler WQL (WMI Query Language).
    except ImportError: #Si il y a un probleme, il le transforme en RuntimeError avec un message clair
        raise RuntimeError("pywin32 est introuvable. Installe-le avec : pip install pywin32") from None
    except Exception as error:
        raise RuntimeError(f"Lecture de {wmi_class} impossible : {error}") from None

#lire une propriete sans planter
def safe_get(obj, name, default=None):
    try:
        value = getattr(obj, name)
    except Exception:
        return default
    return default if value is None or value == "" else value

#Retourne la liste des peripheriques, tries par categorie puis par nom
def scan_all():
    devices = []
    for obj in query("Win32_PnPEntity"):
        category = CLASSES.get(safe_get(obj, "PNPClass"))
        if category is None:
            continue  # type de peripherique ignore
        code = safe_get(obj, "ConfigManagerErrorCode")
        maker = str(safe_get(obj, "Manufacturer", "")).strip()
        if maker.startswith("(") or "générique" in maker.lower() or "generic" in maker.lower():
            maker = ""
        devices.append(Device(
            name=str(safe_get(obj, "Name", "")).strip() or "Inconnu",
            category=category,
            manufacturer=maker or "Inconnu",
            device_id=str(safe_get(obj, "PNPDeviceID", "")).strip(),
            status="Inconnu" if code is None else ETATS.get(code, "Erreur"),
            description=str(safe_get(obj, "Description", "")).strip(),
        ))
    devices.sort(key=lambda d: (d.category, d.name.lower()))
    return devices

#Meme principe mais avec dautres classes WMI car ces elements ne sont pas des peripheriques PnP
def scan_system():
    devices = []
    for cs in query("Win32_ComputerSystem"):
        devices.append(Device(
            name=str(safe_get(cs, "Name", "Inconnu")).strip(),
            category="Systeme",
            manufacturer=str(safe_get(cs, "Manufacturer", "Inconnu")).strip(),
            status="OK",
            details={"Modele": str(safe_get(cs, "Model", "N/A"))},
        ))
    for os_ in query("Win32_OperatingSystem"):
        devices.append(Device(
            name=str(safe_get(os_, "Caption", "Inconnu")).strip(),
            category="Systeme",
            manufacturer=str(safe_get(os_, "Manufacturer", "Inconnu")).strip(),
            status="OK",
            details={
                "Version": str(safe_get(os_, "Version", "N/A")),
                "Architecture": str(safe_get(os_, "OSArchitecture", "N/A")),
            },
        ))
    for cpu in query("Win32_Processor"):
        devices.append(Device(
            name=str(safe_get(cpu, "Name", "Inconnu")).strip(),
            category="Processeur",
            manufacturer=str(safe_get(cpu, "Manufacturer", "Inconnu")).strip(),
            status="OK",
            details={
                "Coeurs physiques": str(safe_get(cpu, "NumberOfCores", "N/A")),
                "Threads logiques": str(safe_get(cpu, "NumberOfLogicalProcessors", "N/A")),
                "Frequence max": f"{safe_get(cpu, 'MaxClockSpeed', 'N/A')} MHz",
            },
        ))
        
    #La RAM est regroupee : 1 ligne pour tous les modules identiques
    rams = query("Win32_PhysicalMemory")
    if rams:
        sizes = [int(safe_get(r, "Capacity", 0)) / 1024 ** 3 for r in rams]
        devices.append(Device(
            name=f"Memoire RAM {round(sum(sizes))} Go",
            category="Memoire",
            manufacturer=str(safe_get(rams[0], "Manufacturer", "Inconnu")).strip(),
            status="OK",
            details={
                "Modules": f"{len(rams)} x {round(sizes[0])} Go",
                "Vitesse": f"{safe_get(rams[0], 'Speed', 'N/A')} MT/s",
            },
        ))
    return devices