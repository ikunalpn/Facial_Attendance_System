import csv
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import mysql.connector
import cv2
import face_recognition
import os
import numpy as np
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

# Database connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="root",
    database="face"
)
cursor = db.cursor()

# Create the users and students tables if they don't exist
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(255) NOT NULL UNIQUE,
        password VARCHAR(255) NOT NULL
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        student_id VARCHAR(255) PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        image_data LONGBLOB
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INT AUTO_INCREMENT PRIMARY KEY,
        student_id VARCHAR(255),
        name VARCHAR(255),
        date DATE,
        time TIME
    )
""")

# Function to handle login
def login():
    username = username_entry.get()
    password = password_entry.get()

    if not username or not password:
        messagebox.showerror("Error", "Please enter both username and password.")
        return

    cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
    user = cursor.fetchone()

    if user:
        login_window.destroy()
        create_main_window()
    else:
        messagebox.showerror("Error", "Invalid username or password.")

# Function to create the login window
def create_login_window():
    global login_window
    login_window = tk.Tk()
    login_window.title("Login")

    username_label = ttk.Label(login_window, text="Username:")
    username_label.grid(row=0, column=0, padx=10, pady=10)

    global username_entry
    username_entry = ttk.Entry(login_window)
    username_entry.grid(row=0, column=1, padx=10, pady=10)

    password_label = ttk.Label(login_window, text="Password:")
    password_label.grid(row=1, column=0, padx=10, pady=10)

    global password_entry
    password_entry = ttk.Entry(login_window, show="*")
    password_entry.grid(row=1, column=1, padx=10, pady=10)

    login_button = ttk.Button(login_window, text="Login", command=login)
    login_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

    login_window.mainloop()

# Function to register a new student
def register_student():
    student_id = student_id_entry.get()
    name = name_entry.get()
    if not student_id or not name:
        messagebox.showerror("Error", "Please enter both Student ID and Name.")
        return

    # Capture face image
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    # Encode face image
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    if not face_locations:
        messagebox.showerror("Error", "No face detected. Please try again.")
        return

    face_encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]

    # Convert face encoding to bytes
    face_encoding_bytes = face_encoding.tobytes()

    # Insert student data into the database
    sql = "INSERT INTO students (student_id, name, image_data) VALUES (%s, %s, %s)"
    values = (student_id, name, face_encoding_bytes)
    try:
        cursor.execute(sql, values)
        db.commit()
        messagebox.showinfo("Success", "Student registered successfully.")
        student_id_entry.delete(0, tk.END)
        name_entry.delete(0, tk.END)
    except mysql.connector.IntegrityError:
        messagebox.showerror("Error", "Student ID already exists. Please use a different ID.")

last_attendance_time = {}
# Function to mark attendance

def mark_attendance():
    cap = cv2.VideoCapture(0)

    # Load known face encodings from the database
    cursor.execute("SELECT student_id, name, image_data FROM students")
    known_face_encodings = []
    known_face_names = []
    known_student_ids = []
    for row in cursor.fetchall():
        student_id = row[0]
        name = row[1]
        image_data = row[2]
        face_encoding = np.frombuffer(image_data, dtype=np.float64)
        known_face_encodings.append(face_encoding)
        known_face_names.append(name)
        known_student_ids.append(student_id)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for face_encoding, face_location in zip(face_encodings, face_locations):
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
            name = "Unknown"
            student_id = "Unknown"
            if True in matches:
                matched_idx = matches.index(True)
                name = known_face_names[matched_idx]
                student_id = known_student_ids[matched_idx]

            # Get current date and time
                current_date = datetime.date.today()
                current_time = datetime.datetime.now().time()

            if (student_id, name) not in last_attendance_time or \
                        (datetime.datetime.now() - last_attendance_time[(student_id, name)]).seconds >= 60:

                    # Insert attendance data into the database
                    sql = "INSERT INTO attendance (student_id, name, date, time) VALUES (%s, %s, %s, %s)"
                    values = (student_id, name, current_date, current_time)
                    cursor.execute(sql, values)
                    db.commit()

                    # Update the last attendance time for this user
                    last_attendance_time[(student_id, name)] = datetime.datetime.now()

            top, right, bottom, left = face_location
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 0, 255), 2)
            cv2.rectangle(frame, (left, bottom - 25), (right, bottom), (0, 0, 255), cv2.FILLED)
            cv2.putText(frame, f"{name} ({student_id})", (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6, (255, 255, 255), 1)

        cv2.imshow("Attendance", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

def export_attendance():
    cursor.execute("SELECT student_id, name, date, time FROM attendance")
    rows = cursor.fetchall()

    # Generate a unique filename with the current date and time
    current_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("Attendance_Sheets", f"attendance_{current_datetime}.csv")

    with open(filename, "w", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["Student ID", "Name", "Date", "Time"])
        csv_writer.writerows(rows)

    messagebox.showinfo("Success", f"Attendance exported as CSV file: {filename}.")

def export_attendance_pdf():
    cursor.execute("SELECT student_id, name, date, time FROM attendance")
    rows = cursor.fetchall()

    # Generate a unique filename with the current date and time
    current_datetime = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = os.path.join("Attendance_Sheets", f"attendance_{current_datetime}.pdf")
    doc = SimpleDocTemplate(filename, pagesize=letter)
    table_data = [["Student ID", "Name", "Date", "Time"]]
    table_data.extend(rows)

    table = Table(table_data)
    style = TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black)])
    table.setStyle(style)

    content = [table]
    doc.build(content)

    messagebox.showinfo("Success", f"Attendance exported as PDF file: {filename}.")

# Create the main window
def create_main_window():
    global root
    root = tk.Tk()
    root.title("Facial Attendance System")

    # Create tabs
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True)

    # Registration tab
    registration_tab = ttk.Frame(notebook)
    notebook.add(registration_tab, text="Registration")

    student_id_label = ttk.Label(registration_tab, text="Student ID:")
    student_id_label.grid(row=0, column=0, padx=10, pady=10)

    global student_id_entry
    student_id_entry = ttk.Entry(registration_tab)
    student_id_entry.grid(row=0, column=1, padx=10, pady=10)

    name_label = ttk.Label(registration_tab, text="Name:")
    name_label.grid(row=1, column=0, padx=10, pady=10)

    global name_entry
    name_entry = ttk.Entry(registration_tab)
    name_entry.grid(row=1, column=1, padx=10, pady=10)

    register_button = ttk.Button(registration_tab, text="Register", command=register_student)
    register_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

    # Attendance tab
    attendance_tab = ttk.Frame(notebook)
    notebook.add(attendance_tab, text="Attendance")

    attendance_button = ttk.Button(attendance_tab, text="Mark Attendance", command=mark_attendance)
    attendance_button.pack(padx=10, pady=10)

    export_button = ttk.Button(attendance_tab, text="Export as CSV", command=export_attendance)
    export_button.pack(padx=10, pady=10)

    export_pdf_button = ttk.Button(attendance_tab, text="Export as PDF", command=export_attendance_pdf)
    export_pdf_button.pack(padx=10, pady=10)
    
    root.mainloop()

# Show the login window
create_login_window()