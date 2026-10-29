# -*- coding: utf-8 -*-
"""
Gestion des périphériques — interface inspirée exactement de la maquette fournie.
Windows 10/11 | Python 3.10+
Installation :
    py -m pip install customtkinter pywin32
Lancement :
    py gestion_peripheriques.py

Les informations sont lues par le backend Windows/WMI du projet.
Les actions clavier appellent les fonctions de keyboard_control.py.
"""
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

try:
    import win32com.client
except ImportError:
    win32com = None


# ---------- Thème / dimensions ----------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BG = "#071426"
PANEL = "#0B1B30"
PANEL2 = "#10243D"
PANEL3 = "#142B48"
BORDER = "#203D60"
BLUE = "#2478FF"
BLUE_DARK = "#123C80"
TEXT = "#E7F0FF"
MUTED = "#A7BEDF"
GREEN = "#20D99A"
FONT = "Segoe UI"


# Le backend du projet est la source unique des données matérielles.
from device_scanner import scan_all, scan_system
from device_info import get_details, clear_cache
import keyboard_control


def safe(obj, prop, default="N/A"):
    try:
        value = getattr(obj, prop)
        return str(value) if value not in (None, "") else default
    except Exception:
        return default


def query_wmi(query):
    """Compatibilité avec l'ancienne interface : les requêtes WMI sont gérées par le backend."""
    try:
        from device_scanner import query as backend_query
        # Les requêtes reçues par l'interface sont au format SELECT * FROM Classe.
        match = __import__("re").search(r"FROM\s+([A-Za-z0-9_]+)", query, __import__("re").I)
        return backend_query(match.group(1)) if match else []
    except Exception:
        return []


def detect_devices():
    """Adapte les objets Device du backend au format attendu par l'interface."""
    try:
        devices = scan_system() + scan_all()
    except RuntimeError as error:
        raise RuntimeError(str(error)) from error

    result = []
    for device in devices:
        try:
            get_details(device)
        except Exception:
            pass
        details = {
            "Nom": device.name or "Inconnu",
            "Type": device.category or "Autre",
            "Fabricant": device.manufacturer or "N/A",
            "État": device.status or "Inconnu",
            "Identifiant": device.device_id or "N/A",
            "Modèle": device.name or "N/A",
            "Description": device.description or device.name or "N/A",
            "Classe": device.category or "Autre",
            "ID Windows": device.device_id or "N/A",
            "Statut Windows": device.status or "N/A",
            "Service": "N/A",
            "Emplacement": device.device_id or "N/A",
            "_backend_device": device,
        }
        if device.driver:
            details["Pilote"] = device.driver
        details.update(device.details or {})
        result.append(details)
    return sorted(result, key=lambda d: (str(d["Type"]).casefold(), str(d["Nom"]).casefold()))


