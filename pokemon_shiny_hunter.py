import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, filedialog
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional, Dict, List
from PIL import Image, ImageTk
import requests
from io import BytesIO
from datetime import datetime
from dataclasses import dataclass, asdict

# Constants
CACHE_DIR = Path("cache/sprites")
DATA_FILE = "shiny_counter_data.json"
DEFAULT_SPRITE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/0.png"

@dataclass
class PokemonData:
    name: str
    encounters: int = 0
    adjustment: int = 1
    sprite_url: Optional[str] = None
    last_updated: Optional[str] = None
    status: str = "ACTIVE"
    found_date: Optional[str] = None
    game: Optional[str] = None
    notes: Optional[str] = None
    method: Optional[str] = None

@dataclass
class AppData:
    pokemon: Dict[str, PokemonData]
    active_hunts: List[str] = None
    last_pokemon: Optional[str] = None
    theme: str = "light"
    sort_by: str = "most_recent"
    sort_order: str = "descending"

    def __post_init__(self):
        if self.active_hunts is None:
            self.active_hunts = []

class Config:
    API_BASE_URL = "https://pokeapi.co/api/v2"
    MAIN_SPRITE_SIZE = (150, 150)
    CARD_SPRITE_SIZE = (80, 80)
    MINI_SPRITE_SIZE = (40, 40)
    MIN_COLUMNS = 1
    MAX_COLUMNS = 5
    CARD_MIN_WIDTH = 300

    POKEMON_GAMES = {
        "Red/Blue/Yellow": 1,
        "Gold/Silver/Crystal": 2,
        "Ruby/Sapphire/Emerald": 3,
        "FireRed/LeafGreen": 3,
        "Diamond/Pearl/Platinum": 4,
        "HeartGold/SoulSilver": 4,
        "Black/White": 5,
        "Black 2/White 2": 5,
        "X/Y": 6,
        "Omega Ruby/Alpha Sapphire": 6,
        "Sun/Moon": 7,
        "Ultra Sun/Ultra Moon": 7,
        "Sword/Shield": 8,
        "Brilliant Diamond/Shining Pearl": 8,
        "Legends: Arceus": 8,
        "Scarlet/Violet": 9
    }

    HUNT_METHODS = [
        "Random Encounter",
        "Soft Reset",
        "Masuda Method",
        "Chain Fishing",
        "Poke Radar",
        "DexNav",
        "SOS Battles",
        "Dynamax Adventures",
        "Outbreaks",
        "Other"
    ]

    COLORS = {
        'light': {
            'primary': '#3D7DCA',
            'secondary': '#FFCB05',
            'background': '#f0f8ff',
            'card_bg': '#ffffff',
            'text_primary': '#2C3E50',
            'text_secondary': '#7F8C8D',
            'border': '#BDC3C7',
            'highlight': '#D6EAF8',
            'complete': '#28a745',  # Darker green
            'paused': '#E74C3C'
        },
        'dark': {
            'primary': '#2c3e50',
            'secondary': '#f1c40f',
            'background': '#34495e',
            'card_bg': '#2c3e50',
            'text_primary': '#ecf0f1',
            'text_secondary': '#bdc3c7',
            'border': '#7f8c8d',
            'highlight': '#3498db',
            'complete': '#28a745',
            'paused': '#e74c3c'
        }
    }


