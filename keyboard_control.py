import os
import time
import threading
import ctypes
import ctypes.wintypes
try:
    import pyautogui
except ImportError:
    pyautogui = None

COMMAND_FILE = r"C:\keyboard_control\command.txt"

def send_to_agent(command_str):
    """Ecrit la commande pour que l'agent sur la VM l'execute"""
    try:
        with open(COMMAND_FILE, "w", encoding="utf-8") as f:
            f.write(command_str)
        return True
    except Exception as e:
        print(f"Erreur de communication avec l'agent : {e}")
        return False

#Le hook clavier bas niveau
WH_KEYBOARD_LL = 13 #hook de type clavier bas niveau
LRESULT = ctypes.c_ssize_t
WM_KEYDOWN, WM_SYSKEYDOWN = 0x0100, 0x0104
VK_CAPITAL = 0x14
VK_NUMLOCK = 0x90
LLKHF_INJECTED = 0x10  # Indicateur d'evenement generer par programme

class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", ctypes.wintypes.DWORD), #vkCode : le code de la touche presser
        ("scanCode", ctypes.wintypes.DWORD),
        ("flags", ctypes.wintypes.DWORD),#flags : contient le fameux bit (injecter ou pas)
        ("time", ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),]

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM)

# Variables d'etat globales
hook_id = None #identifiant que Windows nous donne une fois le hook installer
_hook_ref = None
keyboard_disabled = False
locked_maj = False
locked_min = False
remappings = {}  # vk_code source -> vk_code cible
_hook_ready = threading.Event()

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _hook_proc(nCode, wParam, lParam):
    """Windows appelle cette fonction automatiquement a chaque touche pour decider quoi faire de chaque une"""
    try:
        if nCode >= 0:
            kbd = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kbd.vkCode
            injected = (kbd.flags & LLKHF_INJECTED) != 0
            if not injected:  # on ne touche jamais aux frappes générées par programme
                if keyboard_disabled:
                    return 1
                if (locked_maj or locked_min) and vk == VK_CAPITAL:
                    return 1
                if vk in remappings:
                    if wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
                        target = remappings[vk]
                        ctypes.windll.user32.keybd_event(target, 0, 0, 0)
                        ctypes.windll.user32.keybd_event(target, 0, 2, 0)
                    return 1  # avale keydown ET keyup de la touche d'origine
    except Exception as e:
        print(f"[-] Erreur dans le hook : {e}")
    return ctypes.windll.user32.CallNextHookEx(hook_id, nCode, wParam, lParam)

def _hook_thread():
    """Installe le hook ET pompe les messages dans le MEME thread."""
    global hook_id, _hook_ref
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GetModuleHandleW.restype = ctypes.wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [ctypes.wintypes.LPCWSTR]
    user32.SetWindowsHookExW.restype = ctypes.wintypes.HHOOK
    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int, LowLevelKeyboardProc, ctypes.wintypes.HINSTANCE, ctypes.wintypes.DWORD]
    user32.CallNextHookEx.restype = LRESULT
    user32.CallNextHookEx.argtypes = [
        ctypes.wintypes.HHOOK, ctypes.c_int, ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM]

    _hook_ref = LowLevelKeyboardProc(_hook_proc)
    hook_id = user32.SetWindowsHookExW(
        WH_KEYBOARD_LL, _hook_ref, kernel32.GetModuleHandleW(None), 0)
    _hook_ready.set()
    if not hook_id:
        return

    msg = ctypes.wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))

def start_keyboard_hook():
    global hook_id
    if hook_id:
        return True
    if not is_admin():
        print("[-] ATTENTION : droits administrateur requis pour le hook clavier.")
    threading.Thread(target=_hook_thread, daemon=True).start()
    _hook_ready.wait(3)
    if not hook_id:
        err = ctypes.windll.kernel32.GetLastError()
        print(f"[-] Impossible d'installer le hook clavier ! Code erreur : {err}")
        return False
    print("[+] Hook clavier bas niveau actif.")
    return True

def set_keyboard_disabled(disabled):
    """Active/desactive le clavier, jusqu'a nouvel ordre"""
    global keyboard_disabled
    if disabled and not start_keyboard_hook():
        return False
    keyboard_disabled = disabled
    return True

def _force_capslock_state(turn_on):
    """force physiquement le voyant a etre allumer ou eteint"""
    user32 = ctypes.windll.user32
    is_on = bool(user32.GetKeyState(VK_CAPITAL) & 0x0001)
    if turn_on != is_on:
        user32.keybd_event(VK_CAPITAL, 0, 0, 0)
        user32.keybd_event(VK_CAPITAL, 0, 2, 0)

def set_capslock_lock(mode):
    """Verrouille Verr. Maj. sur un etat donner et bloque sa bascule physique"""
    global locked_maj, locked_min
    if mode is not None and not start_keyboard_hook():
        return False
    locked_maj = (mode == "MAJ")
    locked_min = (mode == "MIN")
    if mode == "MAJ":
        _force_capslock_state(True)
    elif mode == "MIN":
        _force_capslock_state(False)
    return True