class DeviceManager(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Gestion des périphériques")
        self.geometry("1200x760")
        self.minsize(980, 650)
        self.configure(fg_color=BG)
        self.devices = []
        self.selected_device = None
        self.active_page = "Accueil"

        # Barre de titre intégrée au dessin, comme dans la maquette.
        self.titlebar = ctk.CTkFrame(self, height=42, fg_color="#09172A", corner_radius=0,
                                     border_width=1, border_color=BORDER)
        self.titlebar.pack(fill="x")
        self.titlebar.pack_propagate(False)
        ctk.CTkLabel(self.titlebar, text="▣", font=(FONT, 18), text_color="#B8D3FF").pack(side="left", padx=(14, 10))
        ctk.CTkLabel(self.titlebar, text="Gestion des périphériques", font=(FONT, 12, "bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkButton(self.titlebar, text="—", width=36, height=30, fg_color="transparent",
                      hover_color=PANEL3, command=self.iconify).pack(side="right", padx=3)
        ctk.CTkButton(self.titlebar, text="□", width=36, height=30, fg_color="transparent",
                      hover_color=PANEL3, command=self._toggle_maximize).pack(side="right", padx=3)
        ctk.CTkButton(self.titlebar, text="×", width=36, height=30, fg_color="transparent",
                      hover_color="#7F2638", command=self.destroy).pack(side="right", padx=(3, 8))

        self.body = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self.body.pack(fill="both", expand=True)
        self.sidebar = ctk.CTkFrame(self.body, width=150, fg_color="#081629", corner_radius=0,
                                    border_width=1, border_color=BORDER)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self.nav_buttons = {}
        self.keyboard_disabled_device_id = None
        self._make_nav("Accueil", "⌂")
        self._make_nav("Périphériques", "▦")
        self._make_nav("Clavier", "⌨")
        self._make_nav("À propos", "ⓘ")
        ctk.CTkFrame(self.sidebar, fg_color="transparent").pack(fill="both", expand=True)
        self._make_nav("Paramètres", "⚙", bottom=True)

        self.content = ctk.CTkFrame(self.body, fg_color=BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)
        self.refresh_devices()
        self.show_page("Accueil")

    def _toggle_maximize(self):
        try:
            self.state("zoomed" if self.state() != "zoomed" else "normal")
        except Exception:
            pass

    def _make_nav(self, label, symbol, bottom=False):
        btn = ctk.CTkButton(
            self.sidebar, text=f"{symbol}   {label}", anchor="w",
            height=39, corner_radius=6, font=(FONT, 11),
            fg_color="transparent", hover_color=PANEL3, text_color=TEXT,
            command=lambda name=label: self.show_page(name)
        )
        btn.pack(fill="x", padx=7, pady=(7 if label == "Accueil" else 3, 0) if not bottom else (0, 9), side="bottom" if bottom else "top")
        self.nav_buttons[label] = btn

    def refresh_devices(self):
        try:
            clear_cache()
            self.devices = detect_devices()
        except Exception as error:
            self.devices = []
            messagebox.showerror(
                "Détection impossible",
                "Le backend n'a pas pu lire les périphériques Windows.\\n\\n"
                f"Détail : {error}\\n\\n"
                "Vérifiez que vous utilisez Windows et que pywin32 est installé."
            )

    def _clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def _page_title(self, title, subtitle=None):
        ctk.CTkLabel(self.content, text=title, font=(FONT, 20, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=22, pady=(16, 2))
        if subtitle:
            ctk.CTkLabel(self.content, text=subtitle, font=(FONT, 11),
                         text_color=MUTED).pack(anchor="w", padx=22, pady=(0, 14))

    def _card(self, parent, **kwargs):
        return ctk.CTkFrame(parent, fg_color=PANEL2, border_color=BORDER, border_width=1,
                            corner_radius=7, **kwargs)

    def show_page(self, page):
        self.active_page = page
        for name, button in self.nav_buttons.items():
            button.configure(fg_color=BLUE_DARK if name == page else "transparent")
        self._clear_content()
        if page == "Accueil":
            self._home_page()
        elif page == "Périphériques":
            self._devices_page()
        elif page == "Clavier":
            self._keyboard_page()
        elif page == "À propos":
            self._about_page()
        elif page == "Paramètres":
            self._settings_page()

    def _home_page(self):
        self._page_title("Bienvenue !")
        ctk.CTkLabel(self.content,
            text="Ce programme permet de reconnaître les périphériques de votre machine\net d’afficher leurs caractéristiques.",
            font=(FONT, 12), text_color=TEXT, justify="left").pack(anchor="w", padx=22, pady=(0, 18))
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.pack(fill="x", padx=22)
        row.grid_columnconfigure((0, 1), weight=1, uniform="cards")
        card1 = self._card(row, height=135)
        card1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        card1.grid_propagate(False)
        ctk.CTkLabel(card1, text="▣", font=(FONT, 31), text_color="#B9D5FF",
                     fg_color=BLUE_DARK, corner_radius=40, width=62, height=62).place(x=15, y=17)
        ctk.CTkLabel(card1, text=str(len(self.devices)), font=(FONT, 27, "bold"),
                     text_color=TEXT).place(x=91, y=15)
        ctk.CTkLabel(card1, text="Périphériques détectés", font=(FONT, 11),
                     text_color=TEXT).place(x=92, y=54)
        ctk.CTkLabel(card1, text="●", text_color=GREEN, font=(FONT, 13)).place(x=18, y=94)
        ctk.CTkLabel(card1, text="Tous les périphériques sont en état",
                     font=(FONT, 10), text_color=MUTED).place(x=37, y=96)
        card2 = self._card(row, height=135)
        card2.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        card2.grid_propagate(False)
        ctk.CTkLabel(card2, text="⌨", font=(FONT, 30), text_color="#B9D5FF",
                     fg_color=BLUE_DARK, corner_radius=40, width=62, height=62).place(x=15, y=17)
        ctk.CTkLabel(card2, text="Contrôle du clavier", font=(FONT, 14, "bold"),
                     text_color=TEXT).place(x=92, y=27)
        ctk.CTkLabel(card2, text="Vous pouvez prendre le contrôle du\nclavier de votre ordinateur.",
                     font=(FONT, 10), text_color=MUTED, justify="left").place(x=92, y=62)
        ctk.CTkFrame(self.content, height=1, fg_color=BORDER).pack(fill="x", padx=22, pady=(21, 14))
        ctk.CTkLabel(self.content, text="Actions rapides", font=(FONT, 14, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=22, pady=(0, 10))
        actions = ctk.CTkFrame(self.content, fg_color="transparent")
        actions.pack(fill="x", padx=22)
        actions.grid_columnconfigure((0, 1), weight=1, uniform="actions")
        ctk.CTkButton(actions, text="⌕   Détecter les périphériques", height=45,
                      fg_color=BLUE, hover_color="#1763D9", font=(FONT, 11, "bold"),
                      command=self._open_devices_page).grid(row=0, column=0, sticky="ew", padx=(0, 7))
        ctk.CTkButton(actions, text="⌨   Accéder au contrôle du clavier", height=45,
                      fg_color=PANEL, border_color=BLUE, border_width=1, hover_color=PANEL3,
                      font=(FONT, 11), command=lambda: self.show_page("Clavier")).grid(row=0, column=1, sticky="ew", padx=(7, 0))

    def _open_devices_page(self):
        self.refresh_devices()
        self.show_page("Périphériques")

    def _redetect(self):
        self.refresh_devices()
        self.show_page("Périphériques")
        messagebox.showinfo("Détection terminée", f"{len(self.devices)} périphérique(s) détecté(s).")

    def _devices_page(self):
        top = ctk.CTkFrame(self.content, fg_color="transparent")
        top.pack(fill="x", padx=18, pady=(16, 10))
        ctk.CTkLabel(top, text="Liste des périphériques", font=(FONT, 19, "bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(top, text="Recherchez et filtrez les périphériques détectés sur votre machine.",
                     font=(FONT, 11), text_color=MUTED).pack(anchor="w", pady=(3, 9))

        filters = ctk.CTkFrame(top, fg_color="transparent")
        filters.pack(fill="x")
        search = ctk.CTkEntry(filters, height=34, placeholder_text="⌕  Rechercher un périphérique...",
                              fg_color=PANEL, border_color=BORDER, text_color=TEXT, font=(FONT, 10))
        search.pack(side="left", fill="x", expand=True, padx=(0, 8))
        types = sorted({str(d.get("Type", "Autre")) for d in self.devices})
        makers = sorted({str(d.get("Fabricant", "N/A")) for d in self.devices})
        type_filter = ctk.CTkComboBox(filters, values=["Tous les types"] + types, width=170, height=34,
                                      fg_color=PANEL, border_color=BORDER, text_color=TEXT,
                                      button_color=BLUE_DARK, dropdown_fg_color=PANEL2)
        type_filter.set("Tous les types")
        type_filter.pack(side="left", padx=(0, 8))
        maker_filter = ctk.CTkComboBox(filters, values=["Tous les fabricants"] + makers, width=190, height=34,
                                       fg_color=PANEL, border_color=BORDER, text_color=TEXT,
                                       button_color=BLUE_DARK, dropdown_fg_color=PANEL2)
        maker_filter.set("Tous les fabricants")
        maker_filter.pack(side="left")

        table_card = self._card(self.content)
        table_card.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        headers = ["Nom", "Type", "Fabricant", "Statut", ""]
        # Les colonnes de l'en-tête et des lignes utilisent exactement les mêmes poids.
        weights = [40, 19, 25, 14, 4]
        header = ctk.CTkFrame(table_card, fg_color="#132943", corner_radius=5)
        header.pack(fill="x", padx=1, pady=1)
        for i, (heading, weight) in enumerate(zip(headers, weights)):
            header.grid_columnconfigure(i, weight=weight, uniform="device_columns")
            ctk.CTkLabel(header, text=heading, font=(FONT, 10, "bold"), text_color=TEXT,
                         anchor="w").grid(row=0, column=i, sticky="ew", padx=10, pady=10)
        scroll = ctk.CTkScrollableFrame(table_card, fg_color="transparent", corner_radius=0)
        scroll.pack(fill="both", expand=True, padx=1, pady=(0, 1))

        def populate(*_):
            for child in scroll.winfo_children():
                child.destroy()
            term = search.get().strip().casefold()
            selected_type = type_filter.get()
            selected_maker = maker_filter.get()
            filtered = [d for d in self.devices
                        if term in " ".join(str(v) for k, v in d.items() if not k.startswith("_")).casefold()
                        and (selected_type == "Tous les types" or str(d.get("Type", "Autre")) == selected_type)
                        and (selected_maker == "Tous les fabricants" or str(d.get("Fabricant", "N/A")) == selected_maker)]
            for idx, device in enumerate(filtered):
                row = ctk.CTkFrame(scroll, fg_color=PANEL2 if idx % 2 == 0 else "#0D2037",
                                   corner_radius=0, height=38)
                row.pack(fill="x")
                row.pack_propagate(False)
                for i, weight in enumerate(weights):
                    row.grid_columnconfigure(i, weight=weight, uniform="device_columns")
                icon = self._icon_for(device["Type"])
                ctk.CTkLabel(row, text=f"{icon}  {device['Nom']}", font=(FONT, 10),
                             text_color=TEXT, anchor="w").grid(row=0, column=0, sticky="ew", padx=10)
                ctk.CTkLabel(row, text=device["Type"], font=(FONT, 10),
                             text_color=TEXT, anchor="w").grid(row=0, column=1, sticky="ew", padx=10)
                ctk.CTkLabel(row, text=device["Fabricant"], font=(FONT, 10),
                             text_color=TEXT, anchor="w").grid(row=0, column=2, sticky="ew", padx=10)
                status = str(device.get("État", "Inconnu"))
                status_color = GREEN if status.casefold() in ("ok", "normal", "running", "en fonctionnement") else "#FFB84D"
                ctk.CTkLabel(row, text=f"●  {status}", font=(FONT, 10),
                             text_color=status_color, anchor="w").grid(row=0, column=3, sticky="ew", padx=10)
                ctk.CTkButton(row, text="›", width=24, height=27, fg_color="transparent",
                              hover_color=PANEL3, text_color=MUTED, font=(FONT, 19),
                              command=lambda d=device: self._details_page(d)).grid(row=0, column=4, padx=4)
                row.bind("<Double-Button-1>", lambda e, d=device: self._details_page(d))
            footer.configure(text=f"Total : {len(filtered)} périphérique(s)")

        search.bind("<KeyRelease>", populate)
        type_filter.configure(command=populate)
        maker_filter.configure(command=populate)
        footer = ctk.CTkLabel(self.content, text=f"Total : {len(self.devices)} périphérique(s)",
                              font=(FONT, 10), text_color=MUTED)
        footer.pack(anchor="w", padx=18, pady=(0, 10))
        populate()

    @staticmethod
    def _icon_for(kind):
        if "Clavier" in kind: return "⌨"
        if "Souris" in kind: return "🖱"
        if "Écran" in kind or "graphique" in kind: return "▣"
        if "réseau" in kind: return "◉"
        if "Disque" in kind or "Stockage" in kind: return "▰"
        if "USB" in kind: return "♧"
        if "Audio" in kind: return "♫"
        return "▣"

    def _details_page(self, device):
        self.selected_device = device
        self.show_page("Détails")  # L'onglet reste Périphériques comme dans la maquette.
        if "Périphériques" in self.nav_buttons:
            self.nav_buttons["Périphériques"].configure(fg_color=BLUE_DARK)
        ctk.CTkButton(self.content, text="‹  Retour à la liste", height=28, width=140,
                      fg_color="transparent", hover_color=PANEL3, text_color=MUTED,
                      anchor="w", command=lambda: self.show_page("Périphériques")).pack(anchor="w", padx=18, pady=(12, 0))
        self._page_title("Détails du périphérique")
        summary = self._card(self.content, height=88)
        summary.pack(fill="x", padx=18, pady=(0, 10))
        summary.pack_propagate(False)
        ctk.CTkLabel(summary, text=self._icon_for(device["Type"]), font=(FONT, 27),
                     text_color="#B9D5FF", fg_color=BLUE_DARK, corner_radius=35,
                     width=56, height=56).place(x=13, y=15)
        ctk.CTkLabel(summary, text=device["Nom"], font=(FONT, 14, "bold"),
                     text_color=TEXT).place(x=79, y=15)
        ctk.CTkLabel(summary, text=f'Type : {device["Type"]}', font=(FONT, 11),
                     text_color=MUTED).place(x=79, y=39)
        ctk.CTkLabel(summary, text=f'●  État : {device["État"]}', font=(FONT, 10),
                     text_color=GREEN if device["État"] == "OK" else "#FFB84D").place(x=79, y=61)

        columns = ctk.CTkFrame(self.content, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        columns.grid_columnconfigure((0, 1), weight=1, uniform="detail")
        general = self._card(columns)
        general.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        specs = self._card(columns)
        specs.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        self._detail_table(general, "Informations générales", [
            ("Fabricant", device.get("Fabricant", "N/A")),
            ("Modèle", device.get("Modèle", "N/A")),
            ("Identifiant", device.get("Identifiant", "N/A")),
            ("ID Windows", device.get("ID Windows", "N/A")),
            ("Service", device.get("Service", "N/A")),
            ("État", "Fonctionne correctement" if device["État"] == "OK" else device["État"]),
        ])
        special = [(k, v) for k, v in device.items()
                   if k not in {"Nom", "Type", "Fabricant", "État", "Identifiant", "Modèle",
                                "Description", "Classe", "ID Windows", "Statut Windows", "Service",
                                "Emplacement"}]
        if not special:
            special = [("Catégorie", device.get("Classe", "N/A")),
                       ("Type de connexion", "USB / intégré (selon le périphérique)"),
                       ("Statut", device["État"])]
        self._detail_table(specs, "Caractéristiques", special[:8])

    def _detail_table(self, parent, title, rows):
        ctk.CTkLabel(parent, text=title, font=(FONT, 11, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=10, pady=(10, 7))
        for i, (key, value) in enumerate(rows):
            line = ctk.CTkFrame(parent, fg_color=PANEL if i % 2 == 0 else PANEL2, corner_radius=0)
            line.pack(fill="x", padx=1)
            line.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(line, text=key, font=(FONT, 9), text_color=MUTED,
                         anchor="w", wraplength=130).grid(row=0, column=0, sticky="ew", padx=9, pady=7)
            ctk.CTkLabel(line, text=str(value), font=(FONT, 9), text_color=TEXT,
                         anchor="w", wraplength=210).grid(row=0, column=1, sticky="ew", padx=9, pady=7)

    def _keyboard_page(self):
        self._page_title("Contrôle du clavier", "Consultez son état et lancez les actions disponibles.")

        # Zone de test : elle reçoit les frappes manuelles et le texte envoyé automatiquement.
        test = self._card(self.content)
        test.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkLabel(test, text="Zone de test", font=(FONT, 11, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=12, pady=(12, 5))
        ctk.CTkLabel(test, text="Le texte saisi automatiquement apparaîtra ici.",
                     font=(FONT, 10), text_color=MUTED).pack(anchor="w", padx=12, pady=(0, 7))
        self.keyboard_input = ctk.CTkTextbox(
            test, height=75, fg_color="#08172A", border_color=BORDER,
            border_width=1, text_color=TEXT, font=(FONT, 11), corner_radius=5)
        self.keyboard_input.pack(fill="x", padx=12, pady=(0, 10))
        test_tools = ctk.CTkFrame(test, fg_color="transparent")
        test_tools.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(test_tools, text="Effacer la zone de test", height=30,
                      fg_color=PANEL3, hover_color=BLUE_DARK, text_color=TEXT,
                      command=lambda: self.keyboard_input.delete("1.0", "end")).pack(side="left")

        control = self._card(self.content)
        control.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        ctk.CTkLabel(control, text="Actions du clavier", font=(FONT, 12, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=12, pady=(12, 7))
        self.keyboard_records = [
            d for d in self.devices
            if "clavier" in str(d.get("Type", "")).casefold()
            and d.get("Identifiant") not in (None, "", "N/A")
        ]
        self.keyboard_record_map = {}
        choices = []
        for index, record in enumerate(self.keyboard_records):
            label = f"{index + 1}. {record['Nom']}"
            choices.append(label)
            self.keyboard_record_map[label] = record
        if choices:
            self.keyboard_choice = ctk.CTkComboBox(
                control, values=choices, width=420, height=32,
                fg_color=PANEL, border_color=BORDER, text_color=TEXT,
                button_color=BLUE_DARK, dropdown_fg_color=PANEL2)
            self.keyboard_choice.set(choices[0])
            self.keyboard_choice.pack(anchor="w", padx=12, pady=(0, 12))
        else:
            self.keyboard_choice = None
            ctk.CTkLabel(control, text="Aucun clavier avec identifiant matériel exploitable n’a été détecté.",
                         font=(FONT, 10), text_color=MUTED).pack(anchor="w", padx=12, pady=(0, 12))

        # Palette cohérente : boutons neutres identiques, bleu réservé à l'action principale.
        buttons = ctk.CTkFrame(control, fg_color="transparent")
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        for col in range(3):
            buttons.grid_columnconfigure(col, weight=1, uniform="keyboard_actions")
        button_style = dict(height=36, fg_color=PANEL3, hover_color=BLUE_DARK,
                            text_color=TEXT, font=(FONT, 10))
        ctk.CTkButton(buttons, text="Voir l’état du clavier", command=self._show_keyboard_state,
                      **button_style).grid(row=0, column=0, sticky="ew", padx=(0, 6), pady=4)
        ctk.CTkButton(buttons, text="Changer le rôle d’une touche", command=self._remap_keyboard_key,
                      **button_style).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
        ctk.CTkButton(buttons, text="Tester les voyants", command=self._blink_keyboard_leds,
                      **button_style).grid(row=0, column=2, sticky="ew", padx=(6, 0), pady=4)

        self.disable_button = ctk.CTkButton(
            buttons, text="Désactiver temporairement (5 s)", command=self._disable_keyboard,
            fg_color=PANEL3, hover_color=BLUE_DARK, text_color=TEXT,
            height=36, font=(FONT, 10))
        self.disable_button.grid(row=1, column=0, sticky="ew", padx=(0, 6), pady=4)
        self.enable_button = ctk.CTkButton(
            buttons, text="Réactiver le clavier", command=self._enable_keyboard,
            fg_color=BLUE_DARK, hover_color=BLUE, text_color=TEXT,
            height=36, font=(FONT, 10))
        self.enable_button.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        ctk.CTkButton(
            buttons, text="Écriture automatique", command=self._type_text_automatically,
            fg_color=BLUE_DARK, hover_color=BLUE, text_color=TEXT,
            height=36, font=(FONT, 10)
        ).grid(row=1, column=2, sticky="ew", padx=(6, 0), pady=4)
        if self.keyboard_disabled_device_id:
            self.disable_button.grid_remove()
        else:
            self.enable_button.grid_remove()

    def _show_keyboard_state(self):
        try:
            keyboards = keyboard_control.get_keyboards()
            if not keyboards:
                messagebox.showinfo("État du clavier", "Aucun clavier détecté par le backend.")
                return
            lines = []
            for kb in keyboards:
                name = getattr(kb, "name", "Clavier")
                status = getattr(kb, "status", "Inconnu") or "Inconnu"
                lines.append(f"• {name} — Statut : {status}")
            lines.append("\nVoyants : " + keyboard_control.get_leds_state())
            messagebox.showinfo("État du clavier", "\n".join(lines))
        except Exception as error:
            messagebox.showerror("État du clavier", f"Impossible de lire l’état du clavier :\n{error}")

    def _selected_keyboard(self):
        if not self.keyboard_choice:
            messagebox.showwarning("Clavier", "Aucun clavier compatible n’est sélectionné.")
            return None
        record = self.keyboard_record_map.get(self.keyboard_choice.get())
        if not record:
            messagebox.showwarning("Clavier", "Sélectionnez un clavier dans la liste.")
            return None
        return record

    def _run_keyboard_task(self, title, task):
        def worker():
            try:
                ok, message = task()
            except Exception as error:
                ok, message = False, str(error)
            self.after(0, lambda: messagebox.showinfo(title, message) if ok else messagebox.showerror(title, message))
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _disable_keyboard(self):
        record = self._selected_keyboard()
        if not record:
            return
        device_id = record.get("Identifiant", "")
        if not messagebox.askyesno(
            "Désactivation du clavier",
            "Le clavier sélectionné va être désactivé jusqu’à ce que vous cliquiez "
            "sur \"Réactiver le clavier\".\n\n"
            "Exécutez l’application en tant qu’administrateur. Continuer ?"
        ):
            return

        def worker():
            try:
                ok, message = keyboard_control.disable_keyboard_device(device_id)
            except Exception as error:
                ok, message = False, str(error)
            def finish():
                if ok:
                    self.keyboard_disabled_device_id = device_id
                    if (hasattr(self, "disable_button") and self.disable_button.winfo_exists()
                            and hasattr(self, "enable_button") and self.enable_button.winfo_exists()):
                        self.disable_button.grid_remove()
                        self.enable_button.grid()
                    messagebox.showinfo("Clavier", message)
                else:
                    messagebox.showerror("Clavier", message)
            self.after(0, finish)
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _enable_keyboard(self):
        device_id = self.keyboard_disabled_device_id
        if not device_id:
            record = self._selected_keyboard()
            if not record:
                return
            device_id = record.get("Identifiant", "")

        def worker():
            try:
                ok, message = keyboard_control.enable_keyboard_device(device_id)
            except Exception as error:
                ok, message = False, str(error)
            def finish():
                if ok:
                    self._reset_keyboard_buttons(device_id)
                    messagebox.showinfo("Clavier", message)
                else:
                    messagebox.showerror("Clavier", message)
            self.after(0, finish)
        import threading
        threading.Thread(target=worker, daemon=True).start()

    def _reset_keyboard_buttons(self, device_id):
        if self.keyboard_disabled_device_id != device_id:
            return
        self.keyboard_disabled_device_id = None
        if (hasattr(self, "disable_button") and self.disable_button.winfo_exists()
                and hasattr(self, "enable_button") and self.enable_button.winfo_exists()):
            self.enable_button.grid_remove()
            self.disable_button.grid()

    def _remap_keyboard_key(self):
        source = ctk.CTkInputDialog(text="Quelle lettre remplacer ? (A-Z)", title="Remplacer une touche").get_input()
        if not source:
            return
        target = ctk.CTkInputDialog(text="Quelle lettre écrire à la place ? (A-Z)", title="Remplacer une touche").get_input()
        if not target:
            return
        source, target = source.strip(), target.strip()
        if len(source) != 1 or not source.isascii() or not source.isalpha() or len(target) != 1 or not target.isascii() or not target.isalpha():
            messagebox.showerror("Remplacer une touche", "Entrez une seule lettre A-Z dans chaque champ.")
            return
        if not messagebox.askyesno(
            "Remplacer une touche",
            f"Jusqu’à ce que vous cliquiez sur \"Réactiver le clavier\", "
            f"{source.upper()} écrira {target.upper()}. Continuer ?"
        ):
            return
        def task():
            success = keyboard_control.remap_keyboard_key(source, target)
            return success, "Remappage actif." if success else "Impossible d’installer le contrôle clavier."
        self._run_keyboard_task("Remplacer une touche", task)

    def _blink_keyboard_leds(self):
        def task():
            keyboard_control.blink_keyboard_leds()
            return True, "Test des voyants terminé. Leur état initial a été restauré."
        self._run_keyboard_task("Voyants du clavier", task)

    def _type_text_automatically(self):
        """Ouvre une petite fenêtre de saisie, sans ajouter de champ permanent à la page."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Écriture automatique")
        dialog.geometry("420x190")
        dialog.resizable(False, False)
        dialog.configure(fg_color=BG)
        dialog.transient(self)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog, text="Texte à écrire automatiquement",
            font=(FONT, 13, "bold"), text_color=TEXT
        ).pack(anchor="w", padx=18, pady=(18, 6))
        entry = ctk.CTkEntry(
            dialog, height=36, placeholder_text="Saisissez votre texte ici…",
            fg_color="#08172A", border_color=BORDER, text_color=TEXT,
            font=(FONT, 11)
        )
        entry.pack(fill="x", padx=18, pady=(0, 12))
        entry.focus_set()

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(0, 16))

        def launch_typing():
            text_to_type = entry.get()
            if not text_to_type.strip():
                messagebox.showwarning(
                    "Écriture automatique", "Saisissez d’abord le texte à écrire.", parent=dialog
                )
                return
            if not messagebox.askyesno(
                "Écriture automatique",
                "Le texte sera saisi dans la zone de test.\n"
                "La saisie commencera après 3 secondes. Continuer ?",
                parent=dialog
            ):
                return
            dialog.grab_release()
            dialog.destroy()
            self.keyboard_input.focus_set()

            def task():
                skipped = keyboard_control.type_text_value(text_to_type)
                if skipped:
                    return True, f"Texte envoyé dans la zone de test. Caractères ignorés : {skipped}"
                return True, "Texte envoyé dans la zone de test."
            self._run_keyboard_task("Écriture automatique", task)

        ctk.CTkButton(
            actions, text="Annuler", height=34, fg_color=PANEL3,
            hover_color=BLUE_DARK, text_color=TEXT,
            command=dialog.destroy
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions, text="Écrire", height=34, fg_color=BLUE_DARK,
            hover_color=BLUE, text_color=TEXT, command=launch_typing
        ).pack(side="right")
        entry.bind("<Return>", lambda _event: launch_typing())

    def _refresh_keyboard_info(self):
        messagebox.showinfo("Clavier", "Les informations du clavier ont été actualisées.")

    def _about_page(self):
        self._page_title("À propos")
        card = self._card(self.content)
        card.pack(fill="x", padx=22, pady=10)
        ctk.CTkLabel(card, text="Gestion des périphériques", font=(FONT, 17, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=18, pady=(18, 8))
        ctk.CTkLabel(card, text="Projet de système d’exploitation — Python / Windows\n"
                     "Reconnaissance des périphériques et affichage de leurs caractéristiques.\n"
                     "Les données matérielles proviennent des classes WMI de Windows.",
                     font=(FONT, 11), text_color=MUTED, justify="left").pack(anchor="w", padx=18, pady=(0, 18))

    def _settings_page(self):
        self._page_title("Paramètres")
        card = self._card(self.content)
        card.pack(fill="x", padx=22, pady=10)
        ctk.CTkLabel(card, text="Détection des périphériques", font=(FONT, 12, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(card, text="Relance une lecture des périphériques exposés par Windows.",
                     font=(FONT, 10), text_color=MUTED).pack(anchor="w", padx=15, pady=(0, 10))
        ctk.CTkButton(card, text="Détecter à nouveau", fg_color=BLUE,
                      command=self._redetect).pack(anchor="w", padx=15, pady=(0, 15))


if __name__ == "__main__":
    app = DeviceManager()
    app.mainloop()