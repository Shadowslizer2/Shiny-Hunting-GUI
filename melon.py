import os
import subprocess
import time
import glob
import win32gui
import win32con
import win32api
import pyvjoy
import keyboard
from tkinter import *
from tkinter import messagebox
import tkinter as tk
from tkinter import ttk

# Initialize virtual controller
try:
    controller = pyvjoy.VJoyDevice(1)
    CONTROLLER_AVAILABLE = True
except:
    CONTROLLER_AVAILABLE = False
    print("Warning: Virtual controller not available - will use keyboard fallback")

# Global variables
processes = []
windows = []
NUM_EMULATORS = 24  # Default number of emulators, can be changed
ROWS = 3  # Number of rows to arrange emulators in


class EmulatorController:
    def __init__(self, root):
        self.root = root
        root.title("MelonDS Controller")
        root.geometry("800x600")

        # Initialize communication files
        self.initialize_communication_files()

        # Main control frame
        main_frame = Frame(root)
        main_frame.pack(pady=10)

        # Configuration frame
        config_frame = Frame(root)
        config_frame.pack(pady=5)

        Label(config_frame, text="Number of Emulators:").pack(side=LEFT, padx=5)
        self.num_emulators_var = IntVar(value=NUM_EMULATORS)
        Spinbox(config_frame, from_=1, to=32, textvariable=self.num_emulators_var, width=5).pack(side=LEFT, padx=5)

        Label(config_frame, text="Rows:").pack(side=LEFT, padx=5)
        self.rows_var = IntVar(value=ROWS)
        Spinbox(config_frame, from_=1, to=4, textvariable=self.rows_var, width=5).pack(side=LEFT, padx=5)

        # Create main control buttons
        Button(main_frame, text="Open Emulators", command=self.open_emulators, height=2, width=20).grid(row=0, column=0,
                                                                                                        padx=5, pady=5)
        Button(main_frame, text="Close All Emulators", command=self.close_emulators, height=2, width=20).grid(row=1,
                                                                                                              column=0,
                                                                                                              padx=5,
                                                                                                              pady=5)
        Button(main_frame, text="Sudowoodo Reset", command=self.sudowoodo_sequence, height=2, width=20).grid(row=0,
                                                                                                                column=1,
                                                                                                                padx=5,
                                                                                                                pady=5)
        Button(main_frame, text="Eevee Reset", command=self.eevee_sequence, height=2, width=20).grid(row=1,
                                                                                                             column=1,
                                                                                                             padx=5,
                                                                                                             pady=5)
        Button(main_frame, text="Snorlax Reset", command=self.snorlax_sequence, height=2, width=20).grid(row=2,
                                                                                                     column=1,
                                                                                                     padx=5,
                                                                                                     pady=5)
        Button(main_frame, text="Simple Reset", command=self.simple_reset_sequence, height=2, width=20).grid(row=1,
                                                                                                             column=2,
                                                                                                             padx=5,
                                                                                                             pady=5)
        Button(main_frame, text="Run Away", command=self.run_away, height=2, width=20).grid(row=0,
                                                                                                           column=2,
                                                                                                           padx=5,
                                                                                                           pady=5)
        Button(main_frame, text="Fossil Reset", command=self.fossil_sequence, height=2, width=20).grid(row=2,
                                                                                                       column=2,
                                                                                                       padx=5,
                                                                                                       pady=5)
        Button(main_frame, text="Sweet Scent", command=self.sweet_scent_sequence, height=2, width=20).grid(row=0,
                                                                                                          column=3,
                                                                                                          padx=5,
                                                                                                          pady=5)
        Button(main_frame, text="Sweet Scent Start Up", command=self.sweet_scent_set_up, height=2, width=20).grid(row=1,
                                                                                                           column=3,
                                                                                                           padx=5,
                                                                                                           pady=5)
        Button(main_frame, text="Headbutt", command=self.headbutt, height=2, width=20).grid(row=2,
                                                                                           column=3,
                                                                                           padx=5,
                                                                                           pady=5)

        # DS Controller Layout Frame
        ds_frame = Frame(root)
        ds_frame.pack(pady=20)

        # D-Pad (Left side)
        dpad_frame = Frame(ds_frame)
        dpad_frame.grid(row=0, column=0, padx=20)

        # D-Pad buttons arranged in cross pattern with text labels
        Label(dpad_frame, text="D-Pad").grid(row=0, column=1)
        Button(dpad_frame, text="Up", command=self.move_up, width=5, height=1).grid(row=1, column=1)
        Button(dpad_frame, text="Left", command=self.move_left, width=5, height=1).grid(row=2, column=0)
        Button(dpad_frame, text="Down", command=self.move_down, width=5, height=1).grid(row=2, column=1)
        Button(dpad_frame, text="Right", command=self.move_right, width=5, height=1).grid(row=2, column=2)

        # Action buttons (Right side)
        action_frame = Frame(ds_frame)
        action_frame.grid(row=0, column=1, padx=20)

        # Action buttons arranged in diamond pattern with corrected positions
        Label(action_frame, text="Action Buttons").grid(row=0, column=1)
        Button(action_frame, text="X", command=self.press_x, width=5, height=1).grid(row=1, column=1)  # Top
        Button(action_frame, text="Y", command=self.press_y, width=5, height=1).grid(row=2, column=0)  # Left
        Button(action_frame, text="A", command=self.press_a, width=5, height=1).grid(row=2, column=2)  # Right
        Button(action_frame, text="B", command=self.press_b, width=5, height=1).grid(row=3, column=1)  # Bottom

        # Fast Forward button
        ff_frame = Frame(ds_frame)
        ff_frame.grid(row=0, column=2, padx=10)
        self.ff_button = Button(ff_frame, text="Fast Forward", command=self.toggle_fast_forward,
                                height=3, width=15, bg='orange', fg='black')
        self.ff_button.pack()
        self.ff_state = False

        # Shoulder buttons (Top)
        shoulder_frame = Frame(ds_frame)
        shoulder_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0))

        Button(shoulder_frame, text="L", command=self.press_l, width=5).grid(row=0, column=0, padx=10)
        Button(shoulder_frame, text="R", command=self.press_r, width=5).grid(row=0, column=1, padx=10)

        # Start/Select buttons (Bottom)
        start_select_frame = Frame(ds_frame)
        start_select_frame.grid(row=2, column=0, columnspan=3, pady=(10, 0))

        Button(start_select_frame, text="Select", command=self.press_select, width=7).grid(row=0, column=0, padx=5)
        Button(start_select_frame, text="Start", command=self.press_start, width=7).grid(row=0, column=1, padx=5)

        # Status label
        self.status = Label(root, text="Ready")
        self.status.pack(pady=10)

    def initialize_communication_files(self):
        """Ensure communication files exist with default values"""
        if not os.path.exists("melon_emulator_count.txt"):
            with open("melon_emulator_count.txt", 'w') as f:
                f.write(str(self.num_emulators_var.get()))

        if not os.path.exists("encounter_trigger.txt"):
            with open("encounter_trigger.txt", 'w') as f:
                f.write("0")

    def update_status(self, message):
        self.status.config(text=message)
        self.root.update()

    def get_recent_rom_and_sav(self):
        """Find most recent .sav file and its corresponding .nds file"""
        roms_dir = r"F:\Important Documents\Nintendo\Desmume\Roms"

        if not os.path.exists(roms_dir):
            messagebox.showerror("Error", "ROMs directory not found")
            return None, None

        sav_files = glob.glob(os.path.join(roms_dir, '*.sav'))
        if not sav_files:
            messagebox.showerror("Error", "No .sav files found in ROMs directory")
            return None, None

        recent_sav = max(sav_files, key=os.path.getmtime)
        nds_file = os.path.splitext(recent_sav)[0] + '.nds'

        if not os.path.exists(nds_file):
            messagebox.showerror("Error", f"No matching .nds file found for {recent_sav}")
            return None, recent_sav

        return nds_file, recent_sav

    def position_window(self, hwnd, x, y, width, height):
        """Position a window at specified coordinates"""
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, x, y, width, height, win32con.SWP_SHOWWINDOW)

    def soft_reset(self, hwnd):
        """Perform soft reset (L+R+Start+Select) on specific window"""
        win32gui.SetForegroundWindow(hwnd)
        time.sleep(0.05)

        keyboard.press('f')  # L button
        keyboard.press('g')  # R button
        keyboard.press('b')  # Start button
        keyboard.press('v')  # Select button
        time.sleep(0.1)
        keyboard.release('f')
        keyboard.release('g')
        keyboard.release('b')
        keyboard.release('v')
        time.sleep(0.05)

    def press_button(self, button_num, duration=0.2):
        """Generic button press function"""
        if CONTROLLER_AVAILABLE:
            try:
                controller.set_button(button_num, 1)
                time.sleep(duration)
                controller.set_button(button_num, 0)
                self.update_status(f"Button {button_num} pressed ({duration*1000}ms)")
            except Exception as e:
                self.update_status(f"Controller error: {e}")
        else:
            self.update_status("No controller available")

    def press_b(self):
        """Press B button (Button 1)"""
        self.press_button(1)

    def press_a(self):
        """Press A button (Button 2)"""
        self.press_button(2)

    def press_y(self):
        """Press Y button (Button 3)"""
        self.press_button(3)

    def press_x(self):
        """Press X button (Button 4)"""
        self.press_button(4)

    def press_l(self):
        """Press L button (Button 5)"""
        self.press_button(5)

    def press_r(self):
        """Press R button (Button 6)"""
        self.press_button(6)

    def press_select(self):
        """Press Select button (Button 7)"""
        self.press_button(7)

    def press_start(self):
        """Press Start button (Button 8)"""
        self.press_button(8, 0.3)

    def set_axis(self, axis, value, duration=0.1):
        """Set axis value with automatic reset after duration"""
        if CONTROLLER_AVAILABLE:
            try:
                if axis == 1:
                    controller.set_axis(pyvjoy.HID_USAGE_X, value)
                elif axis == 2:
                    controller.set_axis(pyvjoy.HID_USAGE_Y, value)

                # Reset after duration
                self.root.after(int(duration * 1000), lambda: self.reset_axis(axis))
            except Exception as e:
                self.update_status(f"Controller error: {e}")

    def reset_axis(self, axis):
        """Reset axis to center position"""
        if CONTROLLER_AVAILABLE:
            try:
                if axis == 1:
                    controller.set_axis(pyvjoy.HID_USAGE_X, 0x4000)
                elif axis == 2:
                    controller.set_axis(pyvjoy.HID_USAGE_Y, 0x4000)
            except Exception as e:
                self.update_status(f"Controller error: {e}")

    def move_left(self):
        """Move Left (Axis 1-) - single press"""
        self.set_axis(1, 0x0000)  # Full left
        self.update_status("Moving Left (single press)")

    def move_right(self):
        """Move Right (Axis 1+) - single press"""
        self.set_axis(1, 0x8000)  # Full right
        self.update_status("Moving Right (single press)")

    def move_up(self):
        """Move Up (Axis 2-) - single press"""
        self.set_axis(2, 0x0000)  # Full up
        self.update_status("Moving Up (single press)")

    def move_down(self):
        """Move Down (Axis 2+) - single press"""
        self.set_axis(2, 0x8000)  # Full down
        self.update_status("Moving Down (single press)")

    def tap_left(self, duration=0.05):
        """Quick Left tap (Axis 1-) - press and release"""
        self.set_axis(1, 0x0000)  # Full left
        self.update_status("Tapping Left")
        time.sleep(duration)
        self.set_axis(1, 0x4000)  # Center position (release)

    def tap_right(self, duration=0.05):
        """Quick Right tap (Axis 1+) - press and release"""
        self.set_axis(1, 0x8000)  # Full right
        self.update_status("Tapping Right")
        time.sleep(duration)
        self.set_axis(1, 0x4000)  # Center position (release)

    def tap_up(self, duration=0.05):
        """Quick Up tap (Axis 2-) - press and release"""
        self.set_axis(2, 0x0000)  # Full up
        self.update_status("Tapping Up")
        time.sleep(duration)
        self.set_axis(2, 0x4000)  # Center position (release)

    def tap_down(self, duration=0.05):
        """Quick Down tap (Axis 2+) - press and release"""
        self.set_axis(2, 0x8000)  # Full down
        self.update_status("Tapping Down")
        time.sleep(duration)
        self.set_axis(2, 0x4000)  # Center position (release)

    def toggle_fast_forward(self):
        """Toggle Fast Forward state with pyvjoy debugging info"""
        self.ff_state = not self.ff_state

        if CONTROLLER_AVAILABLE:
            try:
                print("\n[VJoy Controller Debug]")

                # Try to get some basic info about pyvjoy
                print(f"Pyvjoy available: {hasattr(pyvjoy, '__version__')}")

                # Print device capabilities from constants
                print("\nDevice Capabilities (from pyvjoy constants):")
                print(f"Max buttons: {getattr(pyvjoy.constants, 'VJOY_MAX_NUMBER_OF_BUTTONS', 'Unknown')}")
                print(f"Max axes: {getattr(pyvjoy.constants, 'VJOY_MAX_NUMBER_OF_ANALOG', 'Unknown')}")
                print(f"Max hats: {getattr(pyvjoy.constants, 'VJOY_MAX_NUMBER_OF_HATS', 'Unknown')}")

                # Show our intended action
                print(f"\nAttempting to set button 9 to: {self.ff_state}")

                # Set button 9
                controller.set_button(9, 1 if self.ff_state else 0)
                self.ff_button.config(bg='green' if self.ff_state else 'orange')

                status_msg = f"Fast Forward {'ON' if self.ff_state else 'OFF'} (Button 9)"
                self.update_status(status_msg)
                print(f"\n{status_msg}")

            except Exception as e:
                error_msg = f"VJoy Error: {str(e)}"
                self.update_status(error_msg)
                print(error_msg)
                print(f"Exception type: {type(e).__name__}")
                if hasattr(e, 'args'):
                    print(f"Error details: {e.args}")
        else:
            error_msg = "VJoy Controller not initialized"
            self.update_status(error_msg)
            print(error_msg)
            
    def eevee_sequence(self):
        """Perform soft reset, wait 6 seconds, then press Start button"""
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Eevee sequence for {num_emulators} emulators...")

        # Update emulator count file immediately
        self.update_emulator_count_file()

        # Get all melonDS windows
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        # First pass: soft reset all windows individually
        for hwnd in windows:
            try:
                self.soft_reset(hwnd)
            except Exception as e:
                print(f"Error resetting window {hwnd}: {e}")

        # Reset + A
        self.update_status("Waiting 8.5 seconds...")
        time.sleep(8.5)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 1.75 seconds...")
        time.sleep(1.75)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        # Talk to Bill
        self.update_status("Waiting 1 seconds...")
        time.sleep(1)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 1 seconds...")
        time.sleep(1)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 1 seconds...")
        time.sleep(1)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 1 seconds...")
        time.sleep(1)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 1.7 seconds...")
        time.sleep(1.7)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 0.5 seconds...")
        time.sleep(0.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 0.5 seconds...")
        time.sleep(0.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 6 seconds...")
        time.sleep(6)
        self.update_status("Sending B button to all instances...")
        self.press_b()

        self.update_status("Waiting 1.5 seconds...")
        time.sleep(1.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 0.5 seconds...")
        time.sleep(0.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        # Open Pokemon Summary
        self.update_status("Waiting 0.5 seconds...")
        time.sleep(0.5)
        self.update_status("Sending x button to all instances...")
        self.press_x()

        time.sleep(0.1)
        self.tap_down()

        time.sleep(0.1)
        self.press_a()

        self.update_status("Waiting 1.25 seconds...")
        time.sleep(1.5)
        self.update_status("Moving to Eevee all instances...")
        self.tap_left()

        time.sleep(.1)
        self.tap_up()

        time.sleep(.1)
        self.tap_right()

        time.sleep(0.1)
        self.press_a()

        time.sleep(0.25)
        self.press_a()

        # Trigger shiny hunter increment at the end
        self.trigger_shinyhunter_increment()

        self.update_status("Eevee sequence completed")


    def fossil_sequence(self):
        """Perform soft reset, wait 6 seconds, then press Start button"""
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Fossil sequence for {num_emulators} emulators...")

        # Update emulator count file immediately
        self.update_emulator_count_file()

        # Get all melonDS windows
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        # First pass: soft reset all windows individually
        for hwnd in windows:
            try:
                self.soft_reset(hwnd)
            except Exception as e:
                print(f"Error resetting window {hwnd}: {e}")

        # Reset + A
        self.update_status("Waiting 8.5 seconds...")
        time.sleep(8.5)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 1.75 seconds...")
        time.sleep(1.75)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        # Talk to Person

        time.sleep(.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        time.sleep(1)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        time.sleep(1)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 6 seconds...")
        time.sleep(6)
        self.update_status("Sending B button to all instances...")
        self.press_b()

        # Open Pokemon Summary
        self.update_status("Waiting 1 seconds...")
        time.sleep(1)
        self.update_status("Sending x button to all instances...")
        self.press_x()

        time.sleep(0.1)
        self.tap_down()

        time.sleep(0.1)
        self.press_a()

        self.update_status("Waiting 1.25 seconds...")
        time.sleep(1.25)
        self.update_status("Moving to Fossil all instances...")
        self.tap_right()

        time.sleep(0.1)
        self.press_a()

        time.sleep(0.25)
        self.press_a()

        # Trigger shiny hunter increment at the end
        self.trigger_shinyhunter_increment()

        self.update_status("Fossil sequence completed")

    def snorlax_sequence(self):
        """Perform Sweet Scent set up sequence """
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Snorlax sequence for {num_emulators} emulators...")
        self.update_emulator_count_file()
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        # First pass: soft reset all windows individually
        for hwnd in windows:
            try:
                self.soft_reset(hwnd)
            except Exception as e:
                print(f"Error resetting window {hwnd}: {e}")

        # Button Presses
        time.sleep(8.5)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        time.sleep(1.75)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        time.sleep(3)
        self.update_status("Sending X button to all instances...")
        self.press_x()

        time.sleep(.1)
        self.tap_up()

        time.sleep(.1)
        self.press_a()

        time.sleep(1)
        self.press_b()

        time.sleep(1.75)
        self.press_b()

        time.sleep(.1)
        self.press_a()

        time.sleep(.15)
        self.press_a()

        time.sleep(.4)
        self.press_a()

        self.trigger_shinyhunter_increment()
        self.update_status("Snorlax sequence completed")

    def sudowoodo_sequence(self):
        """Perform soft reset, wait 6 seconds, then press Start button"""
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Sudowoodo sequence for {num_emulators} emulators...")

        # Update emulator count file immediately
        self.update_emulator_count_file()

        # Get all melonDS windows
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        # First pass: soft reset all windows individually
        for hwnd in windows:
            try:
                self.soft_reset(hwnd)
            except Exception as e:
                print(f"Error resetting window {hwnd}: {e}")

        # Button Presses
        self.update_status("Waiting 9 seconds...")
        time.sleep(9)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 2 seconds...")
        time.sleep(2)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 3.5 seconds...")
        time.sleep(3.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 4 seconds...")
        time.sleep(4)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 2 seconds...")
        time.sleep(2)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 3.5 seconds...")
        time.sleep(3.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 0.5 seconds...")
        time.sleep(0.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        # Trigger shiny hunter increment at the end
        self.trigger_shinyhunter_increment()

        self.update_status("Sudowoodo sequence completed")


    def simple_reset_sequence(self):
        """Perform soft reset, wait 6 seconds, then press Start button"""
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Sudowoodo sequence for {num_emulators} emulators...")

        # Update emulator count file immediately
        self.update_emulator_count_file()

        # Get all melonDS windows
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        # First pass: soft reset all windows individually
        for hwnd in windows:
            try:
                self.soft_reset(hwnd)
            except Exception as e:
                print(f"Error resetting window {hwnd}: {e}")

        # Button Presses
        self.update_status("Waiting 8.75 seconds...")
        time.sleep(8.5)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 1.75 seconds...")
        time.sleep(1.75)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 3 seconds...")
        time.sleep(3)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        time.sleep(.15)
        self.press_a()

        # Trigger shiny hunter increment at the end
        self.trigger_shinyhunter_increment()

        self.update_status("Simple Reset sequence completed")

    def headbutt(self):
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Headbutt sequence for {num_emulators} emulators...")

        # Update emulator count file immediately
        self.update_emulator_count_file()

        # Get all melonDS windows
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        self.press_a()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.move_down()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.move_right()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting 5.5 seconds...")
        time.sleep(5.4)
        self.press_a()

        time.sleep(1.4)
        self.press_a()

        time.sleep(1)
        self.press_a()

        # Trigger shiny hunter increment at the end
        self.trigger_shinyhunter_increment()

        self.update_status("Headbutt sequence completed")

    def run_away(self):
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Run Away sequence for {num_emulators} emulators...")

        # Update emulator count file immediately
        self.update_emulator_count_file()

        # Get all melonDS windows
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        self.press_a()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.move_down()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.move_right()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting 5.6 seconds...")
        time.sleep(5.6)
        self.press_a()

        # Trigger shiny hunter increment at the end
        self.trigger_shinyhunter_increment()

        self.update_status("Simple Reset sequence completed")

    def sweet_scent_set_up(self):
        """Perform Sweet Scent set up sequence """
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Sweet Scent Start Up sequence for {num_emulators} emulators...")
        self.update_emulator_count_file()
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        # First pass: soft reset all windows individually
        for hwnd in windows:
            try:
                self.soft_reset(hwnd)
            except Exception as e:
                print(f"Error resetting window {hwnd}: {e}")

        # Button Presses
        self.update_status("Waiting 9 seconds...")
        time.sleep(9)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 2 seconds...")
        time.sleep(2)
        self.update_status("Sending Start button to all instances...")
        self.press_start()

        self.update_status("Waiting 3.5 seconds...")
        time.sleep(3.5)
        self.update_status("Sending A button to all instances...")
        self.press_a()

        self.update_status("Waiting 4 seconds...")
        time.sleep(4)
        self.update_status("Sending X button to all instances...")
        self.press_x()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.tap_down()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting 1.25 seconds...")
        time.sleep(1.25)
        self.tap_down()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.tap_left()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.trigger_shinyhunter_increment()
        self.update_status("Sweet Scent Start Up sequence completed")

    def sweet_scent_sequence(self):
        num_emulators = self.num_emulators_var.get()
        self.update_status(f"Starting Sweet Scent sequence for {num_emulators} emulators...")
        self.update_emulator_count_file()
        self.find_melonds_windows()

        if not windows:
            messagebox.showwarning("Warning", "No melonDS windows found")
            return

        self.press_a()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.move_down()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.move_right()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting 5.6 seconds...")
        time.sleep(5.6)
        self.press_x()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting 1.25 seconds...")
        time.sleep(1.25)
        self.tap_down()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.tap_left()

        self.update_status("Waiting .1 seconds...")
        time.sleep(.1)
        self.press_a()

        self.trigger_shinyhunter_increment()
        self.update_status("Sweet Scent sequence completed")

    def update_emulator_count_file(self):
        """Update the emulator count file"""
        try:
            with open("melon_emulator_count.txt", 'w') as f:
                f.write(str(self.num_emulators_var.get()))
        except Exception as e:
            print(f"Error updating emulator count file: {e}")

    def trigger_shinyhunter_increment(self):
        """Signal to increment encounters in shiny hunter"""
        try:
            with open("encounter_trigger.txt", 'w') as f:
                f.write(str(time.time()))
        except Exception as e:
            print(f"Error updating encounter trigger file: {e}")

    def find_melonds_windows(self):
        """Find all melonDS windows"""
        global windows
        windows = []

        def window_enum_callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd) and "melonDS" in win32gui.GetWindowText(hwnd):
                windows.append(hwnd)

        win32gui.EnumWindows(window_enum_callback, None)
        windows = windows[:self.num_emulators_var.get()]  # Only keep the requested number

    def open_emulators(self):
        """Open emulator instances with most recent ROM"""
        global processes
        num_emulators = self.num_emulators_var.get()
        rows = self.rows_var.get()
        cols = (num_emulators + rows - 1) // rows  # Calculate columns needed

        self.update_status(f"Opening {num_emulators} emulators in {rows} rows...")

        melon_path = r"F:\Important Documents\Nintendo\Desmume\melonDS.exe"

        if not os.path.exists(melon_path):
            messagebox.showerror("Error", "melonDS.exe not found")
            return

        nds_file, sav_file = self.get_recent_rom_and_sav()
        if not nds_file:
            return

        # Get primary monitor dimensions
        screen_width = win32api.GetSystemMetrics(0)
        screen_height = win32api.GetSystemMetrics(1)

        # Calculate window dimensions with 5px padding between windows
        padding = 0
        window_width = (screen_width - (padding * (cols + 1))) // cols
        window_height = (screen_height - (padding * (rows + 1))) // rows

        # Close any existing instances first
        self.close_emulators()

        # Open new instances
        processes = []
        for _ in range(num_emulators):
            processes.append(subprocess.Popen([melon_path, nds_file]))
            time.sleep(0.3)

        # Wait for windows to initialize
        time.sleep(2.5)

        # Position windows
        self.find_melonds_windows()

        for i, hwnd in enumerate(windows):
            try:
                col = i % cols
                row = i // cols
                # Calculate position with padding - 10 for setting to far left
                x = col * (window_width + padding) + padding - 10
                y = row * (window_height + padding) + padding

                # Adjust for taskbar (subtract 40px from height if at bottom)
                adjusted_height = window_height
                if y + window_height > screen_height - 40:
                    adjusted_height = window_height - 40

                self.position_window(hwnd, x, y, window_width, adjusted_height)
            except Exception as e:
                print(f"Error positioning window {i}: {e}")

        # Update emulator count file
        self.update_emulator_count_file()

        self.update_status(f"{num_emulators} emulators opened and positioned in {rows} rows")

    def close_emulators(self):
        """Close all melonDS processes"""
        global processes, windows
        self.update_status("Closing emulators...")

        # Close processes we opened
        for proc in processes:
            try:
                proc.terminate()
            except:
                pass

        # Find and close any other melonDS windows
        self.find_melonds_windows()
        for hwnd in windows:
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except:
                pass

        processes = []
        windows = []
        time.sleep(0.5)
        self.update_status("All emulators closed")

if __name__ == "__main__":
    root = Tk()
    app = EmulatorController(root)

    try:
        keyboard.hook(lambda e: None)
        root.mainloop()
    finally:
        keyboard.unhook_all()
        if 'controller' in globals():
            try:
                controller.reset()
            except:
                pass