import time
import tkinter as tk
from collections import deque
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
from enum import Enum

# Constants
CACHE_DIR = Path("cache/sprites")
DATA_FILE = "shiny_counter_data.json"
DEFAULT_SPRITE_URL = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/0.png"


class HuntStatus(Enum):
    ACTIVE = "Active"
    COMPLETE = "Complete"
    PAUSED = "Paused"


@dataclass
class PokemonData:
    name: str
    encounters: int = 0
    adjustment: int = 1
    sprite_url: Optional[str] = None
    last_updated: Optional[str] = None
    status: HuntStatus = HuntStatus.ACTIVE
    found_date: Optional[str] = None
    game: Optional[str] = None
    notes: Optional[str] = None
    method: Optional[str] = None
    shiny_chance: Optional[float] = None


@dataclass
class RouteData:
    name: str
    game: str
    location: str
    method: str
    encounters: int = 0
    pokemon: Dict[str, float] = None  # {pokemon_name: encounter_rate}
    status: HuntStatus = HuntStatus.ACTIVE
    last_updated: Optional[str] = None


@dataclass
class AppData:
    pokemon: Dict[str, PokemonData]
    routes: Dict[str, RouteData] = None
    active_hunts: List[str] = None
    last_pokemon: Optional[str] = None

    def __post_init__(self):
        if self.routes is None:
            self.routes = {}
        if self.active_hunts is None:
            self.active_hunts = []


class Config:
    API_BASE_URL = "https://pokeapi.co/api/v2"
    MAIN_SPRITE_SIZE = (150, 150)  # For main display
    CARD_SPRITE_SIZE = (80, 80)  # For hunt cards
    MINI_SPRITE_SIZE = (40, 40)  # For compact displays
    COLUMNS = 2

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

    ENCOUNTER_METHODS = {
        "Grass": "Land",
        "Surfing": "Water",
        "Fishing": "Water",
        "Headbutt": "Headbutt",
        "Cave": "Cave",
        "Special": "Special"
    }

    COLORS = {
        'primary': '#3D7DCA',
        'secondary': '#FFCB05',
        'background': '#f0f8ff',
        'card_bg': '#ffffff',
        'text_primary': '#2C3E50',
        'text_secondary': '#7F8C8D',
        'border': '#BDC3C7',
        'highlight': '#D6EAF8',
        'complete': '#2ECC71',
        'paused': '#E74C3C'
    }


