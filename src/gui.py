import tkinter as tk
from tkinter import ttk, StringVar, messagebox
import webbrowser
from PIL import Image, ImageTk
import utils
from utils import Data

class GUI:
    def __init__(self) -> None:
        self.data: Data = {}
        utils.clear_cache()

        self.root = tk.Tk()
        self.root.config(background = "black")
        self.root.title("Daily Dose of Cosmos")
        self.root.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        if utils.ICON_PATH.is_file():
            self.icon_photo = ImageTk.PhotoImage(Image.open(utils.ICON_PATH))
            self.root.iconphoto(True, self.icon_photo)

        self.api_key_var = StringVar(value = utils.get_api_key())
        self.date_entry_var = StringVar(value = "")

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
            padding = 3
        )

        self.header = ttk.Label(
            self.root,
            text = "Ready for your Daily Dose of Cosmos?",
            font = ("Arial", 14, "bold"),
            foreground = "white",
            background = "black",
        )
        self.header.pack(padx = 20, pady = (50, 20))

        self.frame = tk.Frame(
            self.root,
            background = "black"
        )
        self.frame.pack(padx = 20, pady = 20, ipadx = 20, ipady = 20)

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
            justify = "center"
        )
        self.api_key_entry.grid(row = 1, column = 0, padx = 10, pady = 5)

        self.fetch_button = ttk.Button(
            self.frame,
            text = "Fetch APOD",
            command = self.on_fetch_click,
            style = "apod.TButton"
        )
        self.fetch_button.grid(row = 0, column = 2, rowspan = 2, padx = 20, pady = 10)

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

        self.root.mainloop()


    def on_close(self) -> None:
        utils.clear_cache()
        self.root.destroy()


    def on_fetch_click(self) -> None:
        key = self.api_key_var.get().strip()
        if not key:
            messagebox.showerror("Missing API key", "Please enter your NASA API key.")
            return
        utils.save_api_key(key)

        date = self.date_entry_var.get().strip()
        if not date:
            messagebox.showinfo("Missing date", "APOD will fetch the picture for today.")
        elif utils.use_regex_and_datetime(date) is False:
            messagebox.showerror(
                "Error",
                "Please input a valid date in the format YYYY-MM-DD from 1995-06-16 until today."
            )
            return

        # TODO tilføj 'temp = hvis checkbox er tikket' check
        try:
            self.data = utils.fetch_and_parse_response_to_data(key, True, date)
            if self.data is None or not self.data:
                return
        except (ValueError, RuntimeError) as ex:
            messagebox.showerror("Error", str(ex))
            return

        self.open_apod_window(self.data)


    def resize_image(self, image_canvas, image_state) -> None:
        original_image = image_state["original"]
        if original_image is None:
            return

        canvas_width = image_canvas.winfo_width()
        canvas_height = image_canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            return

        display_image = original_image.copy()
        display_image.thumbnail(
            (canvas_width, canvas_height),
            Image.Resampling.LANCZOS
        )

        photo = ImageTk.PhotoImage(display_image)
        image_state["photo"] = photo

        image_canvas.delete("all")
        image_canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image = photo,
            anchor = "center"
        )


    def open_apod_window(self, data: Data) -> None:
        apod_window = tk.Toplevel(self.root)
        apod_window.title("Daily Dose of Cosmos")
        apod_window.config(background = "black")
        is_image = data["media_type"] == "image"

        title_label = ttk.Label(
            apod_window,
            text = data["title"],
            font = ("Arial", 16, "bold"),
            background = "black",
            foreground = "white"
        )
        title_label.pack(padx = 20, pady = (20, 5))

        date_label = ttk.Label(
            apod_window,
            text = data["date"],
            font = ("Arial", 12),
            background = "black",
            foreground = "white"
        )
        date_label.pack(padx = 20, pady = 5)

        copyright_label = ttk.Label(
            apod_window,
            text = f'Credit/Copyright: {data["copyright"]}',
            font = ("Arial", 8),
            background = "black",
            foreground = "white"
        )
        copyright_label.pack(pady = 5)

        if is_image:
            image_state = {"original": None, "photo": None}
            apod_window.state("zoomed")
            apod_window.focus()

            image_canvas = tk.Canvas(
                apod_window,
                background = "black",
                highlightthickness = 0
            )
            image_canvas.pack(fill = "both", expand = True, padx = 10, pady = 10)
            image_canvas.bind(
                "<Configure>",
                lambda resize: self.resize_image(image_canvas, image_state)
            )

        explanation_text = tk.Text(
            apod_window,
            wrap = "word",
            font = ("Arial", 10),
            background = "black",
            foreground = "white",
            relief = "flat",
        )
        if is_image:
            explanation_text.configure(height = 5)
        else:
            explanation_text.configure(height = 10)
        explanation_text.pack(fill = "x", padx = 20, pady = (10, 20))
        explanation_text.insert("1.0", data["explanation"])
        explanation_text.config(state = "disabled")

        try:
            if data["media_type"] == "image":
                image_path = utils.fetch_and_save_image(data)

                if not image_path:
                    return

                with Image.open(image_path) as image:
                    image_state["original"] = image.copy()

                apod_window.after_idle(lambda: self.resize_image(image_canvas, image_state))

            elif data["media_type"] == "video":
                apod_window.state("normal")

                video_label = ttk.Label(
                    apod_window,
                    text = "This APOD is a video",
                    font = ("Arial", 12, "bold"),
                    background = "black",
                    foreground = "white",
                )
                video_label.pack(before = explanation_text, padx = 20, pady = 10)

                open_video_button = ttk.Button(
                    apod_window,
                    text = "Open video in browser",
                    command = lambda: webbrowser.open(data["url"]),
                    style = "apod.TButton"
                )
                open_video_button.pack(before = explanation_text, padx = 20, pady = 10)

            else:
                messagebox.showinfo("Unsupported media type",
                                    f"Cannot display media type: {data['media_type']}")

        except ValueError as ex:
            messagebox.showerror("Image error", str(ex))
