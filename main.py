import customtkinter as ctk
import subprocess
import sys
import os
import threading
import queue  # New import for queue
import time   # New import for sleep
import configparser  # New import for config handling
import webbrowser  # Add this import at the top

from console import ConsoleWindow, QueueWriter  # Importing ConsoleWindow and QueueWriter from console.py
from setupGUI import run_setup  # Add this import at the top

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Constants
CONFIG_FILE = "config.ini"

class ToolTip:
    """
    It creates a tooltip for a given widget as the mouse goes on it.
    """
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tooltip_window = tw = ctk.CTkToplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(tw, text=self.text, wraplength=150, bg_color="#2e2e2e", text_color="white")
        label.pack()

    def hide_tooltip(self, event=None):
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            tw.destroy()

def get_base_path():
    """Get the base path for the application in both dev and standalone environments"""
    if getattr(sys, 'frozen', False):
        # Running in a bundle (standalone)
        return os.path.dirname(sys.executable)
    else:
        # Running in normal Python environment
        return os.path.dirname(os.path.abspath(__file__))

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("System Captioner")
        self.geometry("400x285")
        self.resizable(False, False)

        # Add icon to the main window
        icon_path = os.path.join(get_base_path(), "icon.ico")
        self.iconbitmap(icon_path)

        self.intelligent_mode = ctk.BooleanVar()
        self.gpu_enabled = ctk.BooleanVar()
        self.model_selection = ctk.StringVar()
        self.app_running = False
        self.process = None

        # Redirect stdout and stderr to the console queue
        self.console_queue = queue.Queue()
        sys.stdout = QueueWriter(self.console_queue)
        sys.stderr = QueueWriter(self.console_queue)

        # Initialize the console window
        self.console_window = ConsoleWindow(self.console_queue, self)
        self.console_window.withdraw()  # Start hidden

        self.config = configparser.ConfigParser()
        self.load_config()

        # Initialize variables with config values
        self.intelligent_mode.set(self.config.getboolean('Settings', 'mode'))
        self.gpu_enabled.set(self.config.getboolean('Settings', 'cuda'))
        self.model_selection.set(self.config.get('Settings', 'model'))

        self.start_button = ctk.CTkButton(self, text="Start", command=self.toggle_app, fg_color="green", hover_color="dark green")
        self.start_button.pack(pady=(25, 10))

        self.console_button = ctk.CTkButton(self, text="Console", command=self.open_console, fg_color="blue", hover_color="dark blue")
        self.console_button.pack(pady=(0, 25))

        self.checkbox_frame = ctk.CTkFrame(self)
        self.checkbox_frame.pack(pady=(0, 10))

        self.inner_checkbox_frame = ctk.CTkFrame(self.checkbox_frame)
        self.inner_checkbox_frame.pack()

        self.intelligent_checkbox = ctk.CTkCheckBox(
            self.inner_checkbox_frame, 
            text="Intelligent mode", 
            variable=self.intelligent_mode,
            command=self.save_config
        )
        self.intelligent_checkbox.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.intelligent_tooltip_button = ctk.CTkButton(
            self.inner_checkbox_frame,
            text="?",
            width=25,
            height=25,
            fg_color="transparent",
            hover_color="grey",
            command=None
        )
        self.intelligent_tooltip_button.grid(row=0, column=1)
        ToolTip(
            self.intelligent_tooltip_button, 
            "In intelligent mode, subtitle window is shown only when speech is detected."
        )

        self.gpu_checkbox = ctk.CTkCheckBox(
            self.inner_checkbox_frame,
            text="Run on GPU",
            variable=self.gpu_enabled,
            command=self.save_config
        )
        self.gpu_checkbox.grid(row=1, column=0, sticky="w", padx=(0, 10), pady=(5, 0))

        self.gpu_tooltip_button = ctk.CTkButton(
            self.inner_checkbox_frame,
            text="?",
            width=25,
            height=25,
            fg_color="transparent",
            hover_color="grey",
            command=None
        )
        self.gpu_tooltip_button.grid(row=1, column=1, pady=(5, 0))
        ToolTip(
            self.gpu_tooltip_button, 
            "Disabling this will run the app on CPU and result in much slower transcription."
        )

        self.model_frame = ctk.CTkFrame(self)
        self.model_frame.pack(pady=(0, 10))

        self.model_label = ctk.CTkLabel(self.model_frame, text="Model:")
        self.model_label.pack(side="left", padx=(0, 5))

        self.model_dropdown = ctk.CTkOptionMenu(
            self.model_frame,
            values=["tiny", "base", "small", "medium", "large"],
            variable=self.model_selection,
            command=self.save_config  # Save config on change
        )
        self.model_dropdown.pack(side="left")

        self.model_tooltip_button = ctk.CTkButton(
            self.model_frame,
            text="?",
            width=25,
            height=25,
            fg_color="transparent",
            hover_color="grey",
            command=None
        )
        self.model_tooltip_button.pack(side="left")
        ToolTip(
            self.model_tooltip_button, 
            "Select the model to use for transcription. Larger models are more accurate but require more VRAM."
        )

        # Add audio device selection frame
        self.device_frame = ctk.CTkFrame(self)
        self.device_frame.pack(pady=(0, 10))

        self.device_label = ctk.CTkLabel(self.device_frame, text="Audio Device:")
        self.device_label.pack(side="left", padx=(0, 5))

        self.devices = self.get_audio_devices()
        self.device_names = [device['name'] for device in self.devices]
        self.device_selection = ctk.StringVar()

        # Load saved device from config
        saved_device = self.config.get('Settings', 'audio_device', fallback='')
        if saved_device in self.device_names:
            self.device_selection.set(saved_device)
        elif self.device_names:
            self.device_selection.set(self.device_names[0])

        self.device_dropdown = ctk.CTkOptionMenu(
            self.device_frame,
            values=self.device_names,
            variable=self.device_selection,
            command=self.on_device_change  # Call this method when device changes
        )
        self.device_dropdown.pack(side="left")

        # Add this line after super().__init__()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Add these as class attributes
        self.TRANSCRIPTION_TIMEOUT = 5  # seconds
        self.last_transcription_start = 0
        self.current_transcription_file = None
        self.timeout_thread = None
        self.stop_timeout = threading.Event()

        # Add these after all other UI elements in __init__
        self.feedback_label = ctk.CTkLabel(
            self,
            text="If the app didn't work or you had any issues, let me know!",
            text_color="light blue",
            cursor="hand2",
            font=("", -13, "underline")  # Added underline to the font
        )
        self.feedback_label.pack(side="bottom", pady=(0, 10))
        self.feedback_label.bind("<Button-1>", lambda e: self.open_feedback_link())

    def load_config(self):
        """Load the configuration from config.ini or create default if not exists."""
        if not os.path.exists(CONFIG_FILE):
            # Run setup GUI to get initial audio device selection
            run_setup()
        self.config.read(CONFIG_FILE)

    def save_config(self, *args):
        """Save the current settings to config.ini."""
        self.config['Settings']['mode'] = str(self.intelligent_mode.get())
        self.config['Settings']['cuda'] = str(self.gpu_enabled.get())
        self.config['Settings']['model'] = self.model_selection.get()
        self.config['Settings']['audio_device'] = self.device_selection.get()

        # Save the sample rate of the selected device
        selected_device = self.device_selection.get()
        device_info = next((device for device in self.devices if device['name'] == selected_device), None)
        if device_info:
            self.config['Settings']['sample_rate'] = str(device_info['defaultSampleRate'])

        with open(CONFIG_FILE, 'w') as configfile:
            self.config.write(configfile)

    def toggle_app(self):
        if not self.app_running:
            self.start_app()
            self.start_button.configure(text="Stop", fg_color="red", hover_color="dark red")
        else:
            self.stop_app()
            self.start_button.configure(text="Start", fg_color="green", hover_color="dark green")

    def start_app(self):
        # Reset the timeout tracking variables
        self.last_transcription_start = 0
        self.current_transcription_file = None
        
        base_dir = get_base_path()
        recordings_path = os.path.join(base_dir, "recordings")
        transcriptions_path = os.path.join(base_dir, "transcriptions.txt")

        if os.path.exists(recordings_path):
            try:
                for filename in os.listdir(recordings_path):
                    file_path = os.path.join(recordings_path, filename)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                print("Existing recordings have been deleted.", flush=True)
                self.enqueue_console_message("Existing recordings have been deleted.")
            except Exception as e:
                print(f"Error deleting recordings: {e}", flush=True)
                self.enqueue_console_message(f"Error deleting recordings: {e}")
        else:
            print("Recordings directory does not exist. Creating one.", flush=True)
            self.enqueue_console_message("Recordings directory does not exist. Creating one.")
            os.makedirs(recordings_path)

        try:
            with open(transcriptions_path, 'w') as f:
                pass  # Truncate the file to empty it
            print("transcriptions.txt has been emptied.", flush=True)
            self.enqueue_console_message("transcriptions.txt has been emptied.")
        except Exception as e:
            print(f"Error emptying transcriptions.txt: {e}", flush=True)
            self.enqueue_console_message(f"Error emptying transcriptions.txt: {e}")

        self.start_button.configure(text="Stop", fg_color="red", hover_color="dark red")
        intelligent = self.intelligent_mode.get()
        cuda = self.gpu_enabled.get()
        model = self.model_selection.get()
        
        # Determine the path to the Controller executable
        if getattr(sys, 'frozen', False):
            controller_executable = os.path.join(base_dir, 'Controller', 'Controller.exe')
        else:
            controller_executable = os.path.join(base_dir, 'controller.py')
        
        args = [controller_executable]
        if intelligent:
            args.append("--intelligent")
        if cuda:
            args.append("--cuda")
        args.extend(["--model", model])
        
        # Get the selected device index
        selected_device = self.device_selection.get()
        device_index = next((device['index'] for device in self.devices if device['name'] == selected_device), None)
        if device_index is not None:
            args.extend(["--device-index", str(device_index)])
        
        # If running in a frozen state, ensure subprocess handles executable correctly
        self.process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Merge stderr into stdout
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        self.app_running = True

        self.stop_timeout.clear()
        self.timeout_thread = threading.Thread(target=self.monitor_timeout, daemon=True)
        self.timeout_thread.start()

        threading.Thread(target=self.read_process_output, daemon=True).start()
        threading.Thread(target=self.watch_console_queue, daemon=True).start()

    def stop_app(self):
        if self.process:
            try:
                self.process.terminate()
                # Wait for a short time for graceful termination
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if process doesn't terminate gracefully
                self.process.kill()
            self.process = None
        self.start_button.configure(text="Start", fg_color="green", hover_color="dark green")
        self.app_running = False
        self.stop_timeout.set()
        if self.timeout_thread and threading.current_thread() != self.timeout_thread:
            self.timeout_thread.join()
            self.timeout_thread = None

    def monitor_timeout(self):
        while self.app_running and not self.stop_timeout.is_set():
            if self.last_transcription_start > 0:
                elapsed_time = time.time() - self.last_transcription_start
                if elapsed_time > self.TRANSCRIPTION_TIMEOUT:
                    error_msg = f"Transcription timeout for {self.current_transcription_file} after {self.TRANSCRIPTION_TIMEOUT} seconds"
                    self.enqueue_console_message(f"controller.py ERROR: {error_msg}")
                    self.stop_app()
                    time.sleep(1)  # Give it a moment to clean up
                    self.start_app()  # Restart the application
                    break
            time.sleep(1)

    def read_process_output(self):
        """Read and process lines from the subprocess's combined stdout and stderr."""
        if self.process.stdout:
            for line in iter(self.process.stdout.readline, ''):
                if not line:
                    break
                line = line.strip()

                # Check for transcription start
                if "Starting transcription for" in line:
                    self.last_transcription_start = time.time()
                    self.current_transcription_file = line.split("...")[-2].split("recordings\\")[-1]

                # Check for transcription completion or error
                if "Transcription completed" in line or "Error during transcription" in line:
                    self.last_transcription_start = 0  # Reset the timer
                    self.current_transcription_file = None

                # Determine if the line is an error message
                if "ERROR" in line:
                    self.enqueue_console_message(f"controller.py ERROR: {line}")
                else:
                    self.enqueue_console_message(f"controller.py: {line}")

    def enqueue_console_message(self, message):
        """Helper method to enqueue messages to the console queue."""
        self.console_queue.put(message)

    def open_console(self):
        """Open the console window."""
        if not self.console_window or not self.console_window.winfo_exists():
            self.console_window = ConsoleWindow(self.console_queue, self)
        else:
            self.console_window.deiconify()
            self.console_window.focus()

    def watch_console_queue(self):
        """Continuously watch for console messages (if any additional handling is needed)."""
        while self.app_running:
            time.sleep(1)  # Adjust the sleep duration as needed

    def run(self):
        """Run the main application loop."""
        self.mainloop()

    def get_audio_devices(self):
        """Get list of available audio devices."""
        from recorder import get_audio_devices
        return get_audio_devices()

    def on_device_change(self, selected_device_name):
        """Handle changes in the selected audio device."""
        # Find the selected device info
        device_info = next((device for device in self.devices if device['name'] == selected_device_name), None)
        if device_info:
            # Update the config with the new sample rate
            self.config['Settings']['sample_rate'] = str(device_info['defaultSampleRate'])
            self.config['Settings']['audio_device'] = selected_device_name
            with open(CONFIG_FILE, 'w') as configfile:
                self.config.write(configfile)

    def on_closing(self):
        """Handle cleanup when the window is closed."""
        # Stop the application if it's running
        if self.app_running:
            self.stop_app()
        
        # Ensure the process is terminated
        if self.process:
            try:
                self.process.terminate()
                # Wait for a short time for graceful termination
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                # Force kill if process doesn't terminate gracefully
                self.process.kill()
            self.process = None

        # Destroy the console window if it exists
        if self.console_window and self.console_window.winfo_exists():
            self.console_window.destroy()

        # Destroy the main window
        self.quit()
        self.destroy()

    def open_feedback_link(self):
        """Open the feedback link in default web browser"""
        webbrowser.open("https://github.com/evermoving/SystemCaptioner/issues")

if __name__ == "__main__":
    app = App()
    app.run()
