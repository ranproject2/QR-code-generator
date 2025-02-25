import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import ttk
import qrcode
from PIL import Image, ImageTk
import io

# Dummy database to store user credentials
user_db = {"user123": "password123"}  # Existing user

# Global variable to store the generated QR code
generated_img = None

# Function to generate QR Code
def generate_qr(event_type='text'):
    global generated_img
    
    if event_type == 'text':
        input_text = text_entry.get()
    elif event_type == 'url':
        input_text = url_entry.get()
    elif event_type == 'event':
        event_date = event_date_entry.get()
        event_time = event_time_entry.get()
        event_details = event_details_entry.get()
        input_text = f"Event Date: {event_date}\nEvent Time: {event_time}\nDetails: {event_details}"

    if not input_text:
        messagebox.showwarning("Input Error", "Please enter some text to generate a QR code.")
        return

    qr = qrcode.QRCode(version=1, box_size=5, border=2)
    qr.add_data(input_text)
    qr.make(fit=True)

    img = qr.make_image(fill='black', back_color='white')

    # Convert image to display in Tkinter
    img_byte_array = io.BytesIO()
    img.save(img_byte_array)
    img_byte_array = img_byte_array.getvalue()

    img_tk = ImageTk.PhotoImage(Image.open(io.BytesIO(img_byte_array)))

    qr_label.config(image=img_tk)
    qr_label.image = img_tk

    generated_img = img  # Save for later download


# Function to handle login
def login():
    username = username_entry.get()
    password = password_entry.get()

    if username in user_db and user_db[username] == password:
        login_frame.pack_forget()  # Hide login page
        qr_code_generator_frame.pack(pady=10)  # Show QR generator
    else:
        messagebox.showerror("Login Error", "Invalid username or password.")


# Function to handle user registration
def signup():
    username = signup_username_entry.get()
    password = signup_password_entry.get()
    confirm_password = signup_confirm_password_entry.get()

    if username in user_db:
        messagebox.showerror("Sign Up Error", "Username already exists!")
        return

    if password != confirm_password:
        messagebox.showerror("Sign Up Error", "Passwords do not match!")
        return

    if username and password:
        user_db[username] = password
        messagebox.showinfo("Success", "Account created! Please log in.")
        signup_frame.pack_forget()
        login_frame.pack(pady=20)  # Show login page
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

    file_path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Files", "*.png"), ("JPEG Files", "*.jpg")])
    if file_path:
        generated_img.save(file_path)
        messagebox.showinfo("Success", f"QR code saved as {file_path}")


# Create the main window
root = tk.Tk()
root.title("QR Code Generator")

# Header Label
header_label = tk.Label(root, text="QR CODE GENERATOR", font=("Arial", 24, "bold"))
header_label.pack(pady=20)

# ---------------- Login Frame ----------------
login_frame = tk.Frame(root)
login_frame.pack(pady=20)

tk.Label(login_frame, text="Username:").grid(row=0, column=0, padx=10, pady=5)
username_entry = tk.Entry(login_frame, width=25)
username_entry.grid(row=0, column=1, padx=10, pady=5)

tk.Label(login_frame, text="Password:").grid(row=1, column=0, padx=10, pady=5)
password_entry = tk.Entry(login_frame, width=25, show="*")
password_entry.grid(row=1, column=1, padx=10, pady=5)

login_button = tk.Button(login_frame, text="Login", command=login)
login_button.grid(row=2, column=0, columnspan=2, pady=10)

signup_button = tk.Button(login_frame, text="Sign Up", command=open_signup)
signup_button.grid(row=3, column=0, columnspan=2, pady=5)

# ---------------- Sign-Up Frame ----------------
signup_frame = tk.Frame(root)

tk.Label(signup_frame, text="Create a New Account", font=("Arial", 14, "bold")).pack(pady=5)

tk.Label(signup_frame, text="Username:").pack()
signup_username_entry = tk.Entry(signup_frame, width=25)
signup_username_entry.pack(pady=5)

tk.Label(signup_frame, text="Password:").pack()
signup_password_entry = tk.Entry(signup_frame, width=25, show="*")
signup_password_entry.pack(pady=5)

tk.Label(signup_frame, text="Confirm Password:").pack()
signup_confirm_password_entry = tk.Entry(signup_frame, width=25, show="*")
signup_confirm_password_entry.pack(pady=5)

signup_submit_button = tk.Button(signup_frame, text="Sign Up", command=signup)
signup_submit_button.pack(pady=5)

back_button = tk.Button(signup_frame, text="Back to Login", command=back_to_login)
back_button.pack(pady=5)

# ---------------- QR Code Generator Frame ----------------
qr_code_generator_frame = tk.Frame(root)

qr_tabs = ttk.Notebook(qr_code_generator_frame)
qr_tabs.pack(pady=10)

# URL Tab
url_tab = tk.Frame(qr_tabs)
qr_tabs.add(url_tab, text="URL")

tk.Label(url_tab, text="Enter URL:").pack(pady=10)
url_entry = tk.Entry(url_tab, width=40)
url_entry.pack(pady=5)
tk.Button(url_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='url')).pack(pady=10)

# Text Tab
text_tab = tk.Frame(qr_tabs)
qr_tabs.add(text_tab, text="Text")

tk.Label(text_tab, text="Enter Text:").pack(pady=10)
text_entry = tk.Entry(text_tab, width=40)
text_entry.pack(pady=5)
tk.Button(text_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='text')).pack(pady=10)

# Event Tab
event_tab = tk.Frame(qr_tabs)
qr_tabs.add(event_tab, text="Event")

tk.Label(event_tab, text="Event Date (YYYY-MM-DD):").pack(pady=5)
event_date_entry = tk.Entry(event_tab, width=40)
event_date_entry.pack(pady=5)

tk.Label(event_tab, text="Event Time (HH:MM):").pack(pady=5)
event_time_entry = tk.Entry(event_tab, width=40)
event_time_entry.pack(pady=5)

tk.Label(event_tab, text="Event Details:").pack(pady=5)
event_details_entry = tk.Entry(event_tab, width=40)
event_details_entry.pack(pady=5)

tk.Button(event_tab, text="Generate QR Code", command=lambda: generate_qr(event_type='event')).pack(pady=10)

# QR Code Display
qr_label = tk.Label(qr_code_generator_frame)
qr_label.pack(pady=10)

# Function to save QR Code in PNG format
def save_qr_code():
    global generated_img

    if generated_img is None:
        messagebox.showwarning("QR Code Error", "No QR code generated to save.")
        return

    file_path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[("PNG Files", "*.png"), ("JPEG Files", "*.jpg"), ("All Files", "*.*")]
    )

    if file_path:
        generated_img.save(file_path, format="PNG")  # Saves as PNG
        messagebox.showinfo("Success", f"QR code saved successfully as {file_path}")

tk.Button(qr_code_generator_frame, text="Save QR Code", command=save_qr_code).pack(pady=10)


# Run Tkinter
root.mainloop()
