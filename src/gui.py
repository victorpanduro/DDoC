from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, StringVar, messagebox
import utils
from utils import Data
import webbrowser

class GUI:

    def __init__(self):
        self.data: Data = {}
        utils.clear_tmp_images()
        
        # Create the main window
        self.root = tk.Tk()
        self.root.config(background = "black")
        self.root.title("Daily Dose of Cosmos") 
        self.root.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.icon_photo = ImageTk.PhotoImage(Image.open(utils.ICON_PATH)) 
        self.root.iconphoto(True, self.icon_photo)

        # Variables
        self.api_key_var = StringVar(value = utils.get_api_key())
        self.date_entry_var = StringVar(value = "")
        self.original_image = None
        self.current_photo = None

        # --- Style ---
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.style.configure("apod.TButton",
            background = "#2b2b2b",
            foreground = "white",
            padding = 6,
            borderwidth = 0
        )
        self.style.map("apod.TButton",
            background = [("pressed", "#8a8a8a"), ("active", "#bdbbbb")],
            foreground = [("pressed", "black"), ("active", "black")]
        )
        self.style.configure("apod.TEntry",
            background = "black",
            foreground = "black",
            padding = 3,
            borderwidth = 0
        )
        # --- ---
        
        # Widgets
        # --- Header ---
        self.header = ttk.Label(
            self.root, 
            text = "Ready for your Daily Dose of Cosmos?",
            font = ("Arial", 14, "bold"),
            foreground = "white",
            background = "black",
        )
        self.header.pack(padx = 20, pady = (50, 20))
        # --- ---

        # --- Frame ---
        self.frame = tk.Frame(
            self.root,
            background = "black"
        )
        self.frame.pack(padx = 20, pady = 20, ipadx = 20, ipady = 20)
        # --- --- 

        # --- Key entry ---
        self.api_key_entry_label = ttk.Label(
            self.frame, 
            text = "Enter your NASA API key:", 
            foreground = "white", 
            background = "black"
        )
        self.api_key_entry_label.grid(row = 0, column = 0, padx = 10, pady = 5)

        self.api_key_entry = ttk.Entry(
            self.frame, 
            textvariable = self.api_key_var, 
            font = ("Arial", 10),
            width = 45,
            style = "TEntry",
            justify = "center",
            validate = "key"
        )
        self.api_key_entry.grid(row = 1, column = 0, padx = 10, pady = 5)
        # --- ---

        # --- Fetch button ---
        self.fetch_button = ttk.Button(
            self.frame, 
            text = "Fetch APOD", 
            command = self.on_fetch_click,
            style = "apod.TButton"
        )
        self.fetch_button.grid(row = 0, column = 2, rowspan = 2, padx = 20, pady = 10)
        # --- ---

        # --- Date entry ---
        self.date_entry_label = ttk.Label(
            self.frame, 
            text = "Enter date (YYYY-MM-DD):", 
            font = ("Arial", 10), 
            background = "black", 
            foreground = "white",
        )
        self.date_entry_label.grid(row = 0, column = 1, padx = 10, pady = 5)

        self.date_entry = ttk.Entry(
            self.frame, 
            textvariable = self.date_entry_var, 
            font = ("Arial", 10),
            width = 15,
            style = "TEntry",
            justify = "center",

        )
        self.date_entry.grid(row = 1, column = 1, padx = 10, pady = 5)
        # --- ---

        self.root.mainloop()  # Start the event loop


    def on_close(self):
        utils.clear_tmp_images()
        self.root.destroy()
    

    def on_fetch_click(self): 
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showerror("Missing API key", "Please enter your NASA API key.")
            return
        utils.save_api_key(key)

        date = self.date_entry_var.get().strip()
        if not date:
            messagebox.showinfo("Missing date", "APOD will fetch the picture for today.")
        elif utils.use_regex_and_datetime(date) == False:
            messagebox.showerror(
                "Error", 
                "Please input a valid date in the format YYYY-MM-DD from 1995-06-16 until today."
            )
            return
        
        if not self.data or date != self.data["date"]:
            try:
                self.data = utils.fetch_and_parse_response_to_data(key, date)
                if self.data == None or not self.data:
                    return
            except (ValueError, RuntimeError) as ex:
                messagebox.showerror("Error", str(ex))
                return 
            
            self.open_apod_window(self.data)
    

    def resize_image(self, event = None):
        if self.original_image is None:
            return

        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            return

        display_image = self.original_image.copy()
        display_image.thumbnail(
            (canvas_width, canvas_height),
            Image.Resampling.LANCZOS
        )

        photo = ImageTk.PhotoImage(display_image)
        self.image_reference["photo"] = photo

        self.image_canvas.delete("all")
        self.image_canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image = photo,
            anchor = "center"
        )


    def open_apod_window(self, data: Data):
        self.apod_window = tk.Toplevel(self.root)
        self.apod_window.title("APOD")
        self.apod_window.config(background = "black")
        is_image = data["media_type"] == "image"

        # --- Title ---
        self.title_label = ttk.Label(
            self.apod_window,
            text = data["title"],
            font = ("Arial", 16, "bold"),
            background = "black",
            foreground = "white"
        )
        self.title_label.pack(padx = 20, pady = (20, 5))

        # --- Date ---
        self.date_label = ttk.Label(
            self.apod_window,
            text = data["date"],
            font = ("Arial", 12),
            background = "black",
            foreground = "white"
        )
        self.date_label.pack(padx = 20, pady = 5)

        # --- Copyright ---
        self.copyright_label = ttk.Label(
            self.apod_window,
            text = f'Credit/Copyright: {data["copyright"]}',
            font = ("Arial", 8),
            background = "black",
            foreground = "white"
        )
        self.copyright_label.pack(pady = 5)

        if is_image:
            self.original_image = None
            self.image_reference = {"photo": None}
            self.apod_window.state("zoomed")
            # --- Image canvas ---
            self.image_canvas = tk.Canvas(
                self.apod_window, 
                background = "black", 
                highlightthickness = 0
            )
            self.image_canvas.pack(fill = "both", expand = True, padx = 10, pady = 10)
            self.image_canvas.bind("<Configure>", self.resize_image)
        
        # --- Explanation ---
        self.explanation_text = tk.Text(
            self.apod_window,
            wrap = "word",
            font = ("Arial", 10),
            background = "black",
            foreground = "white",
            relief = "flat",
        )
        if is_image:
            self.explanation_text.configure(height = 5)
        else:
            self.explanation_text.configure(height = 10)
        self.explanation_text.pack(fill = "x", padx = 20, pady = (10, 20))
        self.explanation_text.insert("1.0", data["explanation"])
        self.explanation_text.config(state = "disabled")

        try:
            if data["media_type"] == "image":
                image_path = utils.fetch_and_save_image(data)

                if not image_path:
                    return

                with Image.open(image_path) as image:
                    self.original_image = image.copy()

                self.apod_window.after_idle(self.resize_image)

            elif data["media_type"] == "video":
                self.apod_window.state("normal")

                video_label = ttk.Label(
                    self.apod_window,
                    text = "This APOD is a video",
                    font = ("Arial", 12, "bold"),
                    background = "black",
                    foreground = "white",
                )
                video_label.pack(before = self.explanation_text, padx = 20, pady = 10)

                open_video_button = ttk.Button(
                    self.apod_window,
                    text = "Open video in browser",
                    command = lambda: webbrowser.open(data["url"]),
                    style = "apod.TButton"
                )
                open_video_button.pack(before = self.explanation_text, padx = 20, pady = 10)

            else:
                messagebox.showinfo("Unsupported media type", f"Cannot display media type: {data['media_type']}")

        except ValueError as ex:
            messagebox.showerror("Image error", str(ex))
