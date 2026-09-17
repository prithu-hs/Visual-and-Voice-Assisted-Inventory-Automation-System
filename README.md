\# Visual and Voice-Assisted Inventory Automation System



An AI-powered inventory management web application built with Python and Flask. The system combines visual product detection using YOLO and voice-based commands to simplify inventory management, stock updates, shopping, and billing.



\## Features



\- User registration and login

\- Role-based Admin and User access

\- Inventory and product management

\- Stock addition, removal, and adjustment

\- Low-stock and out-of-stock monitoring

\- Visual product detection using YOLO

\- Voice-based inventory commands

\- Shopping cart and purchase management

\- Real-time stock updates using Flask-SocketIO

\- Transaction history

\- Automatic PDF invoice generation

\- Product and order management



\## Technologies Used



\### Backend

\- Python

\- Flask

\- Flask-SocketIO

\- SQLite



\### AI and Automation

\- YOLO / Ultralytics

\- OpenCV

\- PyTorch

\- SpeechRecognition

\- Google Speech Recognition

\- gTTS



\### Frontend

\- HTML5

\- CSS3

\- Bootstrap

\- JavaScript



\### Other Libraries

\- NumPy

\- Pillow

\- ReportLab

\- PyDub



\## Project Structure



```text

Visual-and-Voice-Assisted-Inventory-Automation-System/

│

├── models/

│   ├── coco.names

│   └── yolov4.cfg

│

├── static/

│

├── templates/

│   ├── base.html

│   ├── dashboard.html

│   ├── login.html

│   ├── product\_detail.html

│   ├── products.html

│   ├── register.html

│   ├── transactions.html

│   ├── user\_dashboard.html

│   ├── user\_orders.html

│   ├── user\_shop.html

│   ├── visual\_search.html

│   └── voice\_control.html

│

├── app.py

├── speech\_recognizer.py

├── yolo\_detector.py

├── requirements.txt

├── yolov8n.pt

└── .gitignore

