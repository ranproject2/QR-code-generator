import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
from tkinter import ttk
import qrcode
from PIL import Image, ImageTk, ImageDraw
import io
import sqlite3
import os
from datetime import datetime
import random
import webbrowser
import base64
import csv
try:
    import cv2
    from pyzbar.pyzbar import decode
    import numpy as np
    scanner_available = True
except ImportError:
    scanner_available = False

# Connect to SQLite database (it will create the database if it doesn't exist)
conn = sqlite3.connect('user_data.db')  # Database file
cursor = conn.cursor()

# Create the users table if it doesn't already exist
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT)''')

# Check if is_admin column exists, add it if it doesn't
cursor.execute("PRAGMA table_info(users)")
columns = [column[1] for column in cursor.fetchall()]
if "is_admin" not in columns:
    cursor.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
    conn.commit()

# Create history table to store generated QR codes
cursor.execute('''CREATE TABLE IF NOT EXISTS qr_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    qr_type TEXT,
                    content TEXT,
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id))''')

# Create favorites table to store favorite QR code settings
cursor.execute('''CREATE TABLE IF NOT EXISTS favorites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    name TEXT,
                    fg_color TEXT,
                    bg_color TEXT,
                    box_size INTEGER,
                    border_size INTEGER,
                    error_level TEXT,
                    pattern TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id))''')

# Create analytics table to track QR code usage
cursor.execute('''CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    qr_type TEXT,
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id))''')

# Check if admin user exists, if not create it
cursor.execute("SELECT id FROM users WHERE username = ?", ("Admin",))
admin_exists = cursor.fetchone()
if not admin_exists:
    cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", 
                  ("Admin", "RANPROJECT", 1))
    conn.commit()

# Color dictionaries mapping names to hex codes
foreground_colors = {
    "Black": "#000000",
    "Red": "#FF0000",
    "Green": "#00AA00",
    "Blue": "#0000FF",
    "Purple": "#800080",
    "Navy": "#000080",
    "Teal": "#008080",
    "Maroon": "#800000",
    "Orange": "#FFA500",
    "Brown": "#A52A2A",
    "Magenta": "#FF00FF",
    "Gold": "#FFD700",
    "Crimson": "#DC143C",
    "Forest Green": "#228B22",
    "Royal Blue": "#4169E1"
}

background_colors = {
    "White": "#FFFFFF",
    "Light Gray": "#F0F0F0",
    "Light Pink": "#FFE0E0",
    "Light Green": "#E0FFE0",
    "Light Blue": "#E0E0FF",
    "Light Yellow": "#FFFFC0",
    "Light Cyan": "#C0FFFF",
    "Light Purple": "#FFE0FF",
    "Beige": "#F5F5DC",
    "Mint": "#F5FFFA",
    "Lavender": "#E6E6FA",
    "Ivory": "#FFFFF0",
    "Cream": "#FFFDD0",
    "Sky Blue": "#87CEEB",
    "Peach": "#FFDAB9"
}

# QR code templates presets
qr_templates = {
    "Standard": {
        "fg": "Black",
        "bg": "White",
        "box_size": "5",
        "border": "2",
        "ecc": "M (15%)",
        "pattern": "Standard"
    },
    "Professional": {
        "fg": "Navy",
        "bg": "Light Gray",
        "box_size": "6",
        "border": "2",
        "ecc": "H (30%)",
        "pattern": "Standard"
    },
    "Colorful": {
        "fg": "Purple",
        "bg": "Light Yellow",
        "box_size": "7",
        "border": "3",
        "ecc": "Q (25%)",
        "pattern": "Dots"
    },
    "High Contrast": {
        "fg": "Black",
        "bg": "Light Yellow",
        "box_size": "8",
        "border": "4",
        "ecc": "H (30%)",
        "pattern": "Standard"
    },
    "Modern": {
        "fg": "Royal Blue",
        "bg": "White",
        "box_size": "6",
        "border": "2",
        "ecc": "M (15%)",
        "pattern": "Rounded"
    },
    "Corporate": {
        "fg": "Teal",
        "bg": "White",
        "box_size": "5",
        "border": "2", 
        "ecc": "M (15%)",
        "pattern": "Standard"
    }
}

# Global variables
generated_img = None
current_user_id = None
is_admin = False
logo_path = None
is_dark_mode = False
qr_data = None  # Store the last generated QR code data
qr_format = "PNG"  # Default export format

# Function to view database tables - Admin only
def view_database():
    if not is_admin:
        messagebox.showinfo("Admin Only", "Database access is restricted to administrators only.")
        return
    
    # Create database viewer window
    db_window = tk.Toplevel(root)
    db_window.title("Database Viewer (Admin Only)")
    db_window.geometry("800x500")
    db_window.config(bg=bg_color)
    
    # Create notebook with tabs for each table
    db_tabs = ttk.Notebook(db_window)
    db_tabs.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Function to create a table view
    def create_table_view(table_name, parent):
        frame = tk.Frame(parent, bg=bg_color)
        frame.pack(fill="both", expand=True)
        
        # Create Treeview for data display
        columns_frame = tk.Frame(frame, bg=bg_color)
        columns_frame.pack(fill="both", expand=True)
        
        # Get column names
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Create Treeview
        tree = ttk.Treeview(columns_frame, columns=columns, show="headings")
        tree.pack(fill="both", expand=True, side="left")
        
        # Add scrollbars
        yscrollbar = ttk.Scrollbar(columns_frame, orient="vertical", command=tree.yview)
        yscrollbar.pack(side="right", fill="y")
        
        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        xscrollbar.pack(side="bottom", fill="x")
        
        tree.configure(yscrollcommand=yscrollbar.set, xscrollcommand=xscrollbar.set)
        
        # Set column headings
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100, minwidth=50)
        
        # Get data and populate
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        for i, row in enumerate(rows):
            tree.insert("", "end", values=row)
            
        # Add row count label
        count_label = tk.Label(frame, text=f"Total rows: {len(rows)}", bg=bg_color, fg=fg_color)
        count_label.pack(pady=5)
            
        return frame
    
    # Function to refresh data
    def refresh_data():
        # Clear the notebook
        for tab in db_tabs.tabs():
            db_tabs.forget(tab)
        
        # Recreate tabs with fresh data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            if table_name != "sqlite_sequence":  # Skip SQLite internal tables
                tab = create_table_view(table_name, db_tabs)
                db_tabs.add(tab, text=table_name)
    
    # Create a tab for each table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    for table in tables:
        table_name = table[0]
        if table_name != "sqlite_sequence":  # Skip SQLite internal tables
            tab = create_table_view(table_name, db_tabs)
            db_tabs.add(tab, text=table_name)
    
    # Add control buttons at the bottom
    button_frame = tk.Frame(db_window, bg=bg_color)
    button_frame.pack(pady=10)
    
    # Refresh button
    refresh_button = tk.Button(button_frame, text="Refresh Data", command=refresh_data,
                              bg=button_bg_color, fg=button_fg_color,
                              activebackground=button_active_bg, activeforeground=button_active_fg)
    refresh_button.pack(side="left", padx=5)
    
    # Export button
    export_button = tk.Button(button_frame, text="Export to CSV", command=export_database,
                             bg=button_bg_color, fg=button_fg_color,
                             activebackground=button_active_bg, activeforeground=button_active_fg)
    export_button.pack(side="left", padx=5)
    
    # Close button
    close_button = tk.Button(button_frame, text="Close", command=db_window.destroy,
                            bg=button_bg_color, fg=button_fg_color,
                            activebackground=button_active_bg, activeforeground=button_active_fg)
    close_button.pack(side="left", padx=5)

# Function to export database to CSV - Admin only
def export_database():
    if not is_admin:
        messagebox.showinfo("Admin Only", "Database export is restricted to administrators only.")
        return
    
    folder_path = filedialog.askdirectory(title="Select Export Folder")
    if not folder_path:
        return
        
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    
    exported_files = []
    for table in tables:
        table_name = table[0]
        if table_name != "sqlite_sequence":  # Skip SQLite internal tables
            export_path = os.path.join(folder_path, f"{table_name}.csv")
            
            # Get column names
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Get data
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Write to CSV
            try:
                with open(export_path, 'w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(columns)  # Write header
                    writer.writerows(rows)    # Write data
                exported_files.append(f"{table_name}.csv")
            except Exception as e:
                messagebox.showerror("Export Error", f"Error exporting {table_name}: {str(e)}")
    
    if exported_files:
        messagebox.showinfo("Export Complete", 
                         f"Database tables exported to {folder_path}:\n" + 
                         "\n".join(exported_files))

# Function to apply a QR template
def apply_template():
    selected_template = template_var.get()
    template = qr_templates[selected_template]
    
    # Set all options according to the template
    fg_color_var.set(template["fg"])
    bg_color_var.set(template["bg"])
    box_size_var.set(template["box_size"])
    border_size_var.set(template["border"])
    error_correction_var.set(template["ecc"])
    
    
    messagebox.showinfo("Template Applied", f"Applied '{selected_template}' template")

# Function to save current settings as favorite
def save_favorite():
    if not current_user_id:
        messagebox.showwarning("Login Required", "Please log in to save favorites")
        return
        
    # Ask for a name for this favorite
    favorite_name = simpledialog.askstring("Save Favorite", "Enter a name for this favorite QR style:")
    if not favorite_name:
        return
        
    # Save current settings to database
    cursor.execute("""
        INSERT INTO favorites (user_id, name, fg_color, bg_color, box_size, border_size, error_level)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        current_user_id,
        favorite_name,
        fg_color_var.get(),
        bg_color_var.get(),
        box_size_var.get(),
        border_size_var.get(),
        error_correction_var.get(),
        
    ))
    conn.commit()
    
    messagebox.showinfo("Favorite Saved", f"Saved '{favorite_name}' to your favorites")
    
    # Refresh favorites menu
    load_favorites_menu()

# Function to load favorites to the menu
def load_favorites_menu():
    if not current_user_id:
        return
        
    # Clear existing menu items
    favorites_menu.delete(0, tk.END)
    
    # Add menu header
    favorites_menu.add_command(label="Load Favorite Style", state="disabled")
    favorites_menu.add_separator()
    
    # Get favorites from database
    cursor.execute("SELECT id, name FROM favorites WHERE user_id = ? ORDER BY name", (current_user_id,))
    favorites = cursor.fetchall()
    
    if not favorites:
        favorites_menu.add_command(label="No favorites saved", state="disabled")
    else:
        # Add each favorite to the menu
        for fav_id, name in favorites:
            favorites_menu.add_command(
                label=name,
                command=lambda fid=fav_id: load_favorite(fid)
            )
    
    favorites_menu.add_separator()
    favorites_menu.add_command(label="Save Current Style", command=save_favorite)

# Function to load a favorite style
def load_favorite(favorite_id):
    cursor.execute("""
        SELECT fg_color, bg_color, box_size, border_size, error_level
        FROM favorites WHERE id = ?
    """, (favorite_id,))
    
    result = cursor.fetchone()
    if result:
        fg_color, bg_color, box_size, border_size, error_level= result
        
        # Apply settings
        fg_color_var.set(fg_color)
        bg_color_var.set(bg_color)
        box_size_var.set(box_size)
        border_size_var.set(border_size)
        error_correction_var.set(error_level)
    
        
        messagebox.showinfo("Favorite Loaded", "Favorite style loaded successfully")

# Function to show analytics
def show_analytics():
    if not current_user_id:
        messagebox.showwarning("Login Required", "Please log in to view analytics")
        return
        
    # Create a new window for analytics
    analytics_window = tk.Toplevel(root)
    analytics_window.title("QR Code Analytics")
    analytics_window.geometry("500x400")
    analytics_window.config(bg=bg_color)
    
    # Get analytics data from database
    cursor.execute("""
        SELECT qr_type, COUNT(*) as count
        FROM analytics
        WHERE user_id = ?
        GROUP BY qr_type
        ORDER BY count DESC
    """, (current_user_id,))
    
    type_data = cursor.fetchall()
    
    # Get date-based analytics
    cursor.execute("""
        SELECT strftime('%Y-%m-%d', created_at) as date, COUNT(*) as count
        FROM analytics
        WHERE user_id = ?
        GROUP BY date
        ORDER BY date DESC
        LIMIT 7
    """, (current_user_id,))
    
    date_data = cursor.fetchall()
    
    # Create tabs for different analytics views
    analytics_tabs = ttk.Notebook(analytics_window)
    analytics_tabs.pack(fill="both", expand=True, padx=10, pady=10)
    
    # Tab for QR code types
    types_tab = tk.Frame(analytics_tabs, bg=bg_color)
    analytics_tabs.add(types_tab, text="QR Types")
    
    # Tab for date-based usage
    dates_tab = tk.Frame(analytics_tabs, bg=bg_color)
    analytics_tabs.add(dates_tab, text="Usage by Date")
    
    # Create visualization for QR types
    tk.Label(types_tab, text="Your Most Generated QR Code Types", 
            font=("Arial", 12, "bold"), bg=bg_color, fg=fg_color).pack(pady=10)
    
    # Simple bar chart visualization
    canvas_width = 400
    canvas_height = 250
    canvas = tk.Canvas(types_tab, width=canvas_width, height=canvas_height, bg=entry_bg_color)
    canvas.pack(pady=10)
    
    if not type_data:
        canvas.create_text(canvas_width/2, canvas_height/2, 
                         text="No analytics data available yet",
                         fill=fg_color, font=("Arial", 12))
    else:
        # Determine the maximum count for scaling
        max_count = max([count for _, count in type_data])
        
        # Draw bars
        bar_width = canvas_width / (len(type_data) + 1)
        for i, (qr_type, count) in enumerate(type_data):
            # Calculate bar height based on count
            bar_height = (count / max_count) * (canvas_height - 50)
            
            # Define bar position
            x1 = 20 + i * bar_width + 10
            y1 = canvas_height - 30 - bar_height
            x2 = x1 + bar_width - 10
            y2 = canvas_height - 30
            
            # Draw bar
            canvas.create_rectangle(x1, y1, x2, y2, fill=accent_color)
            
            # Add label
            canvas.create_text(x1 + bar_width/2, canvas_height - 15, 
                             text=qr_type.capitalize(), fill=fg_color)
            
            # Add count at top of bar
            canvas.create_text(x1 + bar_width/2, y1 - 10, 
                             text=str(count), fill=fg_color)
    
    # Create visualization for dates
    tk.Label(dates_tab, text="Your QR Code Generation Activity", 
            font=("Arial", 12, "bold"), bg=bg_color, fg=fg_color).pack(pady=10)
    
    # Simple line chart for dates
    canvas = tk.Canvas(dates_tab, width=canvas_width, height=canvas_height, bg=entry_bg_color)
    canvas.pack(pady=10)
    
    if not date_data:
        canvas.create_text(canvas_width/2, canvas_height/2, 
                         text="No analytics data available yet",
                         fill=fg_color, font=("Arial", 12))
    else:
        # Reverse the data to show chronological order
        date_data = list(reversed(date_data))
        
        # Determine the maximum count for scaling
        max_count = max([count for _, count in date_data])
        
        # Draw lines
        segment_width = canvas_width / (len(date_data) + 1)
        points = []
        
        for i, (date, count) in enumerate(date_data):
            # Calculate point position
            x = 40 + i * segment_width
            y = canvas_height - 40 - ((count / max_count) * (canvas_height - 60))
            
            points.append((x, y))
            
            # Draw point
            canvas.create_oval(x-4, y-4, x+4, y+4, fill=accent_color)
            
            # Add date label
            canvas.create_text(x, canvas_height - 20, 
                             text=date.split('-')[2], fill=fg_color, 
                             angle=45, anchor="e")
            
            # Add count label
            canvas.create_text(x, y - 15, text=str(count), fill=fg_color)
        
        # Draw lines connecting points
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            canvas.create_line(x1, y1, x2, y2, fill=accent_color, width=2)

# Function to record analytics
def record_analytics(qr_type):
    if current_user_id:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO analytics (user_id, qr_type, created_at) VALUES (?, ?, ?)",
                     (current_user_id, qr_type, current_time))
        conn.commit()

# Function to check QR code data capacity
def check_capacity(data):
    # Calculate approximate capacity
    data_length = len(data)
    
    # QR code version capacities (approximate char counts for alphanumeric data with M error correction)
    capacities = {
        1: 25,     # Version 1
        2: 47,     # Version 2
        5: 255,    # Version 5
        10: 859,   # Version 10
        20: 2800,  # Version 20
        25: 4350,  # Version 25
        40: 7089   # Version 40 (max)
    }
    
    # Determine estimated version
    estimated_version = 1
    for version, capacity in sorted(capacities.items()):
        if data_length <= capacity:
            estimated_version = version
            break
    
    # Calculate percentage of capacity used
    version_capacity = next((cap for ver, cap in sorted(capacities.items()) if ver >= estimated_version), 7089)
    capacity_percent = min(100, (data_length / version_capacity) * 100)
    
    return {
        "length": data_length,
        "version": estimated_version,
        "capacity_percent": capacity_percent
    }


    
    # Create a new window for QR scanner
    scanner_window = tk.Toplevel(root)
    scanner_window.title("QR Code Scanner")
    scanner_window.geometry("640x520")
    scanner_window.config(bg=bg_color)
    
    # Frame for video
    video_frame = tk.Label(scanner_window)
    video_frame.pack(pady=10)
    
    # Result display
    result_frame = tk.Frame(scanner_window, bg=bg_color)
    result_frame.pack(fill="x", padx=20, pady=10)
    
    tk.Label(result_frame, text="Decoded Data:", bg=bg_color, fg=fg_color,
            font=("Arial", 11, "bold")).pack(anchor="w")
    
    result_text = tk.Text(result_frame, height=5, width=60, bg=entry_bg_color, fg=entry_fg_color)
    result_text.pack(fill="x", pady=5)
    
    # Buttons
    button_frame = tk.Frame(scanner_window, bg=bg_color)
    button_frame.pack(pady=10)
    
    # Function to handle video streaming
    def video_stream():
        nonlocal cap
        if cap is not None:
            ret, frame = cap.read()
            if ret:
                # Process frame for QR codes
                decoded_objects = decode(frame)
                
                # Draw bounding box around QR codes
                for obj in decoded_objects:
                    # Get the QR code's position
                    points = obj.polygon
                    if len(points) > 4:
                        hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
                        cv2.polylines(frame, [hull], True, (0, 255, 0), 2)
                    else:
                        # Draw the polygon around the QR code
                        pts = np.array([points], np.int32)
                        pts = pts.reshape((-1, 1, 2))
                        cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
                    
                    # Get the data
                    qr_data = obj.data.decode('utf-8')
                    
                    # Display data
                    result_text.delete(1.0, tk.END)
                    result_text.insert(tk.END, qr_data)
                
                # Convert frame to display in tkinter
                cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGBA)
                img = Image.fromarray(cv2image)
                imgtk = ImageTk.PhotoImage(image=img)
                video_frame.imgtk = imgtk
                video_frame.config(image=imgtk)
            
            # Call this function again after 10ms
            video_frame.after(10, video_stream)
    
    # Function to copy decoded data to clipboard
    def copy_to_clipboard():
        decoded_data = result_text.get(1.0, tk.END).strip()
        if decoded_data:
            root.clipboard_clear()
            root.clipboard_append(decoded_data)
            messagebox.showinfo("Copied", "Data copied to clipboard")
    
    # Button to copy data
    copy_button = tk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard,
                          bg=button_bg_color, fg=button_fg_color)
    copy_button.pack(side="left", padx=5)
    
    # Button to close scanner
    close_button = tk.Button(button_frame, text="Close Scanner", 
                           command=lambda: [cap.release(), scanner_window.destroy()],
                           bg=button_bg_color, fg=button_fg_color)
    close_button.pack(side="left", padx=5)
    
    # Initialize webcam
    cap = None
    try:
        cap = cv2.VideoCapture(0)
        video_stream()
    except Exception as e:
        messagebox.showerror("Camera Error", f"Could not access webcam: {str(e)}")
        scanner_window.destroy()
        return
    
    # Handle window closing
    scanner_window.protocol("WM_DELETE_WINDOW", lambda: [cap.release(), scanner_window.destroy()])

# Function to generate QR Code
def generate_qr(event_type='text'):
    global generated_img, qr_data
    
    # Get customization options
    foreground_color = foreground_colors[fg_color_var.get()]
    background_color = background_colors[bg_color_var.get()]
    box_size = int(box_size_var.get())
    border_size = int(border_size_var.get())
    error_correction = error_correction_var.get()
    
    # Convert error correction string to qrcode constant
    if error_correction == "L (7%)":
        error_level = qrcode.constants.ERROR_CORRECT_L
    elif error_correction == "M (15%)":
        error_level = qrcode.constants.ERROR_CORRECT_M
    elif error_correction == "Q (25%)":
        error_level = qrcode.constants.ERROR_CORRECT_Q
    else:  # H (30%)
        error_level = qrcode.constants.ERROR_CORRECT_H
    
    # Get content based on QR type
    if event_type == 'text':
        input_text = text_entry.get()
    elif event_type == 'url':
        input_text = url_entry.get()
        # Prepend http:// if no protocol is specified
        if input_text and not input_text.startswith(('http://', 'https://')):
            input_text = 'https://' + input_text
    elif event_type == 'event':
        event_date = event_date_entry.get()
        event_time = event_time_entry.get()
        event_details = event_details_entry.get()
        event_location = event_location_entry.get()
        input_text = f"BEGIN:VEVENT\nSUMMARY:{event_details}\nLOCATION:{event_location}\nDTSTART:{event_date.replace('-', '')}T{event_time.replace(':', '')}00\nEND:VEVENT"
    elif event_type == 'contact':
        name = contact_name_entry.get()
        phone = contact_phone_entry.get()
        email = contact_email_entry.get()
        input_text = f"BEGIN:VCARD\nVERSION:3.0\nN:{name}\nTEL:{phone}\nEMAIL:{email}\nEND:VCARD"
    elif event_type == 'wifi':
        ssid = wifi_ssid_entry.get()
        password = wifi_password_entry.get()
        security = wifi_security_var.get()
        input_text = f"WIFI:S:{ssid};T:{security};P:{password};;"

    if not input_text:
        messagebox.showwarning("Input Error", "Please enter all required information to generate a QR code.")
        return
    
    # Save the QR data for potential sharing
    qr_data = input_text
    
    # Record analytics
    record_analytics(event_type)
    
    # Create QR code with specified parameters
    qr = qrcode.QRCode(
        version=1,
        error_correction=error_level,
        box_size=box_size,
        border=border_size
    )
    qr.add_data(input_text)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color=foreground_color, back_color=background_color)
    
    # Check data capacity
    capacity_info = check_capacity(input_text)
    capacity_text = f"Data: {capacity_info['length']} chars - QR Version ~{capacity_info['version']} - Usage: {capacity_info['capacity_percent']:.1f}%"
    capacity_info_label.config(text=capacity_text)
    
    # Add logo if option is selected
    if add_logo_var.get() and logo_path:
        try:
            logo = Image.open(logo_path)
            # Calculate logo size (max 30% of QR code)
            logo_size = int(img.size[0] * 0.3)
            logo = logo.resize((logo_size, logo_size))
            
            # Calculate position (center)
            pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
            
            
            # Paste the logo onto the QR code
            img.paste(logo, pos, logo)
        except Exception as e:
            messagebox.showerror("Logo Error", f"Error adding logo: {str(e)}")
    
    
    # Convert image to display in Tkinter
    img_byte_array = io.BytesIO()
    img.save(img_byte_array, format="PNG")
    img_byte_array = img_byte_array.getvalue()

    img_tk = ImageTk.PhotoImage(Image.open(io.BytesIO(img_byte_array)))

    qr_label.config(image=img_tk)
    qr_label.image = img_tk

    generated_img = img  # Save for later download
    
    # Show share button as we have a valid QR code
    share_button.config(state="normal")
    
    # Save to history if user is logged in
    if current_user_id:
        save_to_history(event_type, input_text)


# Function to save QR generation to history
def save_to_history(qr_type, content):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO qr_history (user_id, qr_type, content, created_at) VALUES (?, ?, ?, ?)",
                  (current_user_id, qr_type, content, current_time))
    conn.commit()


# Function to load history
def load_history():
    if not current_user_id:
        return []
    
    cursor.execute("SELECT id, qr_type, content, created_at FROM qr_history WHERE user_id = ? ORDER BY created_at DESC",
                  (current_user_id,))
    return cursor.fetchall()


# Function to share QR code
def share_qr_code():
    if not generated_img or not qr_data:
        messagebox.showwarning("Share Error", "No QR code generated to share.")
        return
    
    # Create a new window for sharing options
    share_window = tk.Toplevel(root)
    share_window.title("Share QR Code")
    share_window.geometry("400x300")
    share_window.config(bg=bg_color)
    
    # Frame for sharing options
    options_frame = tk.Frame(share_window, bg=bg_color)
    options_frame.pack(pady=10, fill="x", padx=20)
    
    tk.Label(options_frame, text="Share Options", font=("Arial", 14, "bold"),
            bg=bg_color, fg=fg_color).pack(pady=5)
    
    # Function to copy data to clipboard
    def copy_data():
        root.clipboard_clear()
        root.clipboard_append(qr_data)
        messagebox.showinfo("Copied", "QR code data copied to clipboard")
    
    # Function to create a data URL for the QR code
    def get_data_url():
        img_byte_array = io.BytesIO()
        generated_img.save(img_byte_array, format="PNG")
        img_base64 = base64.b64encode(img_byte_array.getvalue()).decode()
        return f"data:image/png;base64,{img_base64}"
    
    # Function to save as QR code as HTML
    def save_as_html():
        file_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")]
        )
        
        if file_path:
            data_url = get_data_url()
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>QR Code</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; margin: 50px; }}
        .qr-container {{ max-width: 500px; margin: 0 auto; padding: 20px; 
                        border: 1px solid #ccc; border-radius: 10px; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <div class="qr-container">
        <h2>Your QR Code</h2>
        <img src="{data_url}" alt="QR Code">
        <p>Scan with a QR code reader app</p>
    </div>
</body>
</html>"""
            
            with open(file_path, 'w') as f:
                f.write(html_content)
            
            messagebox.showinfo("Saved", f"HTML file saved as {file_path}")
    
    # Create buttons for different sharing options
    options = [
        ("Copy Data to Clipboard", copy_data),
        ("Save as HTML", save_as_html),
    ]
    
    # Add URL opening option if the QR code contains a URL
    if qr_data.startswith(('http://', 'https://')):
        # Function to open the URL in a browser
        def open_url():
            webbrowser.open(qr_data)
        
        options.append(("Open URL in Browser", open_url))
    
    # Create buttons for each option
    for label, command in options:
        button = tk.Button(options_frame, text=label, command=command,
                         bg=button_bg_color, fg=button_fg_color,
                         width=20, height=2)
        button.pack(pady=5)
    
    # Close button
    tk.Button(options_frame, text="Close", command=share_window.destroy,
             bg=button_bg_color, fg=button_fg_color,
             width=20, height=1).pack(pady=10)


# Function to display history
def show_history():
    history_items = load_history()
    
    # Create a new window for history
    history_window = tk.Toplevel(root)
    history_window.title("QR Code History")
    history_window.geometry("600x400")
    history_window.config(bg=bg_color)
    
    if not history_items:
        tk.Label(history_window, text="No history found", bg=bg_color, fg=fg_color).pack(pady=20)
        return
    
    # Create a frame with scrollbar
    frame = tk.Frame(history_window, bg=bg_color)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    scrollbar = tk.Scrollbar(frame)
    scrollbar.pack(side="right", fill="y")
    
    # Create a listbox with scrollbar
    history_list = tk.Listbox(frame, width=80, height=15, yscrollcommand=scrollbar.set, 
                              bg=entry_bg_color, fg=fg_color, selectbackground=accent_color)
    history_list.pack(side="left", fill="both", expand=True)
    scrollbar.config(command=history_list.yview)
    
    # Populate the listbox
    for item in history_items:
        item_id, qr_type, content, created_at = item
        display_text = f"{created_at} - {qr_type.upper()}: {content[:40]}..."
        history_list.insert(tk.END, display_text)
        
    # Function to regenerate selected QR code
    def regenerate_selected():
        selected_indices = history_list.curselection()
        if not selected_indices:
            messagebox.showinfo("Selection", "Please select a QR code from history")
            return
            
        selected_index = selected_indices[0]
        item_id = history_items[selected_index][0]
        
        # Get full details
        cursor.execute("SELECT qr_type, content FROM qr_history WHERE id = ?", (item_id,))
        qr_type, content = cursor.fetchone()
        
        # Set appropriate tab and populate fields
        if qr_type == 'text':
            qr_tabs.select(1)  # Text tab
            text_entry.delete(0, tk.END)
            text_entry.insert(0, content)
        elif qr_type == 'url':
            qr_tabs.select(0)  # URL tab
            url_entry.delete(0, tk.END)
            url_entry.insert(0, content)
        elif qr_type == 'event':
            qr_tabs.select(2)  # Event tab
            # Parse event content and populate fields (simplified)
            event_date_entry.delete(0, tk.END)
            event_time_entry.delete(0, tk.END)
            event_details_entry.delete(0, tk.END)
            event_location_entry.delete(0, tk.END)
            
            # Simple parsing, could be more robust
            if "DTSTART:" in content:
                date_time = content.split("DTSTART:")[1].split("T")
                if len(date_time) > 1:
                    date = date_time[0]
                    time = date_time[1][:4]
                    event_date_entry.insert(0, f"{date[:4]}-{date[4:6]}-{date[6:8]}")
                    event_time_entry.insert(0, f"{time[:2]}:{time[2:4]}")
            
            if "SUMMARY:" in content:
                details = content.split("SUMMARY:")[1].split("\n")[0]
                event_details_entry.insert(0, details)
                
            if "LOCATION:" in content:
                location = content.split("LOCATION:")[1].split("\n")[0]
                event_location_entry.insert(0, location)
                
        elif qr_type == 'contact':
            qr_tabs.select(3)  # Contact tab
            contact_name_entry.delete(0, tk.END)
            contact_phone_entry.delete(0, tk.END)
            contact_email_entry.delete(0, tk.END)
            
            if "N:" in content:
                name = content.split("N:")[1].split("\n")[0]
                contact_name_entry.insert(0, name)
            
            if "TEL:" in content:
                phone = content.split("TEL:")[1].split("\n")[0]
                contact_phone_entry.insert(0, phone)
                
            if "EMAIL:" in content:
                email = content.split("EMAIL:")[1].split("\n")[0]
                contact_email_entry.insert(0, email)
                
        elif qr_type == 'wifi':
            qr_tabs.select(4)  # WiFi tab
            wifi_ssid_entry.delete(0, tk.END)
            wifi_password_entry.delete(0, tk.END)
            
            if "S:" in content and ";" in content:
                ssid = content.split("S:")[1].split(";")[0]
                wifi_ssid_entry.insert(0, ssid)
            
            if "P:" in content and ";" in content:
                password = content.split("P:")[1].split(";")[0]
                wifi_password_entry.insert(0, password)
                
            if "T:" in content and ";" in content:
                security = content.split("T:")[1].split(";")[0]
                wifi_security_var.set(security)
        
        # Generate the QR code
        generate_qr(qr_type)
        history_window.destroy()
    
    # Function to delete selected history item
    def delete_selected():
        selected_indices = history_list.curselection()
        if not selected_indices:
            messagebox.showinfo("Selection", "Please select a QR code from history")
            return
            
        selected_index = selected_indices[0]
        item_id = history_items[selected_index][0]
        
        # Confirm deletion
        if messagebox.askyesno("Confirm Deletion", "Are you sure you want to delete this history item?"):
            # Delete from database
            cursor.execute("DELETE FROM qr_history WHERE id = ?", (item_id,))
            conn.commit()
            
            # Remove from listbox
            history_list.delete(selected_index)
            
            # Update history_items list
            history_items.pop(selected_index)
            
            messagebox.showinfo("Deleted", "History item deleted successfully")
    
    # Add buttons
    button_frame = tk.Frame(history_window, bg=bg_color)
    button_frame.pack(pady=10)
    
    tk.Button(button_frame, text="Regenerate Selected", command=regenerate_selected,
             bg=button_bg_color, fg=button_fg_color, activebackground=button_active_bg,
             activeforeground=button_active_fg).pack(side="left", padx=5)
    
    tk.Button(button_frame, text="Delete Selected", command=delete_selected,
             bg=button_bg_color, fg=button_fg_color, activebackground=button_active_bg,
             activeforeground=button_active_fg).pack(side="left", padx=5)
    
    tk.Button(button_frame, text="Close", command=history_window.destroy,
             bg=button_bg_color, fg=button_fg_color, activebackground=button_active_bg,
             activeforeground=button_active_fg).pack(side="left", padx=5)


# Function to select a logo
def select_logo():
    global logo_path
    file_path = filedialog.askopenfilename(
        filetypes=[("Image Files", "*.png *.jpg *.jpeg *.gif *.bmp"), ("All Files", "*.*")]
    )
    if file_path:
        logo_path = file_path
        logo_label.config(text=f"Logo: {os.path.basename(file_path)}")


# Function to handle login
def login():
    global current_user_id, is_admin
    username = username_entry.get()
    password = password_entry.get()

    cursor.execute("SELECT id, is_admin FROM users WHERE username = ? AND password = ?", (username, password))
    user = cursor.fetchone()

    if user:
        current_user_id = user[0]
        is_admin = bool(user[1])  # Convert to boolean
        login_frame.pack_forget()  # Hide login page
        main_canvas.pack(fill="both", expand=True)  # Show QR generator in scrollable canvas
        
        # Load favorites menu after login
        load_favorites_menu()
        
        # Update admin status indication
        if is_admin:
            header_label.config(text="QR CODE GENERATOR (ADMIN)")
        else:
            header_label.config(text="QR CODE GENERATOR")
    else:
        messagebox.showerror("Login Error", "Invalid username or password.")


# Function to handle user registration
def signup():
    username = signup_username_entry.get()
    password = signup_password_entry.get()
    confirm_password = signup_confirm_password_entry.get()

    if password != confirm_password:
        messagebox.showerror("Sign Up Error", "Passwords do not match!")
        return

    if username and password:
        try:
            cursor.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", 
                          (username, password, 0))  # Regular users are not admins
            conn.commit()
            messagebox.showinfo("Success", "Account created! Please log in.")
            signup_frame.pack_forget()
            login_frame.pack(pady=20)  # Show login page
        except sqlite3.IntegrityError:
            messagebox.showerror("Sign Up Error", "Username already exists!")
    else:
        messagebox.showerror("Sign Up Error", "Please fill in all fields.")


# Function to open the Sign-Up page
def open_signup():
    login_frame.pack_forget()
    signup_frame.pack(pady=20)


# Function to go back to Login page from Sign-Up
def back_to_login():
    signup_frame.pack_forget()
    login_frame.pack(pady=20)


# Function to save QR Code
def save_qr_code():
    global generated_img

    if generated_img is None:
        messagebox.showwarning("QR Code Error", "No QR code generated to save.")
        return
    
    # Get the selected format
    format_extension = qr_format.lower()
    
    file_path = filedialog.asksaveasfilename(
        defaultextension=f".{format_extension}",
        filetypes=[
            ("PNG Files", "*.png"), 
            ("JPEG Files", "*.jpg"), 
            ("PDF Files", "*.pdf"),
            ("All Files", "*.*")
        ]
    )

    if file_path:
        if format_extension == "pdf":
            # Create a PDF with the QR code
            try:
                # Import only when needed to avoid dependency issues
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.utils import ImageReader
                
                # Create temporary file for the image
                img_byte_array = io.BytesIO()
                generated_img.save(img_byte_array, format="PNG")
                img_byte_array.seek(0)
                
                # Create the PDF
                c = canvas.Canvas(file_path, pagesize=letter)
                width, height = letter
                
                # Add title
                c.setFont("Helvetica-Bold", 16)
                c.drawString(72, height - 72, "Your QR Code")
                
                # Add the QR code image
                qr_img = ImageReader(img_byte_array)
                img_width, img_height = generated_img.size
                
                # Scale to fit on page (max 80% of page width)
                scale_factor = min(1.0, (width * 0.8) / img_width)
                scaled_width = img_width * scale_factor
                scaled_height = img_height * scale_factor
                
                # Center on page
                x = (width - scaled_width) / 2
                y = height - 200 - scaled_height  # Leave space for title
                
                c.drawImage(qr_img, x, y, width=scaled_width, height=scaled_height)
                
                # Add footer with data
                c.setFont("Helvetica", 10)
                c.drawString(72, 72, f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
                
                c.save()
                messagebox.showinfo("Success", f"QR code saved as PDF: {file_path}")
            except ImportError:
                messagebox.showerror("Missing Dependency", 
                                  "PDF export requires ReportLab. Install with: pip install reportlab")
        else:
            # Regular image save
            generated_img.save(file_path, format=format_extension.upper())
            messagebox.showinfo("Success", f"QR code saved successfully as {file_path}")


# Function to toggle dark mode
def toggle_dark_mode():
    global is_dark_mode, bg_color, fg_color, button_bg_color, button_fg_color
    global entry_bg_color, entry_fg_color, button_active_bg, button_active_fg
    global accent_color, header_bg_color
    
    is_dark_mode = not is_dark_mode
    
    if is_dark_mode:
        bg_color = "#2E2E2E"
        fg_color = "#FFFFFF"
        button_bg_color = "#454545"
        button_fg_color = "#FFFFFF"
        entry_bg_color = "#3D3D3D"
        entry_fg_color = "#FFFFFF"
        button_active_bg = "#575757"
        button_active_fg = "#FFFFFF"
        accent_color = "#4a6984"
        header_bg_color = "#1E1E1E"
    else:
        bg_color = "#F0F0F0"
        fg_color = "#333333"
        button_bg_color = "#E0E0E0"
        button_fg_color = "#333333"
        entry_bg_color = "#FFFFFF"
        entry_fg_color = "#333333"
        button_active_bg = "#CCCCCC"
        button_active_fg = "#333333"
        accent_color = "#4a84b4"
        header_bg_color = "#DDDDDD"
    
    # Update the root window
    root.config(bg=bg_color)
    
    # Update header
    header_label.config(bg=header_bg_color, fg=fg_color)
    header_frame.config(bg=header_bg_color)
    
    # Update all frames
    for frame in [login_frame, signup_frame, qr_code_generator_frame]:
        frame.config(bg=bg_color)
    
    # Update all container frames within qr_code_generator_frame
    for widget in qr_code_generator_frame.winfo_children():
        if isinstance(widget, tk.Frame):
            widget.config(bg=bg_color)
            # Update children of this frame
            for child in widget.winfo_children():
                update_widget_colors(child)
    
    # Update tab frames
    for tab in [url_tab, text_tab, event_tab, contact_tab, wifi_tab]:
        tab.config(bg=bg_color)
        for child in tab.winfo_children():
            update_widget_colors(child)
    
    # Update customization frame and its children
    customization_frame.config(bg=bg_color, fg=fg_color)
    for child in customization_frame.winfo_children():
        update_widget_colors(child)
    
    # Update logo frame and options frame
    logo_frame.config(bg=bg_color)
    for child in logo_frame.winfo_children():
        update_widget_colors(child)
    
    # Update row frames and their children
    for row_frame in [row1_frame, row2_frame, row3_frame]:
        row_frame.config(bg=bg_color)
        for child in row_frame.winfo_children():
            update_widget_colors(child)
    
    # Update main canvas and scrollbar
    main_canvas.config(bg=bg_color)
    y_scrollbar.config(bg=button_bg_color)
    
    # Update the display frame
    qr_display_frame.config(bg=bg_color, fg=fg_color)
    qr_label.config(bg=bg_color)
    
    # Update capacity information label
    capacity_info_label.config(bg=bg_color, fg=fg_color)
    
    # Update content frame and its children
    content_frame.config(bg=bg_color)
    tabs_frame.config(bg=bg_color)
    display_frame.config(bg=bg_color)
    
    # Update utility bar
    util_frame.config(bg=header_bg_color)
    for child in util_frame.winfo_children():
        if isinstance(child, tk.Button):
            child.config(bg=button_bg_color, fg=button_fg_color,
                        activebackground=button_active_bg, activeforeground=button_active_fg)
            
    # Update login frame
    for child in login_frame.winfo_children():
        update_widget_colors(child)
        
    # Update signup frame
    for child in signup_frame.winfo_children():
        update_widget_colors(child)
    
    # Update background pattern
    create_pattern_background(main_canvas, root.winfo_width(), qr_code_generator_frame.winfo_height(), "dots")


# Helper function to update widget colors
def update_widget_colors(widget):
    if isinstance(widget, tk.Label):
        widget.config(bg=bg_color, fg=fg_color)
    elif isinstance(widget, tk.Button):
        widget.config(bg=button_bg_color, fg=button_fg_color, 
                     activebackground=button_active_bg, activeforeground=button_active_fg)
    elif isinstance(widget, tk.Entry):
        widget.config(bg=entry_bg_color, fg=entry_fg_color, insertbackground=fg_color)
    elif isinstance(widget, tk.Frame):
        widget.config(bg=bg_color)
        for child in widget.winfo_children():
            update_widget_colors(child)
    elif isinstance(widget, tk.Checkbutton) or isinstance(widget, tk.Radiobutton):
        widget.config(bg=bg_color, fg=fg_color, selectcolor=entry_bg_color,
                     activebackground=bg_color, activeforeground=fg_color)
    elif isinstance(widget, tk.LabelFrame):
        widget.config(bg=bg_color, fg=fg_color)
        for child in widget.winfo_children():
            update_widget_colors(child)
    elif isinstance(widget, tk.Text):
        widget.config(bg=entry_bg_color, fg=entry_fg_color, insertbackground=fg_color)
    elif isinstance(widget, tk.Canvas):
        widget.config(bg=entry_bg_color)
    elif isinstance(widget, tk.Menu):
        # Menu items are more complex, handled separately
        pass


# Set initial colors
bg_color = "#F0F0F0"  # Light gray for light mode
fg_color = "#333333"  # Dark gray text for light mode
button_bg_color = "#E0E0E0"
button_fg_color = "#333333"
entry_bg_color = "#FFFFFF"
entry_fg_color = "#333333"
button_active_bg = "#CCCCCC"
button_active_fg = "#333333"
accent_color = "#4a84b4"
header_bg_color = "#DDDDDD"


# Function to create decorative background pattern
def create_pattern_background(canvas, width, height, pattern_type="dots"):
    canvas.delete("pattern")  # Clear previous pattern
    
    if pattern_type == "dots":
        # Create a dotted pattern
        dot_spacing = 20
        dot_radius = 2
        for x in range(0, width, dot_spacing):
            for y in range(0, height, dot_spacing):
                # Add some randomness to the pattern
                offset_x = random.randint(-3, 3)
                offset_y = random.randint(-3, 3)
                
                # Create small dots with color based on current mode
                dot_color = "#D0D0D0" if not is_dark_mode else "#3A3A3A"
                canvas.create_oval(
                    x + offset_x - dot_radius, 
                    y + offset_y - dot_radius,
                    x + offset_x + dot_radius, 
                    y + offset_y + dot_radius,
                    fill=dot_color, outline="", tags="pattern"
                )
    elif pattern_type == "grid":
        # Create a subtle grid pattern
        grid_spacing = 30
        line_color = "#D0D0D0" if not is_dark_mode else "#3A3A3A"
        
        # Horizontal lines
        for y in range(0, height, grid_spacing):
            canvas.create_line(0, y, width, y, fill=line_color, width=1, tags="pattern")
        
        # Vertical lines
        for x in range(0, width, grid_spacing):
            canvas.create_line(x, 0, x, height, fill=line_color, width=1, tags="pattern")


# Create the main window
root = tk.Tk()
root.title("QR Code Generator")
root.geometry("700x600")
root.config(bg=bg_color)

# Create menu bar
menubar = tk.Menu(root)
root.config(menu=menubar)

# File menu
file_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=file_menu)
file_menu.add_command(label="Load History", command=show_history)
file_menu.add_command(label="Export Settings", command=lambda: messagebox.showinfo("Info", "Feature coming soon"))

# Format submenu for export options
format_menu = tk.Menu(file_menu, tearoff=0)
file_menu.add_cascade(label="Export Format", menu=format_menu)

# Define format variable and options
format_var = tk.StringVar(value="PNG")
format_menu.add_radiobutton(label="PNG", variable=format_var, value="PNG", 
                           command=lambda: setattr(globals(), 'qr_format', "PNG"))
format_menu.add_radiobutton(label="JPEG", variable=format_var, value="JPEG", 
                           command=lambda: setattr(globals(), 'qr_format', "JPEG"))
format_menu.add_radiobutton(label="PDF", variable=format_var, value="PDF", 
                           command=lambda: setattr(globals(), 'qr_format', "PDF"))

file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Tools menu
tools_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Tools", menu=tools_menu)
tools_menu.add_command(label="Analytics", command=show_analytics)
tools_menu.add_command(label="Database Viewer", command=view_database)  # Everyone sees the option
tools_menu.add_command(label="Export Database", command=export_database)  # Everyone sees the option

# Templates menu
templates_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Templates", menu=templates_menu)

# Add template options
for template_name in qr_templates:
    templates_menu.add_command(label=template_name, 
                             command=lambda t=template_name: [template_var.set(t), apply_template()])

# Favorites menu
favorites_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Favorites", menu=favorites_menu)
favorites_menu.add_command(label="No favorites saved", state="disabled")
favorites_menu.add_separator()
favorites_menu.add_command(label="Save Current Style", command=save_favorite)

# Help menu
help_menu = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(label="Tips", command=lambda: messagebox.showinfo("QR Code Tips", 
                                                                    "• Use higher ECC levels for better error correction\n"
                                                                    "• Add a logo to make your QR code recognizable\n"
                                                                    "• Keep URLs short for simpler QR codes\n"
                                                                    "• Test your QR code on different devices"))
help_menu.add_command(label="About", command=lambda: messagebox.showinfo("About", 
                                                                      "QR Code Generator\nVersion 2.0\n\n"
                                                                      "A full-featured QR code generation tool"))

# Header Label with accent background
header_frame = tk.Frame(root, bg=header_bg_color, height=60)
header_frame.pack(fill="x")

header_label = tk.Label(header_frame, text="QR CODE GENERATOR", font=("Arial", 18, "bold"), 
                        bg=header_bg_color, fg=fg_color, pady=10)
header_label.pack()

# ---------------- Login Frame ----------------
login_frame = tk.Frame(root, bg=bg_color)
login_frame.pack(pady=10)

# Create a frame for login controls with some styling
login_box = tk.Frame(login_frame, bg=bg_color, bd=2, relief="groove", padx=20, pady=15)
login_box.pack(pady=30)

tk.Label(login_box, text="Welcome to QR Code Generator", font=("Arial", 12, "bold"), 
        bg=bg_color, fg=fg_color).pack(pady=(0, 15))

tk.Label(login_box, text="Username:", bg=bg_color, fg=fg_color).pack(anchor="w")
username_entry = tk.Entry(login_box, width=25, bg=entry_bg_color, fg=entry_fg_color)
username_entry.pack(fill="x", pady=(0, 10))

tk.Label(login_box, text="Password:", bg=bg_color, fg=fg_color).pack(anchor="w")
password_entry = tk.Entry(login_box, width=25, show="*", bg=entry_bg_color, fg=entry_fg_color)
password_entry.pack(fill="x", pady=(0, 15))

login_button = tk.Button(login_box, text="Login", command=login, 
                        bg=button_bg_color, fg=button_fg_color,
                        activebackground=button_active_bg, activeforeground=button_active_fg,
                        width=10, height=1, bd=1)
login_button.pack(pady=(0, 5))

signup_button = tk.Button(login_box, text="Sign Up", command=open_signup,
                        bg=button_bg_color, fg=button_fg_color,
                        activebackground=button_active_bg, activeforeground=button_active_fg,
                        width=10, height=1, bd=1)
signup_button.pack()

# Add admin login hint 
admin_hint = tk.Label(login_frame, text="Powered By RAN (C)", 
                       font=("Arial", 8), bg=bg_color, fg=fg_color)
admin_hint.pack(pady=(5, 0))

# ---------------- Sign-Up Frame ----------------
signup_frame = tk.Frame(root, bg=bg_color)

# Create a frame for signup controls with some styling
signup_box = tk.Frame(signup_frame, bg=bg_color, bd=2, relief="groove", padx=20, pady=15)
signup_box.pack(pady=30)

tk.Label(signup_box, text="Create a New Account", font=("Arial", 12, "bold"), 
        bg=bg_color, fg=fg_color).pack(pady=(0, 15))

tk.Label(signup_box, text="Username:", bg=bg_color, fg=fg_color).pack(anchor="w")
signup_username_entry = tk.Entry(signup_box, width=25, bg=entry_bg_color, fg=entry_fg_color)
signup_username_entry.pack(fill="x", pady=(0, 10))

tk.Label(signup_box, text="Password:", bg=bg_color, fg=fg_color).pack(anchor="w")
signup_password_entry = tk.Entry(signup_box, width=25, show="*", bg=entry_bg_color, fg=entry_fg_color)
signup_password_entry.pack(fill="x", pady=(0, 10))

tk.Label(signup_box, text="Confirm Password:", bg=bg_color, fg=fg_color).pack(anchor="w")
signup_confirm_password_entry = tk.Entry(signup_box, width=25, show="*", bg=entry_bg_color, fg=entry_fg_color)
signup_confirm_password_entry.pack(fill="x", pady=(0, 15))

signup_submit_button = tk.Button(signup_box, text="Sign Up", command=signup,
                                bg=button_bg_color, fg=button_fg_color,
                                activebackground=button_active_bg, activeforeground=button_active_fg,
                                width=10, height=1, bd=1)
signup_submit_button.pack(pady=(0, 5))

back_button = tk.Button(signup_box, text="Back to Login", command=back_to_login,
                        bg=button_bg_color, fg=button_fg_color,
                        activebackground=button_active_bg, activeforeground=button_active_fg,
                        width=10, height=1, bd=1)
back_button.pack()

# ---------------- Scrollable Canvas for QR Generator ----------------
main_canvas = tk.Canvas(root, bg=bg_color, highlightthickness=0)
y_scrollbar = tk.Scrollbar(root, orient="vertical", command=main_canvas.yview)
y_scrollbar.pack(side="right", fill="y")
main_canvas.configure(yscrollcommand=y_scrollbar.set)

# Create a frame inside the canvas for all QR generator content
qr_code_generator_frame = tk.Frame(main_canvas, bg=bg_color)
main_canvas.create_window((0, 0), window=qr_code_generator_frame, anchor="nw", tags="qr_generator")

# Top bar with utilities
util_frame = tk.Frame(qr_code_generator_frame, bg=header_bg_color, height=40)
util_frame.pack(fill="x")

history_button = tk.Button(util_frame, text="History", command=show_history,
                        bg=button_bg_color, fg=button_fg_color,
                        activebackground=button_active_bg, activeforeground=button_active_fg)
history_button.pack(side="left", padx=10, pady=5)

analytics_button = tk.Button(util_frame, text="Analytics", command=show_analytics,
                           bg=button_bg_color, fg=button_fg_color,
                           activebackground=button_active_bg, activeforeground=button_active_fg)
analytics_button.pack(side="left", padx=10, pady=5)

db_viewer_button = tk.Button(util_frame, text="Database", command=view_database,  # Everyone can see the button
                           bg=button_bg_color, fg=button_fg_color,
                           activebackground=button_active_bg, activeforeground=button_active_fg)
db_viewer_button.pack(side="left", padx=10, pady=5)

dark_mode_button = tk.Button(util_frame, text="Toggle Dark Mode", command=toggle_dark_mode,
                        bg=button_bg_color, fg=button_fg_color,
                        activebackground=button_active_bg, activeforeground=button_active_fg)
dark_mode_button.pack(side="right", padx=10, pady=5)

logout_button = tk.Button(util_frame, text="Log Out", 
                         command=lambda: [main_canvas.pack_forget(), login_frame.pack()],
                         bg=button_bg_color, fg=button_fg_color,
                         activebackground=button_active_bg, activeforeground=button_active_fg)
logout_button.pack(side="right", padx=10, pady=5)

# Create a custom style for the notebook tabs
style = ttk.Style()
style.configure('TNotebook', background=bg_color)
style.configure('TNotebook.Tab', background=button_bg_color, foreground=button_fg_color, padding=[10, 2])
style.map('TNotebook.Tab', background=[('selected', button_active_bg)], 
         foreground=[('selected', button_active_fg)])

# Container for tabs and QR display in a 2-column layout
content_frame = tk.Frame(qr_code_generator_frame, bg=bg_color)
content_frame.pack(fill="both", expand=True, padx=10, pady=5)

# Left column for tabs
tabs_frame = tk.Frame(content_frame, bg=bg_color)
tabs_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))

# QR Code Tabs - Using ttk Notebook but regular frames for the tabs
qr_tabs = ttk.Notebook(tabs_frame)
qr_tabs.pack(fill="both", expand=True)

# URL Tab
url_tab = tk.Frame(qr_tabs, bg=bg_color)
qr_tabs.add(url_tab, text="URL")

tk.Label(url_tab, text="Enter URL:", bg=bg_color, fg=fg_color).pack(pady=(10, 5), anchor="w")
url_entry = tk.Entry(url_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
url_entry.pack(fill="x", padx=10)
tk.Button(url_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='url'),
         bg=button_bg_color, fg=button_fg_color,
         activebackground=button_active_bg, activeforeground=button_active_fg).pack(pady=10)

# Text Tab
text_tab = tk.Frame(qr_tabs, bg=bg_color)
qr_tabs.add(text_tab, text="Text")

tk.Label(text_tab, text="Enter Text:", bg=bg_color, fg=fg_color).pack(pady=(10, 5), anchor="w")
text_entry = tk.Entry(text_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
text_entry.pack(fill="x", padx=10)
tk.Button(text_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='text'),
         bg=button_bg_color, fg=button_fg_color,
         activebackground=button_active_bg, activeforeground=button_active_fg).pack(pady=10)

# Event Tab
event_tab = tk.Frame(qr_tabs, bg=bg_color)
qr_tabs.add(event_tab, text="Event")

tk.Label(event_tab, text="Event Date (YYYY-MM-DD):", bg=bg_color, fg=fg_color).pack(pady=(10, 2), anchor="w")
event_date_entry = tk.Entry(event_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
event_date_entry.pack(fill="x", padx=10)

tk.Label(event_tab, text="Event Time (HH:MM):", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
event_time_entry = tk.Entry(event_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
event_time_entry.pack(fill="x", padx=10)

tk.Label(event_tab, text="Event Details:", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
event_details_entry = tk.Entry(event_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
event_details_entry.pack(fill="x", padx=10)

tk.Label(event_tab, text="Event Location:", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
event_location_entry = tk.Entry(event_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
event_location_entry.pack(fill="x", padx=10)

tk.Button(event_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='event'),
         bg=button_bg_color, fg=button_fg_color,
         activebackground=button_active_bg, activeforeground=button_active_fg).pack(pady=10)

# Contact Tab
contact_tab = tk.Frame(qr_tabs, bg=bg_color)
qr_tabs.add(contact_tab, text="Contact")

tk.Label(contact_tab, text="Name:", bg=bg_color, fg=fg_color).pack(pady=(10, 2), anchor="w")
contact_name_entry = tk.Entry(contact_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
contact_name_entry.pack(fill="x", padx=10)

tk.Label(contact_tab, text="Phone:", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
contact_phone_entry = tk.Entry(contact_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
contact_phone_entry.pack(fill="x", padx=10)

tk.Label(contact_tab, text="Email:", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
contact_email_entry = tk.Entry(contact_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
contact_email_entry.pack(fill="x", padx=10)

tk.Button(contact_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='contact'),
         bg=button_bg_color, fg=button_fg_color,
         activebackground=button_active_bg, activeforeground=button_active_fg).pack(pady=10)

# Wi-Fi Tab
wifi_tab = tk.Frame(qr_tabs, bg=bg_color)
qr_tabs.add(wifi_tab, text="Wi-Fi")

tk.Label(wifi_tab, text="SSID (Network Name):", bg=bg_color, fg=fg_color).pack(pady=(10, 2), anchor="w")
wifi_ssid_entry = tk.Entry(wifi_tab, width=40, bg=entry_bg_color, fg=entry_fg_color)
wifi_ssid_entry.pack(fill="x", padx=10)

tk.Label(wifi_tab, text="Password:", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
wifi_password_entry = tk.Entry(wifi_tab, width=40, show="*", bg=entry_bg_color, fg=entry_fg_color)
wifi_password_entry.pack(fill="x", padx=10)

tk.Label(wifi_tab, text="Security Type:", bg=bg_color, fg=fg_color).pack(pady=(5, 2), anchor="w")
wifi_security_var = tk.StringVar(value="WPA")
security_frame = tk.Frame(wifi_tab, bg=bg_color)
security_frame.pack(pady=5, anchor="w", padx=10)

tk.Radiobutton(security_frame, text="WPA/WPA2", variable=wifi_security_var, value="WPA",
              bg=bg_color, fg=fg_color, selectcolor=entry_bg_color,
              activebackground=bg_color, activeforeground=fg_color).pack(side="left", padx=5)
tk.Radiobutton(security_frame, text="WEP", variable=wifi_security_var, value="WEP",
              bg=bg_color, fg=fg_color, selectcolor=entry_bg_color,
              activebackground=bg_color, activeforeground=fg_color).pack(side="left", padx=5)
tk.Radiobutton(security_frame, text="None", variable=wifi_security_var, value="nopass",
              bg=bg_color, fg=fg_color, selectcolor=entry_bg_color,
              activebackground=bg_color, activeforeground=fg_color).pack(side="left", padx=5)

tk.Button(wifi_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='wifi'),
         bg=button_bg_color, fg=button_fg_color,
         activebackground=button_active_bg, activeforeground=button_active_fg).pack(pady=10)

# Right column for QR code display
display_frame = tk.Frame(content_frame, bg=bg_color)
display_frame.pack(side="right", fill="both", expand=True, padx=(5, 0))

# QR Code Display
qr_display_frame = tk.LabelFrame(display_frame, text="Generated QR Code", 
                                bg=bg_color, fg=fg_color)
qr_display_frame.pack(pady=5, fill="both", expand=True)

qr_label = tk.Label(qr_display_frame, bg=bg_color)
qr_label.pack(pady=5, padx=5)

# Capacity info label
capacity_info_label = tk.Label(qr_display_frame, text="Data: 0 chars - QR Version ~1 - Usage: 0.0%",
                              bg=bg_color, fg=fg_color, font=("Arial", 8))
capacity_info_label.pack(pady=(0, 5))

# Button frame for QR code actions
button_frame = tk.Frame(display_frame, bg=bg_color)
button_frame.pack(pady=5)

# Save button
save_button = tk.Button(button_frame, text="Save QR Code", command=save_qr_code,
                      bg=button_bg_color, fg=button_fg_color,
                      activebackground=button_active_bg, activeforeground=button_active_fg)
save_button.pack(side="left", padx=5)

# Share button (initially disabled)
share_button = tk.Button(button_frame, text="Share", command=share_qr_code,
                       bg=button_bg_color, fg=button_fg_color,
                       activebackground=button_active_bg, activeforeground=button_active_fg,
                       state="disabled")
share_button.pack(side="left", padx=5)


# Template selection frame
template_frame = tk.Frame(qr_code_generator_frame, bg=bg_color)
template_frame.pack(pady=2, fill="x", padx=10)

tk.Label(template_frame, text="Template:", bg=bg_color, fg=fg_color).pack(side="left", padx=2)
template_var = tk.StringVar(value="Standard")
template_menu = ttk.Combobox(template_frame, textvariable=template_var, 
                           values=list(qr_templates.keys()), width=15, state="readonly")
template_menu.pack(side="left", padx=2)

apply_button = tk.Button(template_frame, text="Apply", command=apply_template,
                       bg=button_bg_color, fg=button_fg_color,
                       activebackground=button_active_bg, activeforeground=button_active_fg,
                       padx=5, pady=0)
apply_button.pack(side="left", padx=5)

# Customization Frame at the bottom
customization_frame = tk.LabelFrame(qr_code_generator_frame, text="Customization Options", 
                                   bg=bg_color, fg=fg_color)
customization_frame.pack(pady=5, fill="x", padx=10)

# Create a more compact layout for customization options
options_frame = tk.Frame(customization_frame, bg=bg_color)
options_frame.pack(pady=5, padx=5, fill="x")

# Organize options in a more compact grid
row1_frame = tk.Frame(options_frame, bg=bg_color)
row1_frame.pack(fill="x", pady=2)
row1_frame = tk.Frame(options_frame, bg=bg_color)
row1_frame.pack(fill="x", pady=2)

tk.Label(row1_frame, text="FG Color:", bg=bg_color, fg=fg_color, width=10, anchor="e").pack(side="left", padx=2)
fg_color_var = tk.StringVar(value="Black")
fg_color_menu = ttk.Combobox(row1_frame, textvariable=fg_color_var, 
                           values=list(foreground_colors.keys()), width=12, state="readonly")
fg_color_menu.pack(side="left", padx=2)

tk.Label(row1_frame, text="BG Color:", bg=bg_color, fg=fg_color, width=10, anchor="e").pack(side="left", padx=2)
bg_color_var = tk.StringVar(value="White")
bg_color_menu = ttk.Combobox(row1_frame, textvariable=bg_color_var, 
                           values=list(background_colors.keys()), width=12, state="readonly")
bg_color_menu.pack(side="left", padx=2)

row2_frame = tk.Frame(options_frame, bg=bg_color)
row2_frame.pack(fill="x", pady=2)

tk.Label(row2_frame, text="Box Size:", bg=bg_color, fg=fg_color, width=10, anchor="e").pack(side="left", padx=2)
box_sizes = ["5", "6", "7", "8", "9", "10"]
box_size_var = tk.StringVar(value="5")
box_size_menu = ttk.Combobox(row2_frame, textvariable=box_size_var, values=box_sizes, width=12, state="readonly")
box_size_menu.pack(side="left", padx=2)

tk.Label(row2_frame, text="Border:", bg=bg_color, fg=fg_color, width=10, anchor="e").pack(side="left", padx=2)
border_sizes = ["2", "3", "4", "5", "6"]
border_size_var = tk.StringVar(value="2")
border_size_menu = ttk.Combobox(row2_frame, textvariable=border_size_var, values=border_sizes, width=12, state="readonly")
border_size_menu.pack(side="left", padx=2)

row3_frame = tk.Frame(options_frame, bg=bg_color)
row3_frame.pack(fill="x", pady=2)

tk.Label(row3_frame, text="ECC:", bg=bg_color, fg=fg_color, width=10, anchor="e").pack(side="left", padx=2)
error_levels = ["L (7%)", "M (15%)", "Q (25%)", "H (30%)"]
error_correction_var = tk.StringVar(value="M (15%)")
error_menu = ttk.Combobox(row3_frame, textvariable=error_correction_var, values=error_levels, width=12, state="readonly")
error_menu.pack(side="left", padx=2)

# Logo options in a more compact row
logo_frame = tk.Frame(customization_frame, bg=bg_color)
logo_frame.pack(pady=2, fill="x")

add_logo_var = tk.BooleanVar(value=False)
tk.Checkbutton(logo_frame, text="Add Logo", variable=add_logo_var, 
              bg=bg_color, fg=fg_color, selectcolor=entry_bg_color,
              activebackground=bg_color, activeforeground=fg_color).pack(side="left", padx=2)


select_logo_button = tk.Button(logo_frame, text="Select Logo", command=select_logo,
                              bg=button_bg_color, fg=button_fg_color,
                              activebackground=button_active_bg, activeforeground=button_active_fg,
                              padx=5, pady=0)
select_logo_button.pack(side="left", padx=2)

logo_label = tk.Label(logo_frame, text="No logo selected", bg=bg_color, fg=fg_color)
logo_label.pack(side="left", padx=2)

# Function to update canvas scroll region whenever the window size changes
def update_scroll_region(event=None):
    qr_code_generator_frame.update_idletasks()
    main_canvas.config(scrollregion=main_canvas.bbox("all"))
    
    # Also update background pattern if it exists
    if hasattr(root, 'winfo_width'):
        create_pattern_background(main_canvas, root.winfo_width(), qr_code_generator_frame.winfo_height(), "dots")

# Bind event to update scrollbar when window is resized
qr_code_generator_frame.bind("<Configure>", update_scroll_region)

# Add mouse wheel scrolling
def _on_mousewheel(event):
    main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

main_canvas.bind_all("<MouseWheel>", _on_mousewheel)

# Run Tkinter
root.protocol("WM_DELETE_WINDOW", lambda: [conn.close(), root.destroy()])  # Close DB connection on window close
root.mainloop()