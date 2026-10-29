"""
Utilisation (sous Windows) :
    python main.py                          -> menu interactif
    python main.py --details                -> mode ligne de commande : + pilote et caracteristiques
    python main.py --category Disque --details
    python main.py --name realtek --details
    python main.py --all                    -> inclut les peripheriques techniques
"""
import argparse
import sys
import time
from collections import Counter
from itertools import groupby

from device_scanner import scan_all, scan_system
from device_info import get_details

# Peripheriques techniques masques par defaut (virtuels, internes e Windows).
NOISE = ("WAN Miniport", "Kernel Debug", "Wi-Fi Direct", "MS Idd",
         "Proxy de service", "Hub USB racine", "USB composite")

_devices = None        # cache : le scan WMI est lent, on ne le fait qu'une fois
_detailed = set()      # peripheriques dont les details ont deja ete lus


# ---------- Outils d'affichage ----------

def is_noise(device):
    return any(word.lower() in device.name.lower() for word in NOISE)


def show_maker(device):
    """Retourne ' - Fabricant' seulement s'il apprend quelque chose."""
    maker = device.manufacturer
    if maker == "Inconnu" or maker.lower().startswith("microsoft"):
        return ""
    if maker.split()[0].split("(")[0].lower() in device.name.lower():  # déjà dans le nom
        return ""
    return f" - {maker}"


def print_device(device, with_details, count=1):
    line = f"  - {device.name}{show_maker(device)}"
    if count > 1:
        line += f"  x{count}"
    if with_details or device.status != "OK":
        line += f"  [{device.status}]"
    print(line)
    if with_details:
        if device.driver:
            print(f"        Pilote : {device.driver}")
        for label, value in device.details.items():
            print(f"        {label} : {value}")


def load_devices():
    """Scanne la machine une seule fois, puis réutilise le résultat."""
    global _devices
    if _devices is None:
        start = time.time()
        _devices = scan_system() + scan_all()
        print(f"{len(_devices)} périphériques détectés en {time.time() - start:.1f} s")
    return _devices


def display(devices, details=False, include_all=False, category=None, name=None):
    """Filtre la liste puis l'affiche (même logique que les options en ligne de commande)."""
    if not include_all:
        devices = [d for d in devices if not is_noise(d)]
    if category:
        devices = [d for d in devices if d.category.lower() == category.lower()]
    if name:
        needle = name.lower()
        devices = [d for d in devices if needle in d.name.lower() or needle in d.category.lower()]

    if not devices:
        print("Aucun périphérique trouvé.")
        return

    total = len(devices)

    if details:
        start = time.time()
        for device in devices:
            if id(device) not in _detailed:
                get_details(device)
                _detailed.add(id(device))
        print(f"Détails lus en {time.time() - start:.1f} s")

    # groupby suppose une liste triée par catégorie (c'est le cas : scan_all trie,
    # et on retrie ici pour être sûr après avoir ajouté scan_system()).
    devices = sorted(devices, key=lambda d: d.category)
    for cat, group in groupby(devices, key=lambda d: d.category):
        group = list(group)
        print(f"\n[{cat}]")
        counts = Counter(d.name for d in group)
        shown = set()
        for device in group:
            if device.name not in shown:
                shown.add(device.name)
                print_device(device, details, counts[device.name])

    print(f"\nTotal : {total} périphérique(s) affiché(s)")


# ---------- Questions à l'utilisateur ----------

def ask_yes_no(question):
    return input(f"{question} (o/n) : ").strip().lower() in ("o", "oui", "y", "yes")


def choose_category(devices):
    categories = sorted({d.category for d in devices})
    print("\nCatégories disponibles :")
    for number, cat in enumerate(categories, start=1):
        print(f"  {number}. {cat}")
    answer = input("Numéro de la catégorie : ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(categories):
        return categories[int(answer) - 1]
    print("Numéro invalide.")
    return None


# ---------- Menus ----------

def menu_display():
    try:
        devices = load_devices()
    except RuntimeError as error:
        print(f"Erreur : {error}")
        return

    while True:
        print("\n--- Afficher les périphériques ---")
        print("1. Affichage simple (1 ligne par périphérique)")
        print("2. Affichage détaillé (pilote + caractéristiques)")
        print("3. Par catégorie")
        print("4. Par nom")
        print("5. Tout afficher (périphériques techniques inclus)")
        print("6. Retour")
        choice = input("\nChoix : ").strip()

        if choice == "1":
            display(devices)
        elif choice == "2":
            display(devices, details=True)
        elif choice == "3":
            category = choose_category(devices)
            if category:
                display(devices, details=ask_yes_no("Afficher les détails ?"), category=category)
        elif choice == "4":
            name = input("Texte contenu dans le nom : ").strip()
            if name:
                display(devices, details=ask_yes_no("Afficher les détails ?"), name=name)
        elif choice == "5":
            display(devices, details=ask_yes_no("Afficher les détails ?"), include_all=True)
        elif choice == "6":
            break
        else:
            print("Choix invalide.")


def menu_control():
    # Import ici : keyboard_control utilise ctypes.windll et ne doit être chargé que si besoin.
    import keyboard_control
    keyboard_control.main()


def main_menu():
    while True:
        print("\n==============================")
        print("1. Afficher les périphériques")
        print("2. Contrôler (clavier)")
        print("3. Quitter")
        choice = input("\nChoix : ").strip()

        if choice == "1":
            menu_display()
        elif choice == "2":
            menu_control()
        elif choice == "3":
            break
        else:
            print("Choix invalide.")


# ---------- Mode ligne de commande (comme avant) ----------

def main_cli():
    parser = argparse.ArgumentParser(description="Scanner de périphériques")
    parser.add_argument("--details", action="store_true", help="lire aussi les détails et le pilote")
    parser.add_argument("--all", action="store_true", help="inclure les périphériques techniques")
    parser.add_argument("--category", help="filtrer par catégorie (ex. Disque, Reseau)")
    parser.add_argument("--name", help="filtrer par texte contenu dans le nom")
    args = parser.parse_args()

    try:
        devices = load_devices()
    except RuntimeError as error:
        print(f"Erreur : {error}")
        return
    display(devices, args.details, args.all, args.category, args.name)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        main_cli()
    else:
        main_menu()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nArrêt.")
        