class ShinyCounter:
    def __init__(self, root):
        self.root = root
        self.root.title("Pokémon Shiny Hunter")
        self.root.geometry("1000x600")
        self.root.minsize(800, 500)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.storage_file = DATA_FILE
        self.saved_data = AppData(pokemon={})
        self.current_pokemon = ""
        self.current_number = 0
        self.default_adjustment = 1
        self.current_game = tk.StringVar()
        self.current_method = tk.StringVar(value=Config.HUNT_METHODS[0])
        self.image_references = []
        self.current_theme = "light"
        self.sort_by = tk.StringVar(value="most_recent")
        self.sort_order = tk.StringVar(value="descending")

        self.communication_files = {
            'emulator_count': "melon_emulator_count.txt",
            'encounter_trigger': "encounter_trigger.txt"
        }
        self.last_trigger_time = 0
        self.initial_load = True

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.setup_styles()
        self.create_widgets()
        self.load_data()
        self.initialize_communication_files()
        self.setup_file_watcher()
        self.load_most_recent_active_hunt()
        self.initial_load = True

    def load_most_recent_active_hunt(self):
        try:
            if self.saved_data.active_hunts:
                self.load_pokemon(self.saved_data.active_hunts[0])
            elif self.saved_data.last_pokemon and self.saved_data.last_pokemon in self.saved_data.pokemon:
                self.load_pokemon(self.saved_data.last_pokemon)
        except Exception as e:
            print(f"Error loading recent hunt: {e}")

    def on_close(self):
        self.saved_data.last_pokemon = self.current_pokemon
        self.save_data()
        self.root.destroy()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        colors = Config.COLORS[self.current_theme]
        style.configure('TFrame', background=colors['background'])
        style.configure('Card.TFrame', background=colors['card_bg'], borderwidth=1, relief=tk.RAISED)
        style.configure('TButton', font=('Arial', 10), padding=6, background=colors['primary'], foreground='white')
        style.map('TButton', background=[('active', colors['primary'])])
        style.configure('Secondary.TButton', background=colors['secondary'], foreground=colors['text_primary'])
        style.configure('Success.TButton', background=colors['complete'], foreground='white')
        style.configure('Danger.TButton', background=colors['paused'], foreground='white')
        style.configure('TEntry', fieldbackground=colors['card_bg'], foreground=colors['text_primary'])
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'), foreground=colors['primary'])
        style.configure('Subheader.TLabel', font=('Arial', 12), foreground=colors['text_primary'])

    def toggle_theme(self):
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self.saved_data.theme = self.current_theme
        self.setup_styles()
        self.update_ui_colors()
        self.save_data()

    def update_ui_colors(self):
        colors = Config.COLORS[self.current_theme]
        self.root.configure(background=colors['background'])
        self.hunts_canvas.configure(bg=colors['card_bg'])
        for widget in self.hunts_frame.winfo_children():
            widget.configure(style='Card.TFrame')

    def create_widgets(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_panel = ttk.Frame(main_frame, width=400, style='Card.TFrame')
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

        display_frame = ttk.Frame(left_panel, style='Card.TFrame', padding=10)
        display_frame.pack(fill=tk.X, pady=5)

        self.pokemon_label = ttk.Label(display_frame, text="", style='Subheader.TLabel', cursor="hand2")
        self.pokemon_label.pack()
        self.pokemon_label.bind("<Button-1>", lambda e: self.change_pokemon())

        self.number_label = ttk.Label(display_frame, text="", style='Subheader.TLabel')
        self.number_label.pack(pady=5)

        control_frame = ttk.Frame(left_panel, style='Card.TFrame', padding=10)
        control_frame.pack(fill=tk.X, pady=5)

        game_frame = ttk.Frame(control_frame)
        game_frame.pack(fill=tk.X, pady=5)
        ttk.Label(game_frame, text="Game:").pack(side=tk.LEFT)
        game_menu = ttk.OptionMenu(game_frame, self.current_game, *Config.POKEMON_GAMES.keys())
        game_menu.pack(side=tk.LEFT, padx=5)

        method_frame = ttk.Frame(control_frame)
        method_frame.pack(fill=tk.X, pady=5)
        ttk.Label(method_frame, text="Method:").pack(side=tk.LEFT)
        method_menu = ttk.OptionMenu(method_frame, self.current_method, *Config.HUNT_METHODS)
        method_menu.pack(side=tk.LEFT, padx=5)

        adjust_frame = ttk.Frame(control_frame)
        adjust_frame.pack(fill=tk.X, pady=5)
        ttk.Label(adjust_frame, text="Adjust by:").pack(side=tk.LEFT)
        self.amount_entry = ttk.Entry(adjust_frame, width=5)
        self.amount_entry.pack(side=tk.LEFT, padx=5)
        self.amount_entry.insert(0, "1")

        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill=tk.X, pady=5)
        ttk.Button(button_frame, text="+", command=lambda: self.adjust_number("increase")).pack(side=tk.LEFT,
                                                                                                expand=True)
        ttk.Button(button_frame, text="-", command=lambda: self.adjust_number("decrease")).pack(side=tk.LEFT,
                                                                                                expand=True)
        ttk.Button(button_frame, text="Reset", command=lambda: self.adjust_number("reset"),
                   style='Secondary.TButton').pack(side=tk.LEFT, expand=True)

        hunts_panel = ttk.Frame(main_frame, style='Card.TFrame')
        hunts_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        header_frame = ttk.Frame(hunts_panel)
        header_frame.pack(fill=tk.X, pady=5)
        ttk.Label(header_frame, text="Shiny Hunts", style='Header.TLabel').pack(side=tk.LEFT)

        sort_frame = ttk.Frame(header_frame)
        sort_frame.pack(side=tk.RIGHT, padx=5)
        ttk.Combobox(sort_frame, textvariable=self.sort_by, values=["most_recent", "most_encounters"], width=15,
                     state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Combobox(sort_frame, textvariable=self.sort_order, values=["ascending", "descending"], width=12,
                     state="readonly").pack(side=tk.LEFT, padx=2)
        self.sort_by.trace_add('write', lambda *args: self.update_hunts_panel())
        self.sort_order.trace_add('write', lambda *args: self.update_hunts_panel())

        self.hunts_canvas = tk.Canvas(hunts_panel, bg=Config.COLORS[self.current_theme]['card_bg'],
                                      highlightthickness=0)
        self.hunts_scrollbar = ttk.Scrollbar(hunts_panel, orient="vertical", command=self.hunts_canvas.yview)
        self.hunts_frame = ttk.Frame(self.hunts_canvas, padding=10)
        self.hunts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hunts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hunts_canvas.create_window((0, 0), window=self.hunts_frame, anchor="nw")
        self.hunts_canvas.configure(yscrollcommand=self.hunts_scrollbar.set)
        self.hunts_frame.bind("<Configure>", self.on_hunts_frame_configure)
        self.hunts_canvas.bind("<Configure>", self.on_canvas_configure)
        self.hunts_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Hunt", command=self.change_pokemon)
        file_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        file_menu.add_command(label="Run Melon Script", command=self.run_melon_script)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def run_melon_script(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            script_path = os.path.join(base_dir, "melon.py")
            subprocess.Popen([sys.executable, script_path])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run melon.py: {str(e)}")

    def on_mousewheel(self, event):
        self.hunts_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def load_data(self):
        try:
            if os.path.exists(self.storage_file):
                with open(self.storage_file, 'r') as f:
                    loaded_data = json.load(f)
                    pokemon_dict = {}
                    for k, v in loaded_data.get('pokemon', {}).items():
                        try:
                            pokemon_dict[k] = PokemonData(**v)
                        except Exception as e:
                            print(f"Skipping invalid Pokémon entry {k}: {e}")
                    self.saved_data = AppData(
                        pokemon=pokemon_dict,
                        active_hunts=loaded_data.get('active_hunts', []),
                        last_pokemon=loaded_data.get('last_pokemon'),
                        theme=loaded_data.get('theme', 'light'),
                        sort_by=loaded_data.get('sort_by', 'most_recent'),
                        sort_order=loaded_data.get('sort_order', 'descending')
                    )
                    self.current_theme = self.saved_data.theme
                    self.sort_by.set(self.saved_data.sort_by)
                    self.sort_order.set(self.saved_data.sort_order)
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON data: {e}")
            self.saved_data = AppData(pokemon={})
        except Exception as e:
            messagebox.showerror("Error", f"Could not load data: {e}")
            self.saved_data = AppData(pokemon={})

    def save_data(self) -> None:
        try:
            self.saved_data.sort_by = self.sort_by.get()
            self.saved_data.sort_order = self.sort_order.get()
            data = {
                "pokemon": {k: asdict(v) for k, v in self.saved_data.pokemon.items()},
                "active_hunts": self.saved_data.active_hunts,
                "last_pokemon": self.saved_data.last_pokemon,
                "theme": self.saved_data.theme,
                "sort_by": self.saved_data.sort_by,
                "sort_order": self.saved_data.sort_order
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, default=str)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save data: {e}")

    def load_pokemon(self, pokemon_name: str) -> None:
        try:
            pokemon_name = pokemon_name.lower()
            self.current_pokemon = pokemon_name

            if self.current_pokemon in self.saved_data.pokemon:
                data = self.saved_data.pokemon[self.current_pokemon]
                self.current_number = data.encounters
                self.default_adjustment = data.adjustment
                if data.game:
                    self.current_game.set(data.game)
                if data.method:
                    self.current_method.set(data.method)
                if pokemon_name not in self.saved_data.active_hunts:
                    self.saved_data.active_hunts.append(pokemon_name)

            self.update_display()
            self.load_pokemon_image(pokemon_name, size=Config.MAIN_SPRITE_SIZE)
            self.update_hunts_panel()
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't load Pokémon: {e}")

    def load_pokemon_image(self, pokemon_name: str, size=Config.MAIN_SPRITE_SIZE):
        try:
            cache_file = CACHE_DIR / f"{pokemon_name.lower()}_{size[0]}x{size[1]}.png"

            # Check if we have a cached file
            if cache_file.exists():
                # Open local file directly
                img = Image.open(cache_file)
            else:
                # Fetch from API if not cached
                response = requests.get(f"{Config.API_BASE_URL}/pokemon/{pokemon_name.lower()}")
                data = response.json()
                sprite_url = data['sprites']['front_shiny'] or data['sprites']['front_default']
                response = requests.get(sprite_url)
                img = Image.open(BytesIO(response.content))
                img = img.resize(size, Image.Resampling.LANCZOS)
                img.save(cache_file)

            photo_img = ImageTk.PhotoImage(img)
            self.image_references.append(photo_img)
            self.pokemon_label.config(image=photo_img)
            self.pokemon_label.image = photo_img

            # Store the local path, not URL
            if self.current_pokemon in self.saved_data.pokemon:
                self.saved_data.pokemon[self.current_pokemon].sprite_url = str(cache_file)
        except Exception as e:
            print(f"Error loading image: {e}")
            response = requests.get(DEFAULT_SPRITE_URL)
            img = Image.open(BytesIO(response.content)).resize(size, Image.Resampling.LANCZOS)
            photo_img = ImageTk.PhotoImage(img)
            self.image_references.append(photo_img)
            self.pokemon_label.config(image=photo_img)
            self.pokemon_label.image = photo_img

    def change_pokemon(self):
        popup = tk.Toplevel(self.root)
        popup.title("Select Pokémon")
        popup.geometry("300x400")

        search_frame = ttk.Frame(popup)
        search_frame.pack(fill=tk.X, padx=5, pady=5)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var)
        search_entry.pack(fill=tk.X)
        search_entry.focus_set()

        list_frame = ttk.Frame(popup)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(list_frame)
        colors = Config.COLORS[self.current_theme]
        pokemon_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                  bg=colors['card_bg'], fg=colors['text_primary'])
        scrollbar.config(command=pokemon_list.yview)
        pokemon_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        current_gen = Config.POKEMON_GAMES.get(self.current_game.get(), 9)
        all_pokemon = []
        for gen in range(1, current_gen + 1):
            try:
                response = requests.get(f"{Config.API_BASE_URL}/generation/{gen}")
                data = response.json()
                all_pokemon.extend(p['name'].capitalize() for p in data['pokemon_species'])
            except:
                gen_range = {
                    1: (1, 151), 2: (152, 251), 3: (252, 386),
                    4: (387, 493), 5: (494, 649), 6: (650, 721),
                    7: (722, 809), 8: (810, 905), 9: (906, 1025)
                }.get(gen, (1, 151))
                all_pokemon.extend(f"Pokémon {i}" for i in range(gen_range[0], gen_range[1] + 1))

        for pokemon in sorted(set(all_pokemon)):
            pokemon_list.insert(tk.END, pokemon)

        def update_list(*args):
            search_term = search_var.get().lower()
            pokemon_list.delete(0, tk.END)
            for pokemon in all_pokemon:
                if search_term in pokemon.lower():
                    pokemon_list.insert(tk.END, pokemon)

        search_var.trace_add('write', update_list)

        def on_select():
            try:
                selection = pokemon_list.get(pokemon_list.curselection())
                popup.destroy()
                self.load_pokemon(selection)  # Changed from load_pokemon_image to load_pokemon
                if selection not in self.saved_data.active_hunts:
                    self.saved_data.active_hunts.append(selection)
                self.save_data()
            except:
                messagebox.showwarning("No Selection", "Please select a Pokémon")

        button_frame = ttk.Frame(popup)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        ttk.Button(button_frame, text="Cancel", command=popup.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Select", command=on_select, style='Secondary.TButton').pack(side=tk.RIGHT)

    def adjust_number(self, action: str):
        if not self.current_pokemon:
            if not self.saved_data.active_hunts:
                self.change_pokemon()
                return
            self.load_pokemon(self.saved_data.active_hunts[0])

        try:
            amount = int(self.amount_entry.get())
        except ValueError:
            amount = 1

        if action == "increase":
            self.current_number += amount
        elif action == "decrease":
            self.current_number = max(0, self.current_number - amount)
        elif action == "reset":
            self.current_number = 0

        self.update_display()
        self.save_pokemon_data()
        self.update_hunts_panel()

    def save_pokemon_data(self) -> None:
        if not self.current_pokemon:
            return

        adjustment = int(self.amount_entry.get()) if self.amount_entry.get().isdigit() else 1

        if self.current_pokemon not in self.saved_data.pokemon:
            self.saved_data.pokemon[self.current_pokemon] = PokemonData(
                name=self.current_pokemon,
                encounters=self.current_number,
                adjustment=adjustment,
                game=self.current_game.get(),
                method=self.current_method.get(),
                last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status="ACTIVE"  # Using string directly
            )
        else:
            data = self.saved_data.pokemon[self.current_pokemon]
            data.encounters = self.current_number
            data.adjustment = adjustment
            data.game = self.current_game.get()
            data.method = self.current_method.get()
            data.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.save_data()

    def update_display(self):
        if not self.current_pokemon:
            return

        formatted_number = "{:,}".format(self.current_number)
        display_text = f"Encounters: {formatted_number}"

        if self.current_pokemon in self.saved_data.pokemon:
            pokemon_data = self.saved_data.pokemon[self.current_pokemon]
            if pokemon_data.method:
                odds = self.calculate_shiny_odds(pokemon_data)
                probability = 1 - ((odds - 1) / odds) ** self.current_number
                display_text += f"\nShiny Chance: {probability:.2%} (1/{odds:,})"

        self.number_label.config(text=display_text)

    def calculate_shiny_odds(self, pokemon_data: PokemonData) -> int:
        base_odds = 4096
        if pokemon_data.game and pokemon_data.game in Config.POKEMON_GAMES:
            generation = Config.POKEMON_GAMES[pokemon_data.game]
            if generation <= 5:
                base_odds = 8192

        method = pokemon_data.method if pokemon_data.method else "Full Odds"
        if method == "Shiny Charm":
            return base_odds // 3
        elif method == "Masuda Method":
            return base_odds // 6 if base_odds == 4096 else base_odds // 5
        elif method == "Masuda + Charm":
            return base_odds // 8 if base_odds == 4096 else base_odds // 6
        return base_odds

    def on_canvas_configure(self, event):
        self.update_hunts_panel()

    def on_hunts_frame_configure(self, event):
        self.hunts_canvas.configure(scrollregion=self.hunts_canvas.bbox("all"))

    def calculate_columns(self):
        canvas_width = self.hunts_canvas.winfo_width()
        columns = max(Config.MIN_COLUMNS, min(Config.MAX_COLUMNS, canvas_width // Config.CARD_MIN_WIDTH))
        return columns

    def update_hunts_panel(self):
        for widget in self.hunts_frame.winfo_children():
            widget.destroy()

        if not self.saved_data.pokemon:
            ttk.Label(self.hunts_frame, text="No shiny hunts yet").pack()
            return

        columns = self.calculate_columns()
        hunts = sorted(self.saved_data.pokemon.values(), key=self.get_sort_key, reverse=self.sort_order.get() == "descending")

        row = col = 0
        for idx, data in enumerate(hunts):
            card = self.create_hunt_card(data.name, data)
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            col += 1
            if col >= columns:
                col = 0
                row += 1

        for c in range(columns):
            self.hunts_frame.grid_columnconfigure(c, weight=1)

    def get_sort_key(self, data):
        if self.sort_by.get() == "most_recent":
            return datetime.strptime(data.last_updated, "%Y-%m-%d %H:%M:%S") if data.last_updated else datetime.min
        return data.encounters

    def create_hunt_card(self, pokemon_name: str, pokemon_data: PokemonData):
        card = ttk.Frame(self.hunts_frame, style='Card.TFrame', padding=10)
        colors = Config.COLORS[self.current_theme]  # Get current theme colors

        status = pokemon_data.status
        status_color = {
            "COMPLETE": colors['complete'],
            "PAUSED": colors['paused'],
            "ACTIVE": colors['primary']
        }.get(status)

        # Header frame
        header = ttk.Frame(card)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Image label
        img_frame = ttk.Frame(card)
        img_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        try:
            if pokemon_data.sprite_url and os.path.exists(pokemon_data.sprite_url):
                img = Image.open(pokemon_data.sprite_url)
            else:
                response = requests.get(DEFAULT_SPRITE_URL)
                img = Image.open(BytesIO(response.content))

            img = img.resize(Config.CARD_SPRITE_SIZE, Image.Resampling.LANCZOS)
            photo_img = ImageTk.PhotoImage(img)
            self.image_references.append(photo_img)
            img_label = ttk.Label(img_frame, image=photo_img)
            img_label.image = photo_img
            img_label.pack()
        except Exception as e:
            print(f"Error loading card image: {e}")

        # Name and status
        name_frame = ttk.Frame(header)
        name_frame.pack(side=tk.LEFT)
        ttk.Label(name_frame, text=pokemon_name.capitalize(), font=('Arial', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Label(name_frame, text=f"• {status}", foreground=status_color).pack(side=tk.LEFT, padx=5)

        # Details frame
        details = ttk.Frame(card)
        details.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        formatted_number = "{:,}".format(pokemon_data.encounters)
        ttk.Label(details, text=f"Encounters: {formatted_number}").grid(row=0, column=0, sticky="w")

        if pokemon_data.method:
            odds = self.calculate_shiny_odds(pokemon_data)
            probability = 1 - ((odds - 1) / odds) ** pokemon_data.encounters
            ttk.Label(details, text=f"Shiny Chance: {probability:.2%} (1/{odds:,})").grid(row=1, column=0, sticky="w")

        if pokemon_data.game:
            ttk.Label(details, text=f"Game: {pokemon_data.game}").grid(row=2, column=0, sticky="w")

        # Show found date if completed, otherwise don't show anything
        if status == "COMPLETE" and pokemon_data.found_date:
            ttk.Label(details, text=f"Found: {pokemon_data.found_date}").grid(row=3, column=0, sticky="w")

        # Buttons frame
        buttons = ttk.Frame(card)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")

        ttk.Button(buttons, text="Load", command=lambda p=pokemon_name: self.load_pokemon(p), width=8).grid(row=0,
                                                                                                            column=0,
                                                                                                            padx=2)
        ttk.Button(buttons, text="Notes", command=lambda p=pokemon_name: self.add_notes(p), style='Secondary.TButton',
                   width=8).grid(row=0, column=1, padx=2)
        ttk.Button(buttons, text="✓" if status == "COMPLETE" else "▶",
                   command=lambda p=pokemon_name: self.toggle_hunt_status(p),
                   style='Success.TButton' if status == "COMPLETE" else 'TButton',
                   width=8).grid(row=0, column=2, padx=2)

        return card

    def toggle_hunt_status(self, pokemon_name: str):
        pokemon_name = pokemon_name.lower()
        if pokemon_name in self.saved_data.pokemon:
            current_status = self.saved_data.pokemon[pokemon_name].status
            new_status = "COMPLETE" if current_status != "COMPLETE" else "ACTIVE"
            self.saved_data.pokemon[pokemon_name].status = new_status

            if new_status == "COMPLETE" and not self.saved_data.pokemon[pokemon_name].found_date:
                self.saved_data.pokemon[pokemon_name].found_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.save_data()

            if new_status == "ACTIVE":
                if pokemon_name not in self.saved_data.active_hunts:
                    self.saved_data.active_hunts.append(pokemon_name)
            else:
                if pokemon_name in self.saved_data.active_hunts:
                    self.saved_data.active_hunts.remove(pokemon_name)

            self.save_data()
            self.update_hunts_panel()

    def add_notes(self, pokemon_name: str):
        current_notes = self.saved_data.pokemon[pokemon_name].notes if pokemon_name in self.saved_data.pokemon else ""
        notes = simpledialog.askstring("Add Notes", f"Notes for {pokemon_name}:", initialvalue=current_notes, parent=self.root)
        if notes is not None:
            self.saved_data.pokemon[pokemon_name].notes = notes
            self.save_data()
            self.update_hunts_panel()

    def initialize_communication_files(self) -> None:
        for filepath in self.communication_files.values():
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:  # Added encoding
                    f.write("16" if "emulator_count" in filepath else "0")

    def setup_file_watcher(self):
        self.check_emulator_count()
        self.check_encounter_trigger()
        self.root.after(500, self.setup_file_watcher)

    def check_emulator_count(self):
        try:
            with open(self.communication_files['emulator_count'], 'r') as f:
                new_value = f.read().strip()
                current_value = self.amount_entry.get()
                if new_value.isdigit() and new_value != current_value:
                    self.amount_entry.delete(0, tk.END)
                    self.amount_entry.insert(0, new_value)
        except Exception as e:
            print(f"Error reading emulator count: {e}")

    def check_encounter_trigger(self):
        try:
            mod_time = os.path.getmtime(self.communication_files['encounter_trigger'])
            if mod_time > self.last_trigger_time:
                self.last_trigger_time = mod_time
                if hasattr(self, 'initial_load') and not self.initial_load:  # Safe check
                    self.adjust_number("increase")
        except Exception as e:
            print(f"Error checking encounter trigger: {e}")
        finally:
            if hasattr(self, 'initial_load'):
                self.initial_load = False

    def export_data(self) -> None:
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:  # Added encoding
                data = asdict(self.saved_data)
                data['pokemon'] = {k: asdict(v) for k, v in data['pokemon'].items()}
                json.dump(data, f, indent=4)
            messagebox.showinfo("Success", "Data exported successfully")

    def import_data(self):
        file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'r') as f:
                imported_data = json.load(f)

            choice = messagebox.askyesno("Import Options", "Merge with existing data? (No will overwrite all data)")
            if choice:
                for name, data in imported_data.get('pokemon', {}).items():
                    self.saved_data.pokemon[name] = PokemonData(**data)
                self.saved_data.active_hunts = list(set(self.saved_data.active_hunts + imported_data.get('active_hunts', [])))
            else:
                self.saved_data = AppData(**imported_data)

            self.save_data()
            self.update_hunts_panel()
            messagebox.showinfo("Success", "Data imported successfully")


if __name__ == "__main__":
    root = tk.Tk()
    app = ShinyCounter(root)
    root.mainloop()