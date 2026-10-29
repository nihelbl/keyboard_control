"""Agent exécuté sur la VM Windows : lit les ordres écrits par le menu de
contrôle clavier (via SSH, dans command.txt) et les applique réellement sur
le clavier local, en s'appuyant sur le hook bas niveau de keyboard_control.py.

Toute la mécanique Windows (hook, remappage, verrouillage) vit dans
keyboard_control.py pour éviter d'avoir deux implémentations divergentes du
meme hook clavier dans deux fichiers différents.
"""
import os
import time

try:
    import pyautogui
except ImportError:
    pyautogui = None

# Meme valeur que COMMAND_FILE dans keyboard_control.py : les deux fichiers
# doivent imperativement pointer vers le meme command.txt (meme dossier).
COMMAND_FILE = "command.txt"

from keyboard_control import (
    is_admin,
    start_keyboard_hook,
    set_keyboard_disabled,
    set_capslock_lock,
    set_key_remap,
    reset_all,
    type_text_value,
)


def run_agent():
    print("==================================================")
    if is_admin():
        print("[+] Agent exécuté avec les privilèges ADMINISTRATEUR.")
    else:
        print("[-] ATTENTION : L'agent N'EST PAS lancé en Administrateur !")
    print("==================================================")

    start_keyboard_hook()

    while True:
        if os.path.exists(COMMAND_FILE):
            try:
                with open(COMMAND_FILE, "r", encoding="utf-8") as f:
                    cmd = f.read().strip()
                os.remove(COMMAND_FILE)

                if cmd == "DISABLE":
                    print("[*] Ordre reçu : Désactivation du clavier (Souris libre)...")
                    set_keyboard_disabled(True)

                elif cmd == "ENABLE":
                    print("[*] Ordre reçu : Réactivation du clavier / Restauration...")
                    reset_all()

                elif cmd.startswith("TYPE:"):
                    text = cmd[5:]
                    print(f"Exécution écriture : {text}")
                    try:
                        if pyautogui:
                            windows = pyautogui.getWindowsWithTitle("Bloc-notes")
                            if windows:
                                windows[0].activate()
                                time.sleep(0.5)
                    except Exception as focus_err:
                        print(f"Erreur focus : {focus_err}")
                    type_text_value(text)

                elif cmd.startswith("REMAP:"):
                    parts = cmd[6:].split(",")
                    if len(parts) == 2:
                        set_key_remap(parts[0], parts[1])

                elif cmd == "LOCK_MAJ":
                    print("[*] Verrouillage MAJ persistant activé.")
                    set_capslock_lock("MAJ")

                elif cmd == "LOCK_MIN":
                    print("[*] Verrouillage MIN (Minuscules forcées) persistant activé.")
                    set_capslock_lock("MIN")

                elif cmd == "UNLOCK":
                    print("[*] Réinitialisation globale des états.")
                    reset_all()

            except Exception as e:
                print(f"Erreur agent : {e}")

        time.sleep(0.5)


if __name__ == "__main__":
    run_agent()