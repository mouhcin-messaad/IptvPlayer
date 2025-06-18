# Python IPTV Player

A simple and intuitive IPTV player built with Python using `tkinter` for the GUI and `python-vlc` for media playback. This player allows you to load M3U playlists, view EPG (Electronic Program Guide) data, search channels, and manage your favorite channels.

---

## Features

* **M3U Playlist Support:** Load channels from any M3U URL.
* **EPG Integration:** Display Electronic Program Guide data from an XMLTV URL, showing current and upcoming programs.
* **Channel Management:**
    * Browse channels by category.
    * Search and filter channels.
    * Add and remove channels from your favorites.
* **VLC Playback:** Utilises VLC Media Player for robust and versatile stream playback.
* **Persistent Configuration:** Automatically saves and loads your M3U and EPG URLs, and favorite channels.
* **User-Friendly Interface:** A clean and easy-to-navigate graphical user interface.

---

## Requirements

Before running the player, ensure you have the following installed:

* **Python 3.x**
* **VLC Media Player:** The `python-vlc` library requires a working installation of VLC Media Player on your system. You can download it from the [official VLC website](https://www.videolan.org/vlc/).

---

## Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/rmj1986/IptvPlayer.git
    cd iptv
    ```

2.  **Install Python dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

    (Create a `requirements.txt` file with the following content: `tkinter`, `requests`, `python-vlc`, `lxml` (or ensure `xml.etree.ElementTree` is sufficient and remove if not needed as a separate install), `configparser`, `json`.)

    For this script, your `requirements.txt` should contain:

    ```
    requests
    python-vlc
    ```
    (Note: `tkinter`, `configparser`, `os`, `threading`, `datetime`, `json`, `re`, `xml.etree.ElementTree` are typically part of Python's standard library and don't need to be listed in `requirements.txt` for `pip` installation.)

---

## How to Run

1.  **Ensure VLC Media Player is installed.**
2.  **Run the script:**

    ```bash
    python iptv.py
    ```
---

## Usage

1.  **Initial Setup:**
    * On the first run, or if no URLs are configured, a pop-up window will appear asking for your M3U and EPG (optional) URLs.
    * Enter the URLs and click "Load & Save". The application will then fetch and parse the channel and EPG data.

2.  **Navigating Channels:**
    * Channels are displayed in the left-hand pane, categorized by their `group-title` from the M3U.
    * Click on a category to expand or collapse it.
    * Click on a channel name to view its EPG information (if available).
    * **Double-click** a channel name to start playback.

3.  **Search and Filter:**
    * Use the "Search Channel" input field to filter channels by name. The list will update as you type.

4.  **Favorites:**
    * **Add to Favorites:** Right-click on a channel in the main channel list and select "Add to favourites".
    * **Remove from Favorites:** Right-click on a channel in the "Favorite Channels" list and select "Remove from favourites".
    * Your favorite channels are saved and loaded automatically.

5.  **EPG Information:**
    * When you select a channel, its current and upcoming program details (if available from the EPG URL) will be displayed in the "EPG Information" section.

6.  **Updating URLs:**
    * Click the "Load/Update URLs" button at the top left to open the URL input pop-up again and update your M3U or EPG sources.

---

## Configuration

The player stores its configuration (M3U URL, EPG URL, and favorite channels) in a file named `config.ini` in the same directory as the script.

---

## Troubleshooting

* **"Failed to initialize VLC" error:** Ensure VLC Media Player is correctly installed on your system and its installation path is accessible to the `python-vlc` library.
* **"Could not fetch data" or "Request timed out" error:**
    * Check your internet connection.
    * Verify that the M3U and EPG URLs are correct and accessible.
* **No EPG data:**
    * Ensure you have provided a valid EPG URL.
    * Verify the EPG data format is compatible (XMLTV format).
    * Some channels in your M3U may not have corresponding `tvg-id` attributes, or the `tvg-id` in your M3U might not match the `channel id` in your EPG data.
* **Stream Errors:** If a channel doesn't play, it might be offline, the URL is incorrect, or there's an issue with the stream itself. Try another channel.

---

## Contributing

Contributions are welcome! If you have suggestions for improvements, bug fixes, or new features, please open an issue or submit a pull request.

---

## License

This project is open-source and available under the [MIT License](LICENSE).
