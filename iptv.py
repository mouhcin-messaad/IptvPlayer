import tkinter as tk
from tkinter import messagebox, scrolledtext, simpledialog
import tkinter.ttk as ttk
import requests
import re
import vlc
import xml.etree.ElementTree as ET
import configparser
import os
import threading
import datetime
import json

class IPTVPlayerApp:
    def __init__(self, master):
        self.master = master
        master.title("Python IPTV Player")
        master.state('zoomed') # Maximize the window on load

        self.config_file = "config.ini"
        self.m3u_url = ""
        self.epg_url = ""
        self.channels = {} # Stores all original channels: {category: [{name, url, tvg_id, category}, ...]}
        self.epg_data = {}
        self.favourite_channel_keys = set() # Stores a set of (channel_name, category) tuples for quick lookup
        self.favourites = {} # Stores actual favourite channel data: {category: [{name, url, tvg_id, category}, ...]}

        self.vlc_instance_created = False
        self.player = None
        try:
            self.instance = vlc.Instance()
            self.player = self.instance.media_player_new()
            self.vlc_instance_created = True

            if self.player:
                event_manager = self.player.event_manager()
                event_manager.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)

        except vlc.VlcError as e:
            messagebox.showerror("VLC Error", f"Failed to initialize VLC: {e}\nPlease ensure VLC Media Player is installed and correctly configured.")
            master.destroy()
            return

        self.create_widgets()
        self.load_config() # Load config, including favourite_channel_keys

        if not self.m3u_url:
            self.master.after(100, self.open_url_input_popup)
        else:
            self.master.after(100, lambda: self._start_initial_data_load())

    def _start_initial_data_load(self):
        self.show_loading_popup("Loading channels and EPG...")
        threading.Thread(target=self._load_data_in_thread, daemon=True).start()

    def create_widgets(self):
        # Top Frame for controls (only for the Load/Update URL button now)
        top_frame = tk.Frame(self.master)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        tk.Button(top_frame, text="Load/Update URLs", command=self.open_url_input_popup).pack(side=tk.LEFT, padx=5)

        # Main content frame
        main_frame = tk.Frame(self.master)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left Column Frame for favourites and Channel List
        left_column_frame = tk.Frame(main_frame)
        left_column_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)

        # Favourites Section
        favourites_frame = tk.LabelFrame(left_column_frame, text="favourites")
        favourites_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=5)

        self.favourites_tree = ttk.Treeview(favourites_frame, show="tree headings", height=5)
        self.favourites_tree.heading("#0", text="favourite Channels")
        self.favourites_tree.column("#0", width=250, minwidth=150, stretch=True)
        self.favourites_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        fav_scrollbar = ttk.Scrollbar(favourites_frame, orient="vertical", command=self.favourites_tree.yview)
        fav_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.favourites_tree.config(yscrollcommand=fav_scrollbar.set)

        self.favourites_tree.bind("<ButtonRelease-1>", self.on_channel_select)
        self.favourites_tree.bind("<Double-1>", self.on_channel_double_click)
        self.favourites_tree.bind("<Button-3>", self.on_channel_right_click)

        # Channel List Frame (below Favourites)
        channel_list_frame = tk.Frame(left_column_frame)
        channel_list_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=0, pady=5)

        # Search/Filter frame inside channel_list_frame
        search_filter_frame = tk.Frame(channel_list_frame)
        search_filter_frame.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))

        tk.Label(search_filter_frame, text="Search Channel:").pack(side=tk.LEFT, padx=(0, 2))
        self.search_entry = ttk.Entry(search_filter_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.search_entry.bind("<KeyRelease>", self.filter_channels)

        # Scrollbar for the main channel Treeview
        scrollbar = ttk.Scrollbar(channel_list_frame, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.channel_tree = ttk.Treeview(channel_list_frame, show="tree headings",
                                         yscrollcommand=scrollbar.set)

        self.channel_tree.heading("#0", text="Channel Name")
        self.channel_tree.column("#0", width=300, minwidth=200, stretch=True)

        self.channel_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.channel_tree.yview)

        self.channel_tree.bind("<ButtonRelease-1>", self.on_channel_select)
        self.channel_tree.bind("<Double-1>", self.on_channel_double_click)
        self.channel_tree.bind("<Button-3>", self.on_channel_right_click)

        # Right: Video Player and EPG Info
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.video_frame = tk.Frame(right_frame, bg="black")
        self.video_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        epg_info_frame = tk.LabelFrame(right_frame, text="EPG Information")
        epg_info_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        self.epg_text = scrolledtext.ScrolledText(epg_info_frame, height=5, wrap=tk.WORD, state=tk.DISABLED)
        self.epg_text.pack(fill=tk.BOTH, expand=True)

        if self.vlc_instance_created and self.player:
            if self.master.winfo_exists():
                self.player.set_hwnd(self.video_frame.winfo_id())

    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(self.config_file):
            config.read(self.config_file)
            if 'Settings' in config:
                self.m3u_url = config['Settings'].get('m3u_url', '')
                self.epg_url = config['Settings'].get('epg_url', '')
                fav_keys_str = config['Settings'].get('favourite_channel_keys', '[]')
                try:
                    loaded_fav_keys = json.loads(fav_keys_str)
                    self.favourite_channel_keys = set(tuple(item) for item in loaded_fav_keys)
                except json.JSONDecodeError:
                    self.favourite_channel_keys = set()

    def save_config(self):
        config = configparser.ConfigParser()
        config['Settings'] = {
            'm3u_url': self.m3u_url,
            'epg_url': self.epg_url,
            'favourite_channel_keys': json.dumps(list(self.favourite_channel_keys))
        }
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)

    def show_loading_popup(self, message="Loading..."):
        self.loading_popup = tk.Toplevel(self.master)
        self.loading_popup.title("Loading Data")
        self.loading_popup.geometry("300x100")
        self.loading_popup.transient(self.master)
        self.loading_popup.grab_set()
        self.loading_popup.protocol("WM_DELETE_WINDOW", lambda: None)

        tk.Label(self.loading_popup, text=message, pady=10).pack()

        self.progress_bar = ttk.Progressbar(self.loading_popup, orient="horizontal", length=200, mode="indeterminate")
        self.progress_bar.pack(pady=10)
        self.progress_bar.start(10)

        self.loading_popup.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.loading_popup.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.loading_popup.winfo_height() // 2)
        self.loading_popup.geometry(f"+{x}+{y}")

    def hide_loading_popup(self):
        if hasattr(self, 'loading_popup') and self.loading_popup.winfo_exists():
            self.progress_bar.stop()
            self.loading_popup.destroy()
            self.master.grab_release()

    def open_url_input_popup(self):
        if hasattr(self, 'url_input_popup') and self.url_input_popup.winfo_exists():
            self.url_input_popup.destroy()

        self.url_input_popup = tk.Toplevel(self.master)
        self.url_input_popup.title("Enter/Update URLs")
        self.url_input_popup.geometry("400x200")
        self.url_input_popup.transient(self.master)
        self.url_input_popup.grab_set()

        tk.Label(self.url_input_popup, text="M3U URL:").pack(pady=5)
        self.m3u_entry = tk.Entry(self.url_input_popup, width=50)
        self.m3u_entry.pack(pady=5)
        self.m3u_entry.insert(0, self.m3u_url)

        tk.Label(self.url_input_popup, text="EPG URL:").pack(pady=5)
        self.epg_entry = tk.Entry(self.url_input_popup, width=50)
        self.epg_entry.pack(pady=5)
        self.epg_entry.insert(0, self.epg_url)

        self.load_save_button = tk.Button(self.url_input_popup, text="Load & Save", command=self._start_loading_from_popup)
        self.load_save_button.pack(pady=10)

        self.url_input_popup.protocol("WM_DELETE_WINDOW", self._on_url_popup_close_attempt)

        self.url_input_popup.update_idletasks()
        x = self.master.winfo_x() + (self.master.winfo_width() // 2) - (self.url_input_popup.winfo_width() // 2)
        y = self.master.winfo_y() + (self.master.winfo_height() // 2) - (self.url_input_popup.winfo_height() // 2)
        self.url_input_popup.geometry(f"+{x}+{y}")

    def _on_url_popup_close_attempt(self):
        if not self.m3u_url and not (hasattr(self, 'loading_popup') and self.loading_popup.winfo_exists()):
            if messagebox.askyesno("Exit Application?", "No M3U URL loaded. Do you want to exit the application?"):
                self.master.destroy()
        else:
            self.url_input_popup.destroy()
            self.master.grab_release()

    def _start_loading_from_popup(self):
        new_m3u_url = self.m3u_entry.get()
        new_epg_url = self.epg_entry.get()

        if not new_m3u_url:
            messagebox.showerror("Error", "M3U URL cannot be empty.")
            return

        self.m3u_entry.config(state=tk.DISABLED)
        self.epg_entry.config(state=tk.DISABLED)
        self.load_save_button.config(state=tk.DISABLED)

        self.m3u_url = new_m3u_url
        self.epg_url = new_epg_url

        self.show_loading_popup("Loading channels and EPG...")

        threading.Thread(target=self._load_data_in_thread, daemon=True).start()

    def _load_data_in_thread(self):
        success = False
        error_message = ""
        try:
            self.channels = {}
            self.epg_data = {}

            m3u_content = requests.get(self.m3u_url, timeout=20).text
            self.parse_m3u(m3u_content)

            if self.epg_url:
                epg_content = requests.get(self.epg_url, timeout=20).text
                self.parse_epg(epg_content)
            success = True

        except requests.exceptions.Timeout:
            error_message = "Request timed out. Please check the URL or your internet connection."
        except requests.exceptions.RequestException as e:
            error_message = f"Could not fetch data: {e}"
        except Exception as e:
            error_message = f"An error occurred during parsing: {e}"
        finally:
            self.master.after(0, self._on_load_data_complete, success, error_message)

    def _on_load_data_complete(self, success, error_message):
        self.hide_loading_popup()

        if hasattr(self, 'url_input_popup') and self.url_input_popup.winfo_exists():
            self.m3u_entry.config(state=tk.NORMAL)
            self.epg_entry.config(state=tk.NORMAL)
            self.load_save_button.config(state=tk.NORMAL)
            self.url_input_popup.destroy()
            self.master.grab_release()

        if success:
            self.populate_channel_tree(self.channels)
            self._rebuild_favourites_from_all_channels()
            self.populate_favourites_tree(self.favourites)
            self.save_config()
            self.search_entry.delete(0, tk.END)
            self.search_entry.focus_set()
        else:
            messagebox.showerror("Error", error_message)
            if not self.m3u_url:
                self.open_url_input_popup()
            else:
                messagebox.showwarning("Warning", "Previous URLs might still be in use if you don't update.")

    def parse_m3u(self, m3u_content):
        lines = m3u_content.strip().split('\n')
        current_channel_info = {}

        parsed_channels_temp = {}

        for line in lines:
            line = line.strip()
            if line.startswith("#EXTINF:"):
                match = re.search(r'group-title="([^"]*)"', line)
                category = match.group(1) if match else "Uncategorized"

                match = re.search(r',(.+)$', line)
                channel_name = match.group(1).strip() if match else "Unknown Channel"

                tvg_id_match = re.search(r'tvg-id="([^"]*)"', line)
                tvg_id = tvg_id_match.group(1) if tvg_id_match else None

                current_channel_info = {
                    "name": channel_name,
                    "category": category, 
                    "tvg_id": tvg_id,
                }
            elif line and not line.startswith("#"):
                if current_channel_info:
                    channel_url = line
                    # Get category from current_channel_info, where it's correctly stored
                    category = current_channel_info["category"]
                    channel_name = current_channel_info["name"]
                    tvg_id = current_channel_info["tvg_id"]

                    if category not in parsed_channels_temp:
                        parsed_channels_temp[category] = []
                    parsed_channels_temp[category].append({
                        "name": channel_name,
                        "url": channel_url,
                        "tvg_id": tvg_id,
                        "category": category # Ensures category is part of the final channel dict
                    })
                current_channel_info = {}
        self.channels = parsed_channels_temp

    def populate_channel_tree(self, channels_to_display):
        self.channel_tree.delete(*self.channel_tree.get_children())
        for category in sorted(channels_to_display.keys()):
            category_node = self.channel_tree.insert("", "end", text=category, open=True)
            for channel in channels_to_display[category]:
                self.channel_tree.insert(category_node, "end", text=channel["name"],
                                         tags=(channel["url"], channel["tvg_id"], channel["category"], channel["name"]))

    def populate_favourites_tree(self, favourites_to_display):
        self.favourites_tree.delete(*self.favourites_tree.get_children())
        if not favourites_to_display:
            self.favourites_tree.insert("", "end", text="No favourites added yet.")
            return

        for category in sorted(favourites_to_display.keys()):
            category_node = self.favourites_tree.insert("", "end", text=category, open=True)
            for channel in favourites_to_display[category]:
                self.favourites_tree.insert(category_node, "end", text=channel["name"],
                                           tags=(channel["url"], channel["tvg_id"], channel["category"], channel["name"]))

    def parse_epg(self, epg_content):
        try:
            root = ET.fromstring(epg_content)
            for channel_elem in root.findall('channel'):
                channel_id = channel_elem.get('id')
                if channel_id:
                    self.epg_data[channel_id] = []
                    for display_name_elem in channel_elem.findall('display-name'):
                        if display_name_elem.text:
                            self.epg_data[channel_id].append({"display_name": display_name_elem.text.strip()})

            for programme_elem in root.findall('programme'):
                channel_id = programme_elem.get('channel')
                if channel_id in self.epg_data:
                    title_elem = programme_elem.find('title')
                    desc_elem = programme_elem.find('desc')
                    start_time = programme_elem.get('start')
                    stop_time = programme_elem.get('stop')

                    program_info = {
                        "title": title_elem.text if title_elem is not None and title_elem.text else "N/A",
                        "description": desc_elem.text if desc_elem is not None and desc_elem.text else "No description",
                        "start": start_time,
                        "stop": stop_time,
                    }
                    if program_info["title"] != "N/A" or program_info["description"] != "No description":
                        self.epg_data[channel_id].append(program_info)
        except ET.ParseError as e:
            raise ValueError(f"EPG XML parsing error: {e}")
        except Exception as e:
            raise ValueError(f"General EPG parsing error: {e}")

    def filter_channels(self, event=None):
        filter_text = self.search_entry.get().strip().lower()
        filtered_channels_temp = {}

        if not filter_text:
            self.populate_channel_tree(self.channels)
            return

        for category, channels_list in self.channels.items():
            for channel in channels_list:
                if filter_text in channel["name"].lower():
                    if category not in filtered_channels_temp:
                        filtered_channels_temp[category] = []
                    filtered_channels_temp[category].append(channel)

        self.populate_channel_tree(filtered_channels_temp)

    def _rebuild_favourites_from_all_channels(self):
        self.favourites = {}
        for category_name, channels_list in self.channels.items(): # 'category_name' is the key
            for channel in channels_list: # 'channel' is a dict containing 'category'
                # Use channel["category"] to form the key, which is now consistently available
                channel_key = (channel["name"], channel["category"])
                if channel_key in self.favourite_channel_keys:
                    if category_name not in self.favourites:
                        self.favourites[category_name] = []
                    # Add the full channel dict to favourites
                    self.favourites[category_name].append(channel)

    def add_to_favourites(self, channel_info):
        channel_name = channel_info["name"]
        category = channel_info["category"]
        channel_key = (channel_name, category)

        if channel_key not in self.favourite_channel_keys:
            self.favourite_channel_keys.add(channel_key)
            if category not in self.favourites:
                self.favourites[category] = []
            self.favourites[category].append(channel_info)
            self.populate_favourites_tree(self.favourites)
            self.save_config()
            messagebox.showinfo("favourites", f"'{channel_name}' added to favourites.")
        else:
            messagebox.showinfo("favourites", f"'{channel_name}' is already in favourites.")

    def remove_from_favourites(self, channel_info):
        channel_name = channel_info["name"]
        category = channel_info["category"]
        channel_key = (channel_name, category)

        if channel_key in self.favourite_channel_keys:
            self.favourite_channel_keys.remove(channel_key)
            if category in self.favourites:
                self.favourites[category] = [
                    c for c in self.favourites[category]
                    if not (c["name"] == channel_name and c["category"] == category)
                ]
                if not self.favourites[category]:
                    del self.favourites[category]
            self.populate_favourites_tree(self.favourites)
            self.save_config()
            messagebox.showinfo("favourites", f"'{channel_name}' removed from favourites.")
        else:
            messagebox.showinfo("favourites", f"'{channel_name}' is not in favourites.")

    def _on_vlc_error(self, event):
        self.master.after(0, self._handle_vlc_error_on_main_thread)

    def _handle_vlc_error_on_main_thread(self):
        if self.player:
            self.player.stop()

        messagebox.showerror("Stream Error", "The selected stream encountered an error and could not be played. Please try another channel.")
        self.display_epg_info(None)

    def on_channel_select(self, event):
        widget = event.widget
        selected_items = widget.selection()
        if not selected_items:
            self.display_epg_info(None)
            return

        item_id = selected_items[0]

        if not widget.parent(item_id):
            self.display_epg_info(None)
            return

        item_tags = widget.item(item_id, "tags")
        if item_tags and len(item_tags) > 1:
            tvg_id = item_tags[1]
            self.display_epg_info(tvg_id)
        else:
            self.display_epg_info(None)

    def on_channel_double_click(self, event):
        widget = event.widget
        item_id = widget.selection()[0]
        if not widget.parent(item_id):
            messagebox.showinfo("Info", "Please double-click a channel, not a category.")
            return

        item_tags = widget.item(item_id, "tags")

        if item_tags:
            channel_url = item_tags[0]
            self.play_stream(channel_url)
        else:
            messagebox.showinfo("Info", "Could not retrieve channel information.")

    def on_channel_right_click(self, event):
        widget = event.widget
        item_id = widget.identify_row(event.y)

        if not item_id or not widget.parent(item_id):
            return

        widget.selection_set(item_id)

        item_tags = widget.item(item_id, "tags")
        if not item_tags or len(item_tags) < 4:
            return

        channel_info = {
            "name": item_tags[3],
            "url": item_tags[0],
            "tvg_id": item_tags[1],
            "category": item_tags[2]
        }

        context_menu = tk.Menu(self.master, tearoff=0)
        channel_key = (channel_info["name"], channel_info["category"])

        if channel_key in self.favourite_channel_keys:
            context_menu.add_command(label="Remove from favourites",
                                      command=lambda: self.remove_from_favourites(channel_info))
        else:
            context_menu.add_command(label="Add to favourites",
                                      command=lambda: self.add_to_favourites(channel_info))

        context_menu.post(event.x_root, event.y_root)

    def play_stream(self, url):
        if not self.player:
            messagebox.showerror("Playback Error", "VLC player not initialized. Cannot play stream.")
            return

        if self.player.is_playing():
            self.player.stop()

        media = self.instance.media_new(url)
        self.player.set_media(media)
        self.player.play()

    def display_epg_info(self, tvg_id):
        self.epg_text.config(state=tk.NORMAL)
        self.epg_text.delete(1.0, tk.END)

        if tvg_id and tvg_id in self.epg_data:
            info = self.epg_data[tvg_id]
            epg_display_text = ""
            current_time = datetime.datetime.now(datetime.timezone.utc) # Get current UTC time

            display_name = None
            programs_to_display = []
            for item in info:
                if "display_name" in item:
                    display_name = item["display_name"]
                elif "title" in item:
                    try:
                        start_dt = datetime.datetime.strptime(item['start'][:14], "%Y%m%d%H%M%S")
                        stop_dt = datetime.datetime.strptime(item['stop'][:14], "%Y%m%d%H%M%S")

                        start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                        stop_dt = stop_dt.replace(tzinfo=datetime.timezone.utc)

                        if stop_dt >= current_time:
                            programs_to_display.append(item)

                    except ValueError:
                        pass
            
            if display_name:
                epg_display_text += f"Channel: {display_name}\n\n"

            if not programs_to_display: # Use programs_to_display after filtering
                epg_display_text += "No current or upcoming EPG program data available for this channel."
            else:
                # Sort programs by start time
                programs_to_display.sort(key=lambda x: datetime.datetime.strptime(x['start'][:14], "%Y%m%d%H%M%S"))

                for item in programs_to_display:
                    try:
                        start_dt = datetime.datetime.strptime(item['start'][:14], "%Y%m%d%H%M%S")
                        stop_dt = datetime.datetime.strptime(item['stop'][:14], "%Y%m%d%H%M%S")

                        start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                        stop_dt = stop_dt.replace(tzinfo=datetime.timezone.utc)

                        is_current = start_dt <= current_time < stop_dt
                        if is_current:
                            epg_display_text += "--- NOW PLAYING ---\n"

                        local_timezone = datetime.datetime.now().astimezone().tzinfo
                        local_start = start_dt.astimezone(local_timezone)
                        local_stop = stop_dt.astimezone(local_timezone)

                        epg_display_text += f"  Title: {item['title']}\n"
                        epg_display_text += f"  Time: {local_start.strftime('%H:%M')} - {local_stop.strftime('%H:%M')} (Local Time)\n"
                    except ValueError:
                        epg_display_text += f"  Title: {item['title']}\n"
                        epg_display_text += f"  Time: N/A (Format Error)\n"

                    epg_display_text += f"  Desc: {item['description']}\n\n"
        else:
            epg_display_text = "No EPG data available for this channel or Stream Error."

        self.epg_text.insert(tk.END, epg_display_text)
        self.epg_text.config(state=tk.DISABLED)

    def on_closing(self):
        if self.player and self.player.is_playing():
            self.player.stop()
        self.master.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = IPTVPlayerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