def set_key_remap(src, dst):
    """Ajoute un remappage (reste actif jusqu'a reset_all())"""
    if not start_keyboard_hook():
        return False
    try:
        remappings[ord(src.upper())] = ord(dst.upper())
        print(f"[+] Remappage appliqué en mémoire : {src.upper()} remplacé par {dst.upper()}")
        return True
    except Exception as e:
        print(f"[-] Erreur remappage : {e}")
        return False

def reset_all():
    """Reinitialise tous les etats (desactivation, verrouillage, remappage)"""
    global keyboard_disabled, locked_maj, locked_min
    keyboard_disabled = False
    locked_maj = False
    locked_min = False
    remappings.clear()
    return True

def type_text_value(text):
    """Simule la frappe clavier dans la fenêtre active (ex: Bloc-notes)"""
    if not pyautogui:
        print("Erreur : pyautogui n'est pas installé.")
        return ""
    time.sleep(0.5)
    pyautogui.write(text, interval=0.1)
    return ""

# PARTIE du Menus interactifs (utiliser depuis le terminal SSH sur l'hôte)
# Ces fonctions passent par send_to_agent() pour piloter l'agent distant sur la VM.

def disable_keyboard_menu():
    print("[*] Envoi de l'ordre de désactivation du clavier...")
    if send_to_agent("DISABLE"):
        print("[+] Clavier désactivé sur la VM.")
        while True:
            rep = input("veuillez entrer 'oui' afin de reactiver le clavier : ").strip().lower()
            if rep == "oui":
                send_to_agent("ENABLE")
                print("[+] Ordre de réactivation envoyé !")
                break
            else:
                print("Commande non reconnue. Tapez 'oui' pour réactiver.")


def remap_keyboard_menu():
    print("\n--- Remappage de touches ---")
    src = input("Touche source (ex: a) : ").strip()
    dst = input("Touche cible (ex: z) : ").strip()

    if not src or not dst:
        print("Paramètres invalides.")
        return

    print(f"[*] Envoi de l'ordre de remappage ({src} -> {dst})...")
    success = send_to_agent(f"REMAP:{src},{dst}")
    if success:
        print("[+] Ordre de remappage envoyé à l'agent !")
        while True:
            rep = input("veuillez entrer 'oui' afin de reactiver le clavier normal : ").strip().lower()
            if rep == "oui":
                send_to_agent("ENABLE")  # Restaure l'état normal
                print("[+] Rétablissement du clavier envoyé !")
                break
            else:
                print("Commande non reconnue. Tapez 'oui' pour sortir.")
    else:
        print("[-] Échec de l'envoi.")


def type_text_menu():
    text = input("Entre le texte à injecter dans le Bloc-notes de la VM : ")
    if not text:
        print("Texte vide, annulation.")
        return

    print("[*] Envoi de l'ordre d'écriture à l'agent...")
    success = send_to_agent(f"TYPE:{text}")
    if success:
        print("[+] Ordre envoyé ! Regarde le Bloc-notes sur la VM.")
    else:
        print("[-] Échec de l'envoi de l'ordre.")


def leds_menu():
    while True:
        print("\n--- Contrôle des voyants ---")
        print("1. Verrouiller MAJ")
        print("2. Verrouiller MIN")
        print("3. Retour")

        choix = input("Votre choix : ").strip()
        if choix == "1":
            print("[*] Envoi de l'ordre de Verrouillage MAJ persistant...")
            if send_to_agent("LOCK_MAJ"):
                while True:
                    rep = input("veuillez entrer 'oui' afin de deverouiller : ").strip().lower()
                    if rep == "oui":
                        send_to_agent("UNLOCK")
                        print("[+] Déverrouillage envoyé !")
                        break
        elif choix == "2":
            print("[*] Envoi de l'ordre de Verrouillage MIN persistant...")
            if send_to_agent("LOCK_MIN"):
                while True:
                    rep = input("veuillez entrer 'oui' afin de deverouiller : ").strip().lower()
                    if rep == "oui":
                        send_to_agent("UNLOCK")
                        print("[+] Déverrouillage envoyé !")
                        break
        elif choix == "3":
            break
        else:
            print("Choix invalide.")


def main():
    """Menu Contrôle Clavier restructuré en 5 options."""
    while True:
        print("\n--- Menu Contrôle Clavier ---")
        print("1. Désactiver le clavier")
        print("2. Remapper une touche")
        print("3. Injection de texte")
        print("4. Contrôle des voyants")
        print("5. Retourner au menu principal")

        choix = input("Votre choix : ").strip()
        if choix == "1":
            disable_keyboard_menu()
        elif choix == "2":
            remap_keyboard_menu()
        elif choix == "3":
            type_text_menu()
        elif choix == "4":
            leds_menu()
        elif choix == "5":
            break
        else:
            print("Choix invalide, réessayez.")