class ShinyCounter:
    def __init__(self, root):
        self.root = root
        self.root.title("Pokémon Shiny Hunter")
        self.root.geometry("1000x600")
        self.root.minsize(800, 500)

        self.storage_file = DATA_FILE
        self.saved_data = AppData(pokemon={})
        self.current_pokemon = ""
        self.current_number = 0
        self.default_adjustment = 1
        self.current_game = tk.StringVar()
        self.current_method = tk.StringVar(value=Config.HUNT_METHODS[0])
        self.image_references = []

        self.current_route = tk.StringVar()
        self.route_method = tk.StringVar()
        self.route_pokemon = {}

        self.communication_files = {
            'emulator_count': "melon_emulator_count.txt",
            'encounter_trigger': "encounter_trigger.txt"
        }
        self.last_trigger_time = 0

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

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background=Config.COLORS['background'])
        style.configure('Card.TFrame', background=Config.COLORS['card_bg'], borderwidth=1, relief=tk.RAISED)
        style.configure('TButton', font=('Arial', 10), padding=6, background=Config.COLORS['primary'], foreground='white')
        style.map('TButton', background=[('active', Config.COLORS['primary'])])
        style.configure('Secondary.TButton', background=Config.COLORS['secondary'], foreground=Config.COLORS['text_primary'])
        style.configure('Success.TButton', background=Config.COLORS['complete'], foreground='white')
        style.configure('Danger.TButton', background=Config.COLORS['paused'], foreground='white')
        style.configure('TEntry', fieldbackground=Config.COLORS['card_bg'], foreground=Config.COLORS['text_primary'])
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'), foreground=Config.COLORS['primary'])
        style.configure('Subheader.TLabel', font=('Arial', 12), foreground=Config.COLORS['text_primary'])

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

        route_frame = ttk.Frame(control_frame)
        route_frame.pack(fill=tk.X, pady=5)

        ttk.Label(route_frame, text="Route:").pack(side=tk.LEFT)
        self.route_selector = ttk.Combobox(route_frame, textvariable=self.current_route)
        self.route_selector.pack(side=tk.LEFT, padx=5)
        ttk.Button(route_frame, text="New Route", command=self.setup_route).pack(side=tk.LEFT)

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
        ttk.Button(button_frame, text="+", command=lambda: self.adjust_number("increase")).pack(side=tk.LEFT, expand=True)
        ttk.Button(button_frame, text="-", command=lambda: self.adjust_number("decrease")).pack(side=tk.LEFT, expand=True)
        ttk.Button(button_frame, text="Reset", command=lambda: self.adjust_number("reset"), style='Secondary.TButton').pack(side=tk.LEFT, expand=True)

        hunts_panel = ttk.Frame(main_frame, style='Card.TFrame')
        hunts_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        ttk.Label(hunts_panel, text="Shiny Hunts", style='Header.TLabel').pack(pady=5)
        self.hunts_canvas = tk.Canvas(hunts_panel, bg=Config.COLORS['card_bg'], highlightthickness=0)
        self.hunts_scrollbar = ttk.Scrollbar(hunts_panel, orient="vertical", command=self.hunts_canvas.yview)
        self.hunts_frame = ttk.Frame(self.hunts_canvas, padding=10)
        self.hunts_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.hunts_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hunts_canvas.create_window((0, 0), window=self.hunts_frame, anchor="nw")
        self.hunts_canvas.configure(yscrollcommand=self.hunts_scrollbar.set)
        self.hunts_frame.bind("<Configure>", lambda e: self.hunts_canvas.configure(scrollregion=self.hunts_canvas.bbox("all")))
        self.hunts_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Hunt", command=self.change_pokemon)
        file_menu.add_command(label="Export Data", command=self.export_data)
        file_menu.add_command(label="Import Data", command=self.import_data)
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
                            if 'status' in v:
                                # Handle both old string format and new value format
                                status_str = v['status']
                                if status_str.startswith('HuntStatus.'):
                                    status_str = status_str.split('.')[
                                        1]  # Extract "COMPLETE" from "HuntStatus.COMPLETE"
                                v['status'] = HuntStatus[status_str]
                            else:
                                v['status'] = HuntStatus.COMPLETE if v.get('complete', False) else HuntStatus.ACTIVE
                            pokemon_dict[k] = PokemonData(**v)
                        except Exception as e:
                            print(f"Skipping invalid Pokémon entry {k}: {e}")
                    self.saved_data = AppData(
                        pokemon=pokemon_dict,
                        active_hunts=loaded_data.get('active_hunts', []),
                        last_pokemon=loaded_data.get('last_pokemon')
                    )
        except json.JSONDecodeError as e:
            messagebox.showerror("Error", f"Invalid JSON data: {e}")
            self.saved_data = AppData(pokemon={})
        except Exception as e:
            messagebox.showerror("Error", f"Could not load data: {e}")
            self.saved_data = AppData(pokemon={})

    def save_data(self):
        try:
            active_hunts = [name for name, data in self.saved_data.pokemon.items()
                            if data.status == HuntStatus.ACTIVE]
            data = {
                "pokemon": {k: asdict(v) for k, v in self.saved_data.pokemon.items()},
                "active_hunts": active_hunts,
                "last_pokemon": self.saved_data.last_pokemon
            }

            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=4, default=str)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save data: {e}")

    def load_pokemon(self, pokemon_name: str):
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
        pokemon_list = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, bg=Config.COLORS['card_bg'], fg=Config.COLORS['text_primary'])
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

    def save_pokemon_data(self):
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
                status=HuntStatus.ACTIVE
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

    def update_hunts_panel(self):
        for widget in self.hunts_frame.winfo_children():
            widget.destroy()

        if not self.saved_data.pokemon:
            ttk.Label(self.hunts_frame, text="No shiny hunts yet").pack()
            return

        # Grid layout with 2 columns
        row = col = 0
        for idx, (name, data) in enumerate(sorted(
                self.saved_data.pokemon.items(),
                key=lambda x: x[1].encounters,
                reverse=True
        )):
            card = self.create_hunt_card(name, data)
            card.grid(
                row=row,
                column=col,
                padx=5,
                pady=5,
                sticky="nsew"
            )

            col += 1
            if col >= Config.COLUMNS:
                col = 0
                row += 1

        # Configure grid weights
        for c in range(Config.COLUMNS):
            self.hunts_frame.grid_columnconfigure(c, weight=1)

    def create_hunt_card(self, pokemon_name: str, pokemon_data: PokemonData):
        card = ttk.Frame(self.hunts_frame, style='Card.TFrame', padding=10)

        status = HuntStatus(pokemon_data.status)
        status_color = {
            HuntStatus.COMPLETE: Config.COLORS['complete'],
            HuntStatus.PAUSED: Config.COLORS['paused'],
            HuntStatus.ACTIVE: Config.COLORS['primary']
        }.get(status)

        # Header frame
        header = ttk.Frame(card)
        header.grid(row=0, column=0, columnspan=2, sticky="ew")

        # Image label
        img_frame = ttk.Frame(card)
        img_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        try:
            # Check if we have a local cached file
            if pokemon_data.sprite_url and os.path.exists(pokemon_data.sprite_url):
                # Load from local file
                img = Image.open(pokemon_data.sprite_url)
            else:
                # Fall back to default URL
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
        ttk.Label(name_frame, text=f"• {status.value}", foreground=status_color).pack(side=tk.LEFT, padx=5)

        # Details frame
        details = ttk.Frame(card)
        details.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        if pokemon_data.method:
            odds = self.calculate_shiny_odds(pokemon_data)
            probability = 1 - ((odds - 1) / odds) ** pokemon_data.encounters
            ttk.Label(details, text=f"Shiny Chance: {probability:.2%} (1/{odds:,})").grid(row=0, column=0, sticky="w")

        if pokemon_data.game:
            ttk.Label(details, text=f"Game: {pokemon_data.game}").grid(row=1, column=0, sticky="w")

        if pokemon_data.notes:
            ttk.Label(details, text=f"Notes: {pokemon_data.notes}").grid(row=2, column=0, sticky="w")

        # Buttons frame
        buttons = ttk.Frame(card)
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew")

        ttk.Button(buttons, text="Load", command=lambda p=pokemon_name: self.load_pokemon(p), width=8).grid(row=0,
                                                                                                            column=0,
                                                                                                            padx=2)
        ttk.Button(buttons, text="Notes", command=lambda p=pokemon_name: self.add_notes(p), style='Secondary.TButton',
                   width=8).grid(row=0, column=1, padx=2)
        ttk.Button(buttons, text="✓" if status == HuntStatus.COMPLETE else "▶",
                   command=lambda p=pokemon_name: self.toggle_hunt_status(p),
                   style='Success.TButton' if status == HuntStatus.COMPLETE else 'TButton',
                   width=8).grid(row=0, column=2, padx=2)

        return card

    def toggle_hunt_status(self, pokemon_name: str):
        pokemon_name = pokemon_name.lower()
        if pokemon_name in self.saved_data.pokemon:
            current_status = self.saved_data.pokemon[pokemon_name].status
            new_status = HuntStatus.COMPLETE if current_status != HuntStatus.COMPLETE else HuntStatus.ACTIVE
            self.saved_data.pokemon[pokemon_name].status = new_status
            self.save_data()

            # Update active hunts list
            if new_status == HuntStatus.ACTIVE:
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

    def initialize_communication_files(self):
        for filepath in self.communication_files.values():
            if not os.path.exists(filepath):
                with open(filepath, 'w') as f:
                    f.write("16" if "emulator_count" in filepath else "0")

    def setup_file_watcher(self):
        self.check_emulator_count()
        self.check_encounter_trigger()
        self.root.after(500, self.setup_file_watcher)

    def setup_route(self):
        popup = tk.Toplevel(self.root)
        popup.title("New Route Setup")

        # Route configuration inputs
        ttk.Label(popup, text="Location Name:").grid(row=0, column=0)
        loc_entry = ttk.Entry(popup)
        loc_entry.grid(row=0, column=1)

        ttk.Label(popup, text="Game Version:").grid(row=1, column=0)
        game_combo = ttk.Combobox(popup, values=list(Config.POKEMON_GAMES.keys()))
        game_combo.grid(row=1, column=1)

        ttk.Label(popup, text="Encounter Method:").grid(row=2, column=0)
        method_combo = ttk.Combobox(popup, values=list(Config.ENCOUNTER_METHODS.keys()))
        method_combo.grid(row=2, column=1)

        def create_route():
            location = loc_entry.get()
            game = game_combo.get()
            method = method_combo.get()

            if not all([location, game, method]):
                messagebox.showerror("Error", "All fields are required")
                return

            try:
                # Fetch encounter data from PokeAPI
                encounters = self.get_route_encounters(location, game)
                route_name = f"{location} ({method})"

                self.saved_data.routes[route_name] = RouteData(
                    name=route_name,
                    game=game,
                    location=location,
                    method=method,
                    pokemon=encounters
                )
                self.current_route.set(route_name)
                self.update_route_display()
                popup.destroy()
            except Exception as e:
                messagebox.showerror("API Error", f"Failed to get encounters: {str(e)}")

        ttk.Button(popup, text="Create", command=create_route).grid(row=3, columnspan=2)

    def get_route_encounters(self, location, game):
        # Get location data from PokeAPI
        response = requests.get(f"{Config.API_BASE_URL}/location-area/{location.lower()}")
        data = response.json()

        encounters = {}
        for encounter in data.get('pokemon_encounters', []):
            for version in encounter.get('version_details', []):
                if version.get('version', {}).get('name') == game.lower():
                    encounters[encounter['pokemon']['name']] = version.get('chance', 0)

        return encounters

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
                if not self.initial_load:  # Only adjust if not initial load
                    self.adjust_number("increase")
        except Exception as e:
            print(f"Error checking encounter trigger: {e}")
        finally:
            self.initial_load = False  # Set to False after first check

    def export_data(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if file_path:
            with open(file_path, 'w') as f:
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