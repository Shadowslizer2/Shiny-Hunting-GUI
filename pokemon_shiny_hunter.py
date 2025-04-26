import customtkinter as ctk
import tkinter as tk
from tkinter import simpledialog, messagebox, filedialog
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
    status: str = "ACTIVE"  # Can be ACTIVE, COMPLETE, PAUSED, or PHASE
    found_date: Optional[str] = None
    game: Optional[str] = None
    notes: Optional[str] = None
    method: Optional[str] = None
    phase: int = 1
    target: Optional[str] = None


@dataclass
class AppData:
    pokemon: Dict[str, PokemonData]
    active_hunts: List[str] = None
    last_pokemon: Optional[str] = None
    theme: str = "dark"
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
        self.current_game = ctk.StringVar()
        self.current_method = ctk.StringVar(value=Config.HUNT_METHODS[0])
        self.image_references = []
        self.current_theme = "dark"
        self.sort_by = ctk.StringVar(value="most_recent")
        self.sort_order = ctk.StringVar(value="descending")
        self.current_filter = ctk.StringVar(value="all")

        self.communication_files = {
            'emulator_count': "melon_emulator_count.txt",
            'encounter_trigger': "encounter_trigger.txt"
        }
        self.last_trigger_time = 0
        self.initial_load = True
        self.hunt_cards = {}  # Dictionary to track hunt cards
        self.resize_job = None

        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self.load_data()
        self.set_theme(self.saved_data.theme)
        self.create_widgets()
        self.initialize_communication_files()
        self.setup_file_watcher()
        self.load_most_recent_active_hunt()
        self.initial_load = True

    def set_theme(self, theme):
        self.current_theme = theme
        ctk.set_appearance_mode(theme)
        self.saved_data.theme = theme

    def load_most_recent_active_hunt(self):
        try:
            # Get all active hunts sorted by last_updated
            active_hunts = [
                p for p in self.saved_data.pokemon.values()
                if p.status == "ACTIVE"
            ]

            # Sort by last_updated descending
            active_hunts.sort(
                key=lambda x: datetime.strptime(x.last_updated,
                                                "%Y-%m-%d %H:%M:%S") if x.last_updated else datetime.min,
                reverse=True
            )

            if active_hunts:
                most_recent = active_hunts[0].name
                self.load_pokemon(most_recent)
            elif self.saved_data.last_pokemon and self.saved_data.last_pokemon in self.saved_data.pokemon:
                self.load_pokemon(self.saved_data.last_pokemon)

        except Exception as e:
            print(f"Error loading recent hunt: {e}")

    def on_close(self):
        self.saved_data.last_pokemon = self.current_pokemon
        self.save_data()
        self.root.destroy()

    def create_widgets(self):
        # Main frame with proper background
        self.main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Left panel with background matching theme
        left_panel = ctk.CTkFrame(self.main_frame, width=400, corner_radius=0)
        left_panel.pack(side="left", fill="y", padx=0, pady=0)

        # Display frame
        display_frame = ctk.CTkFrame(left_panel, corner_radius=0)
        display_frame.pack(fill="x", pady=5, padx=0)

        self.pokemon_label = ctk.CTkLabel(display_frame, text="", cursor="hand2")
        self.pokemon_label.pack()
        self.pokemon_label.bind("<Button-1>", lambda e: self.change_pokemon())

        self.number_label = ctk.CTkLabel(display_frame, text="")
        self.number_label.pack(pady=5)

        # Control frame
        control_frame = ctk.CTkFrame(left_panel, corner_radius=0)
        control_frame.pack(fill="x", pady=5, padx=0)

        # Game selection
        game_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        game_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(game_frame, text="Game:").pack(side="left")
        game_menu = ctk.CTkOptionMenu(game_frame, variable=self.current_game, values=list(Config.POKEMON_GAMES.keys()))
        game_menu.pack(side="left", padx=5)

        # Method selection
        method_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        method_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(method_frame, text="Method:").pack(side="left")
        method_menu = ctk.CTkOptionMenu(method_frame, variable=self.current_method, values=Config.HUNT_METHODS)
        method_menu.pack(side="left", padx=5)

        # Adjust frame
        adjust_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        adjust_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(adjust_frame, text="Adjust by:").pack(side="left")
        self.amount_entry = ctk.CTkEntry(adjust_frame, width=50)
        self.amount_entry.pack(side="left", padx=5)
        self.amount_entry.insert(0, "1")

        # Button frame
        button_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        button_frame.pack(fill="x", pady=5)
        ctk.CTkButton(button_frame, text="+", command=lambda: self.adjust_number("increase"), width=40).pack(
            side="left", expand=True)
        ctk.CTkButton(button_frame, text="-", command=lambda: self.adjust_number("decrease"), width=40).pack(
            side="left", expand=True)
        ctk.CTkButton(button_frame, text="Reset", command=lambda: self.adjust_number("reset"), fg_color="#FFCB05",
                      text_color="#2C3E50", width=40).pack(side="left", expand=True)
        ctk.CTkButton(button_frame, text="Phase", command=lambda: self.handle_phase_input(),
                      fg_color="#FFCB05", text_color="#2C3E50", width=40).pack(side="left", expand=True)

        # Right panel (hunts) with proper background
        hunts_panel = ctk.CTkFrame(self.main_frame, corner_radius=0)
        hunts_panel.pack(side="right", fill="both", expand=True, padx=0, pady=0)

        # Header frame
        header_frame = ctk.CTkFrame(hunts_panel, fg_color="transparent")
        header_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(header_frame, text="Shiny Hunts", font=("Arial", 14, "bold")).pack(side="left")
        self.note_filter_entry = ctk.CTkEntry(header_frame, placeholder_text="Filter notes...")
        self.note_filter_entry.pack(side="right", padx=10)
        self.note_filter_entry.bind("<KeyRelease>", lambda e: self.update_hunts_panel())

        # Filter buttons
        filter_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        filter_frame.pack(side="right", padx=10)
        ctk.CTkButton(filter_frame, text="All", command=lambda: self.set_filter("all"), width=60).pack(side="left",
                                                                                                       padx=2)
        ctk.CTkButton(filter_frame, text="Active", command=lambda: self.set_filter("active"), width=60).pack(
            side="left", padx=2)
        ctk.CTkButton(filter_frame, text="Completed", command=lambda: self.set_filter("complete"), width=60).pack(
            side="left", padx=2)
        ctk.CTkButton(filter_frame, text="Phases", command=lambda: self.set_filter("phase"), width=60).pack(
            side="left", padx=2)

        # Sort controls
        sort_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        sort_frame.pack(side="right", padx=5)
        ctk.CTkComboBox(sort_frame, variable=self.sort_by, values=["most_recent", "most_encounters"], width=120,
                        state="readonly").pack(side="left", padx=2)
        ctk.CTkComboBox(sort_frame, variable=self.sort_order, values=["ascending", "descending"], width=100,
                        state="readonly").pack(side="left", padx=2)
        self.sort_by.trace_add('write', lambda *args: self.update_hunts_panel())
        self.sort_order.trace_add('write', lambda *args: self.update_hunts_panel())

        # Canvas for scrollable hunts with proper background
        self.hunts_canvas = tk.Canvas(hunts_panel, highlightthickness=0,
                                      bg="#2b2b2b" if self.current_theme == "dark" else "#f0f0f0")
        self.hunts_scrollbar = ctk.CTkScrollbar(hunts_panel, orientation="vertical", command=self.hunts_canvas.yview)
        self.hunts_frame = ctk.CTkFrame(self.hunts_canvas, fg_color="transparent")

        self.hunts_canvas.pack(side="left", fill="both", expand=True)
        self.hunts_scrollbar.pack(side="right", fill="y")
        self.hunts_canvas.create_window((0, 0), window=self.hunts_frame, anchor="nw")
        self.hunts_canvas.configure(yscrollcommand=self.hunts_scrollbar.set)

        self.hunts_frame.bind("<Configure>", self.on_hunts_frame_configure)
        self.hunts_canvas.bind("<Configure>", self.on_canvas_configure)
        self.hunts_canvas.bind_all("<MouseWheel>", self.on_mousewheel)

        # Menu
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Hunt", command=self.change_pokemon)
        file_menu.add_command(label="Toggle Theme", command=self.toggle_theme)
        file_menu.add_command(label="Run Melon Script", command=self.run_melon_script)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

    def toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.set_theme(new_theme)
        # Update canvas background color
        self.hunts_canvas.configure(bg="#f0f0f0" if new_theme == "light" else "#2b2b2b")
        self.save_data()

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
                            # Handle missing fields for backward compatibility
                            if 'phase' not in v:
                                v['phase'] = 1
                            if 'target' not in v:
                                v['target'] = None
                            pokemon_dict[k] = PokemonData(**v)
                        except Exception as e:
                            print(f"Skipping invalid Pokémon entry {k}: {e}")
                    self.saved_data = AppData(
                        pokemon=pokemon_dict,
                        active_hunts=loaded_data.get('active_hunts', []),
                        last_pokemon=loaded_data.get('last_pokemon'),
                        theme=loaded_data.get('theme', 'dark'),
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

    def save_data(self):
        try:
            self.saved_data.sort_by = self.sort_by.get()
            self.saved_data.sort_order = self.sort_order.get()
            data = {
                "pokemon": {
                    k: {
                        **asdict(v),
                        # Ensure phase and target are always included
                        "phase": getattr(v, 'phase', 1),
                        "target": getattr(v, 'target', None)
                    }
                    for k, v in self.saved_data.pokemon.items()
                },
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

    def load_pokemon(self, pokemon_name):
        base_name = pokemon_name.split(" phase ")[0].lower()
        if any(c.isdigit() for c in pokemon_name):
            phase = int(pokemon_name.split()[-1])
        else:
            phase = 1

        try:
            pokemon_name = pokemon_name.lower()
            self.current_pokemon = pokemon_name

            # Update active hunts order
            if pokemon_name in self.saved_data.active_hunts:
                self.saved_data.active_hunts.remove(pokemon_name)
            self.saved_data.active_hunts.insert(0, pokemon_name)

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

    def load_pokemon_image(self, pokemon_name, size=Config.MAIN_SPRITE_SIZE):
        # Extract base name for phases (remove " phase X" suffix)
        base_name = pokemon_name.split(" phase ")[0].lower()

        try:
            cache_file = CACHE_DIR / f"{base_name}_{size[0]}x{size[1]}.png"

            if cache_file.exists():
                img = Image.open(cache_file)
            else:
                response = requests.get(f"{Config.API_BASE_URL}/pokemon/{base_name}")
                data = response.json()
                sprite_url = data['sprites']['front_shiny'] or data['sprites']['front_default']
                response = requests.get(sprite_url)
                img = Image.open(BytesIO(response.content))
                img = img.resize(size, Image.Resampling.LANCZOS)
                img.save(cache_file)

            # Convert to CTkImage
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            self.image_references.append(ctk_img)
            self.pokemon_label.configure(image=ctk_img)
            self.pokemon_label.image = ctk_img

            if self.current_pokemon in self.saved_data.pokemon:
                self.saved_data.pokemon[self.current_pokemon].sprite_url = str(cache_file)
        except Exception as e:
            print(f"Error loading image: {e}")
            response = requests.get(DEFAULT_SPRITE_URL)
            img = Image.open(BytesIO(response.content)).resize(size, Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=size)
            self.image_references.append(ctk_img)
            self.pokemon_label.configure(image=ctk_img)
            self.pokemon_label.image = ctk_img

    def get_next_phase_number(self, target_name):
        target_name = target_name.lower()
        phases = [p for p in self.saved_data.pokemon.values()
                  if p.target and p.target.lower() == target_name]
        return len(phases) + 1

    def handle_phase(self, phased_pokemon):
        if not self.current_pokemon:
            return

        # Create new phase entry
        base_name = phased_pokemon.lower()
        # Get all phases for current target (including other targets)
        all_phases = [p for p in self.saved_data.pokemon.values()
                      if p.target and p.target.lower() == self.current_pokemon.lower()]

        # Calculate next phase number
        phase_number = len(all_phases) + 1

        new_name = f"{base_name} phase {phase_number}"

        # Create COMPLETED phase entry (never modified again)
        self.saved_data.pokemon[new_name] = PokemonData(
            name=new_name,
            encounters=self.current_number,  # Frozen at current count
            adjustment=self.default_adjustment,
            game=self.current_game.get(),
            method=self.current_method.get(),
            last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            status="COMPLETE",  # Marked complete immediately
            found_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # Save found date
            phase=phase_number,
            target=self.current_pokemon  # Links back to main hunt
        )

        # Update main hunt's phase counter only (don't reset encounters)
        if self.current_pokemon in self.saved_data.pokemon:
            current_data = self.saved_data.pokemon[self.current_pokemon]
            current_data.phase = phase_number + 1  # Increment phase counter
            current_data.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.save_data()
        self.update_hunts_panel()

    def update_hunt_card(self, pokemon_name, pokemon_data):
        card = self.hunt_cards[pokemon_name]

        # Update status
        status_color = {
            "COMPLETE": "#28a745",
            "PAUSED": "#e74c3c",
            "ACTIVE": "#3D7DCA",
            "PHASE": "#FFA500"  # Add orange color for phases
        }.get(pokemon_data.status, "#3D7DCA")
        card.status_label.configure(
            text=f"• {pokemon_data.status}",
            text_color=status_color
        )

        # Update encounters
        formatted_number = "{:,}".format(pokemon_data.encounters)
        card.encounters_label.configure(text=f"Encounters: {formatted_number}")

        # Update probability
        odds = self.calculate_shiny_odds(pokemon_data)
        probability = 1 - ((odds - 1) / odds) ** pokemon_data.encounters
        card.probability_label.configure(
            text=f"Shiny Chance: {probability:.2%} (1/{odds:,})"
        )

        # Update game
        if card.game_label:
            card.game_label.configure(text=f"Game: {pokemon_data.game}")

        # Update found date
        if card.found_date_label and pokemon_data.status == "COMPLETE":
            card.found_date_label.configure(text=f"Found: {pokemon_data.found_date}")

        # Update status button
        btn_text = "✓" if pokemon_data.status == "COMPLETE" else "▶"
        btn_fg = "#28a745" if pokemon_data.status == "COMPLETE" else "#3D7DCA"
        card.status_button.configure(text=btn_text, fg_color=btn_fg)

    def change_pokemon(self):
        popup = ctk.CTkToplevel(self.root)
        popup.title("Select Pokémon")
        popup.geometry("300x400")

        search_frame = ctk.CTkFrame(popup)
        search_frame.pack(fill="x", padx=5, pady=5)
        search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(search_frame, textvariable=search_var)
        search_entry.pack(fill="x")
        search_entry.focus_set()

        list_frame = ctk.CTkFrame(popup)
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        scrollbar = ctk.CTkScrollbar(list_frame)
        pokemon_list = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            bg="#f0f0f0" if self.current_theme == "light" else "#2b2b2b",
            fg="#000000" if self.current_theme == "light" else "#ffffff"
        )
        scrollbar.configure(command=pokemon_list.yview)
        pokemon_list.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

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
                self.load_pokemon(selection)
                if selection not in self.saved_data.active_hunts:
                    self.saved_data.active_hunts.append(selection)
                self.save_data()
            except:
                messagebox.showwarning("No Selection", "Please select a Pokémon")

        button_frame = ctk.CTkFrame(popup)
        button_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(button_frame, text="Cancel", command=popup.destroy).pack(side="right", padx=5)
        ctk.CTkButton(button_frame, text="Select", command=on_select, fg_color="#FFCB05", text_color="#2C3E50").pack(
            side="right")

    def adjust_number(self, action):
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
            # Add this line to get the correct starting phase number
            initial_phase = self.get_next_phase_number(self.current_pokemon)

            self.saved_data.pokemon[self.current_pokemon] = PokemonData(
                name=self.current_pokemon,
                encounters=self.current_number,
                adjustment=adjustment,
                game=self.current_game.get(),
                method=self.current_method.get(),
                last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                status="ACTIVE",
                phase=initial_phase  # Use the calculated phase number here
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

        self.number_label.configure(text=display_text)

    def calculate_shiny_odds(self, pokemon_data):
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

    def set_filter(self, filter_type):
        self.current_filter.set(filter_type)
        self.update_hunts_panel()

    def on_canvas_configure(self, event):
        if self.resize_job:
            self.root.after_cancel(self.resize_job)
        self.resize_job = self.root.after(200, self.resize_columns)

    def resize_columns(self):
        current_width = self.hunts_canvas.winfo_width()
        columns = self.calculate_columns()

        row, col = 0, 0
        for card in self.hunt_cards.values():
            card.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            col += 1
            if col >= columns:
                col = 0
                row += 1

        for c in range(columns):
            self.hunts_frame.grid_columnconfigure(c, weight=1)

        self.hunts_canvas.configure(scrollregion=self.hunts_canvas.bbox("all"))

    def on_hunts_frame_configure(self, event):
        self.hunts_canvas.configure(scrollregion=self.hunts_canvas.bbox("all"))

    def calculate_columns(self):
        canvas_width = self.hunts_canvas.winfo_width()
        columns = max(Config.MIN_COLUMNS, min(Config.MAX_COLUMNS, canvas_width // Config.CARD_MIN_WIDTH))
        return columns

    def update_hunts_panel(self):
        current_width = self.hunts_canvas.winfo_width()
        filtered_hunts = self.filter_hunts()
        sorted_hunts = sorted(filtered_hunts, key=self.get_sort_key,
                              reverse=self.sort_order.get() == "descending")
        current_hunt_names = {hunt.name for hunt in sorted_hunts}

        # Remove cards that are no longer needed
        for name in list(self.hunt_cards.keys()):
            if name not in current_hunt_names:
                self.hunt_cards[name].destroy()
                del self.hunt_cards[name]

        # Calculate grid layout
        columns = self.calculate_columns()
        row, col = 0, 0

        # Update or create cards
        for hunt in sorted_hunts:
            pokemon_name = hunt.name
            if pokemon_name in self.hunt_cards:
                self.update_hunt_card(pokemon_name, hunt)
            else:
                self.hunt_cards[pokemon_name] = self.create_hunt_card(pokemon_name, hunt)

            # Reposition card
            self.hunt_cards[pokemon_name].grid(
                row=row, column=col,
                padx=5, pady=5, sticky="nsew"
            )

            col += 1
            if col >= columns:
                col = 0
                row += 1

        # Configure grid columns
        for c in range(columns):
            self.hunts_frame.grid_columnconfigure(c, weight=1)

        # Update canvas scroll region
        self.hunts_canvas.configure(scrollregion=self.hunts_canvas.bbox("all"))

    def filter_hunts(self):
        filter_type = self.current_filter.get()
        note_filter = self.note_filter_entry.get().lower()

        return [
            p for p in self.saved_data.pokemon.values()
            if (filter_type == "all" or
                (filter_type == "active" and p.status == "ACTIVE") or
                (filter_type == "complete" and p.status == "COMPLETE") or
                (filter_type == "paused" and p.status == "PAUSED") or
                (filter_type == "phase" and p.status == "PHASE"))
               and (not note_filter or
                    (p.notes and note_filter in p.notes.lower()) or
                    (p.target and note_filter in p.target.lower()) or
                    (p.name and note_filter in p.name.lower()))
        ]

    def get_sort_key(self, data):
        if self.sort_by.get() == "most_recent":
            return datetime.strptime(data.last_updated, "%Y-%m-%d %H:%M:%S") if data.last_updated else datetime.min
        return data.encounters

    def handle_phase_input(self):
        phased_pokemon = simpledialog.askstring("New Phase",
                                                "Enter the Pokémon you phased on:",
                                                parent=self.root)
        if phased_pokemon:
            self.handle_phase(phased_pokemon)

    def create_hunt_card(self, pokemon_name, pokemon_data):
        card = ctk.CTkFrame(self.hunts_frame)
        status = pokemon_data.status
        status_color = {
            "COMPLETE": "#28a745",
            "PAUSED": "#e74c3c",
            "ACTIVE": "#3D7DCA"
        }.get(status, "#3D7DCA")

        # Use theme-appropriate colors
        bg_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"])
        border_color = self.root._apply_appearance_mode(ctk.ThemeManager.theme["CTkButton"]["border_color"])

        card = ctk.CTkFrame(
            self.hunts_frame,
            fg_color=bg_color,
            border_width=2,
            border_color=border_color,
            corner_radius=10
        )


        # Header with name and status
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Name and status label
        name_frame = ctk.CTkFrame(header, fg_color="transparent")
        name_frame.pack(side="left", fill="x", expand=True)

        name_text = pokemon_name.split()[0].capitalize()
        if pokemon_data.phase > 1:
            name_text += f" (Phase {pokemon_data.phase})"
        if pokemon_data.target:
            name_text += f" → {pokemon_data.target.capitalize()}"

        name_label = ctk.CTkLabel(
            name_frame,
            text=name_text,
            font=("Arial", 12, "bold")
        )
        name_label.pack(side="left")

        display_status = f"Phase {pokemon_data.phase}" if pokemon_data.target else status
        status_label = ctk.CTkLabel(
            name_frame,
            text=f"• {display_status}",
            text_color=status_color
        )
        status_label.pack(side="left", padx=5)

        # Image frame
        img_frame = ctk.CTkFrame(card, fg_color="transparent")
        img_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        try:
            # Try to load cached image first
            if pokemon_data.sprite_url and os.path.exists(pokemon_data.sprite_url):
                img = Image.open(pokemon_data.sprite_url)
            else:
                # Fallback to default sprite
                response = requests.get(DEFAULT_SPRITE_URL)
                img = Image.open(BytesIO(response.content))

            img = img.resize(Config.CARD_SPRITE_SIZE, Image.Resampling.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=Config.CARD_SPRITE_SIZE)
            self.image_references.append(ctk_img)
            img_label = ctk.CTkLabel(img_frame, image=ctk_img, text="")
            img_label.image = ctk_img
            img_label.pack()
        except Exception as e:
            print(f"Error loading card image: {e}")

        # Details frame
        details = ctk.CTkFrame(card, fg_color="transparent")
        details.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        # Encounters
        formatted_number = "{:,}".format(pokemon_data.encounters)
        encounters_label = ctk.CTkLabel(details, text=f"Encounters: {formatted_number}")
        encounters_label.grid(row=0, column=0, sticky="w")

        # Probability calculation
        probability_label = None
        if pokemon_data.method:
            odds = self.calculate_shiny_odds(pokemon_data)
            probability = 1 - ((odds - 1) / odds) ** pokemon_data.encounters
            probability_label = ctk.CTkLabel(
                details,
                text=f"Shiny Chance: {probability:.2%} (1/{odds:,})"
            )
            probability_label.grid(row=1, column=0, sticky="w")

        # Game information
        game_label = None
        if pokemon_data.game:
            game_label = ctk.CTkLabel(details, text=f"Game: {pokemon_data.game}")
            game_label.grid(row=2, column=0, sticky="w")

        # Found date
        found_date_label = None
        if status == "COMPLETE" and pokemon_data.found_date:
            found_date_label = ctk.CTkLabel(details, text=f"Found: {pokemon_data.found_date}")
            found_date_label.grid(row=3, column=0, sticky="w")

        # Action buttons
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

        # Load button
        load_btn = ctk.CTkButton(
            buttons,
            text="Load",
            command=lambda p=pokemon_name: self.load_pokemon(p),
            width=60
        )
        load_btn.grid(row=0, column=0, padx=2)

        # Notes button
        notes_btn = ctk.CTkButton(
            buttons,
            text="Notes",
            command=lambda p=pokemon_name: self.add_notes(p),
            fg_color="#FFCB05",
            text_color="#2C3E50",
            width=60
        )
        notes_btn.grid(row=0, column=1, padx=2)

        # Status toggle button
        btn_text = "✓" if status == "COMPLETE" else "▶"
        btn_fg = "#28a745" if status == "COMPLETE" else "#3D7DCA"
        status_button = ctk.CTkButton(
            buttons,
            text=btn_text,
            command=lambda p=pokemon_name: self.toggle_hunt_status(p),
            fg_color=btn_fg,
            width=60
        )
        status_button.grid(row=0, column=2, padx=2)

        # Configure grid weights
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=2)

        # Store references to dynamic elements
        card.encounters_label = encounters_label
        card.probability_label = probability_label
        card.status_label = status_label
        card.game_label = game_label
        card.found_date_label = found_date_label
        card.status_button = status_button

        return card

    def toggle_hunt_status(self, pokemon_name):
        pokemon_name = pokemon_name.lower()
        if pokemon_name in self.saved_data.pokemon:
            current_status = self.saved_data.pokemon[pokemon_name].status
            # New status cycle including PHASE
            status_cycle = {
                "ACTIVE": "COMPLETE",
                "COMPLETE": "PAUSED",
                "PAUSED": "ACTIVE",
                "PHASE": "COMPLETE"
            }
            new_status = status_cycle.get(current_status, "ACTIVE")

            self.saved_data.pokemon[pokemon_name].status = new_status

            if new_status == "COMPLETE" and not self.saved_data.pokemon[pokemon_name].found_date:
                self.saved_data.pokemon[pokemon_name].found_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            self.save_data()
            self.update_hunts_panel()

    def add_notes(self, pokemon_name):
        current_notes = self.saved_data.pokemon[pokemon_name].notes if pokemon_name in self.saved_data.pokemon else ""
        notes = simpledialog.askstring("Add Notes", f"Notes for {pokemon_name}:", initialvalue=current_notes,
                                       parent=self.root)
        if notes is not None:
            self.saved_data.pokemon[pokemon_name].notes = notes
            self.save_data()
            self.update_hunts_panel()

    def initialize_communication_files(self):
        for filepath in self.communication_files.values():
            if not os.path.exists(filepath):
                with open(filepath, 'w', encoding='utf-8') as f:
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
                if hasattr(self, 'initial_load') and not self.initial_load:
                    self.adjust_number("increase")
        except Exception as e:
            print(f"Error checking encounter trigger: {e}")
        finally:
            if hasattr(self, 'initial_load'):
                self.initial_load = False


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    root = ctk.CTk()
    app = ShinyCounter(root)
    root.mainloop()