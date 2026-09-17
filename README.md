# Visual and Voice-Assisted Inventory Automation System

A Flask-based inventory management system that combines **YOLO object detection** and **voice commands** to make inventory operations faster and easier.

## Features

- User registration and login
- Role-based access for Admin and User
- Product and inventory management
- Real-time stock updates
- Low-stock monitoring
- Product search and details
- YOLO-based visual product detection
- Voice-based inventory commands
- Shopping cart and purchase management
- Order history
- Automatic PDF invoice generation
- SQLite database for storing inventory, users, transactions, and orders
- Flask-SocketIO for real-time communication

## Technologies Used

- **Python**
- **Flask**
- **Flask-SocketIO**
- **SQLite**
- **HTML5**
- **CSS3**
- **Bootstrap**
- **JavaScript**
- **YOLO / Ultralytics**
- **OpenCV**
- **SpeechRecognition**
- **Google Speech Recognition**
- **gTTS**
- **ReportLab**

## Project Structure

```text
Visual-and-Voice-Assisted-Inventory-Automation-System/
│
├── models/
│   ├── coco.names
│   ├── yolov4.cfg
│   └── yolov4.weights
│
├── static/
│
├── templates/
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   ├── product_detail.html
│   ├── products.html
│   ├── register.html
│   ├── transactions.html
│   └── user_dashboard.html
│
├── screenshots/
│   ├── login.png
│   ├── user_dashboard.png
│   ├── Smart_Shop.png
│   ├── Products  Inventory Management.png
│   ├── Voice Control.png
│   └── My_orders.png
│
├── app.py
├── requirements.txt
├── speech_recognizer.py
├── yolo_detector.py
├── yolov8n.pt
└── README.md

How the System Works
1. User Authentication

Users can register and log in to the system. Based on the user's role, different features are displayed.

2. Inventory Management

The admin can:

View products
Monitor current stock
Add or remove stock
View low-stock products
View inventory transactions

3. Visual Product Detection

The system uses YOLO object detection to identify products from an uploaded image or camera input.

The detected objects are matched with products stored in the inventory database.

4. Voice Control

Users can give voice commands such as:
How many apples are available?
Add 5 bottles
Remove 2 books
Buy 1 apple

The system converts speech into text using speech recognition and processes the command using rule-based command handling.

5. Shopping and Orders

Users can purchase products through the shopping system. The system checks stock availability, updates inventory, records the transaction, and stores the order details.

6. PDF Invoice

After a purchase, the system generates a PDF invoice containing:

Customer details
Product details
Quantity
Unit price
Total amount

Installation
1. Clone the repository
git clone https://github.com/prithu-hs/Visual-and-Voice-Assisted-Inventory-Automation-System.git

2. Navigate to the project directory
cd Visual-and-Voice-Assisted-Inventory-Automation-System

3. Create a virtual environment
python -m venv venv

4. Activate the virtual environment

Windows:venv\Scripts\activate

5. Install dependencies
pip install -r requirements.txt

6. Run the application
python app.py

The application will run at:
http://localhost:5000

Key Modules
app.py

Main Flask application containing:

Authentication
Routes
Inventory management
Shopping cart
Purchase processing
PDF billing
API endpoints
SocketIO events

yolo_detector.py

Handles:

YOLO model loading
Image preprocessing
Object detection
Product matching
Bounding-box visualization
speech_recognizer.py

Handles:

Speech recognition
Voice command processing
Product and quantity extraction
Stock updates
Voice command logging
Text-to-speech responses
Future Improvements
Improve authentication and password security
Add advanced product search
Improve voice command understanding
Add more product classes for object detection
Add detailed sales and inventory analytics
Improve mobile responsiveness
Add stronger API validation and access control
Author

Prithu H S

GitHub: https://github.com/prithu-hs
LinkedIn: https://www.linkedin.com/in/prithuhs-917791352