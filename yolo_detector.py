import cv2
import numpy as np
import torch
from ultralytics import YOLO
import os
import time
from PIL import Image
import sqlite3

class YOLODetector:
    def __init__(self, model_path='models/yolov4.pt', conf_threshold=0.7, iou_threshold=0.4):
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.model = None
        self.class_names = []
        self.is_initialized = False
        
        # Create models directory if it doesn't exist
        os.makedirs('models', exist_ok=True)
        
        self.initialize_model(model_path)
    
    def initialize_model(self, model_path):
        """Initialize YOLO model"""
        try:
            # Try to load custom model first, then fall back to pretrained
            if os.path.exists(model_path):
                self.model = YOLO(model_path)
                print(f"Loaded custom model from {model_path}")
            else:
                # Load pretrained YOLOv8 model (similar architecture to YOLOv4)
                self.model = YOLO('yolov8n.pt')
                print("Loaded pretrained YOLOv8 model")
            
            self.class_names = self.model.names
            self.is_initialized = True
            print(f"YOLO model initialized with {len(self.class_names)} classes")
            
        except Exception as e:
            print(f"Error initializing YOLO model: {e}")
            self.is_initialized = False
    
    def preprocess_image(self, image):
        """Preprocess image for YOLO detection"""
        if isinstance(image, str):
            # Load image from file path
            image = cv2.imread(image)
        elif isinstance(image, np.ndarray):
            # Image is already a numpy array
            pass
        else:
            # Convert PIL Image to numpy array
            image = np.array(image)
            image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        return image
    
    def detect_products(self, image):
        """Detect products in image using YOLO"""
        if not self.is_initialized:
            return {"error": "YOLO model not initialized"}
        
        try:
            # Preprocess image
            processed_image = self.preprocess_image(image)
            
            # Run YOLO detection
            results = self.model(
                processed_image, 
                conf=self.conf_threshold,
                iou=self.iou_threshold,
                verbose=False
            )
            
            detections = []
            
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Extract detection information
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        confidence = box.conf[0].cpu().numpy()
                        class_id = int(box.cls[0].cpu().numpy())
                        class_name = self.class_names[class_id]
                        
                        # Filter for retail-relevant classes
                        retail_classes = ['bottle', 'cup', 'book', 'cell phone', 'banana', 
                                        'apple', 'orange', 'broccoli', 'carrot', 'pizza', 
                                        'donut', 'cake', 'wine glass', 'cup', 'fork', 
                                        'knife', 'spoon', 'bowl', 'chair', 'laptop']
                        
                        if class_name in retail_classes:
                            detection = {
                                'class_name': class_name,
                                'confidence': float(confidence),
                                'bbox': [float(x1), float(y1), float(x2), float(y2)],
                                'class_id': class_id
                            }
                            detections.append(detection)
            
            # Match detections with inventory products
            matched_products = self.match_with_inventory(detections)
            
            return {
                'success': True,
                'detections': detections,
                'matched_products': matched_products,
                'total_detections': len(detections)
            }
            
        except Exception as e:
            return {"error": f"Detection failed: {str(e)}"}
    
    def match_with_inventory(self, detections):
        """Match detected objects with inventory products"""
        conn = sqlite3.connect('inventory.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        matched_products = []
        
        # Get all products from database
        products = cursor.execute('SELECT * FROM products').fetchall()
        
        for detection in detections:
            class_name = detection['class_name']
            
            # Simple keyword matching (in real implementation, use embeddings)
            for product in products:
                product_name = product['name'].lower()
                
                # Check if detection class matches product name
                if class_name in product_name or any(word in product_name for word in class_name.split()):
                    matched_product = dict(product)
                    matched_product['detection_confidence'] = detection['confidence']
                    matched_product['detection_bbox'] = detection['bbox']
                    matched_products.append(matched_product)
                    break
        
        conn.close()
        return matched_products
    
    def draw_detections(self, image, detections):
        """Draw detection bounding boxes on image"""
        image_with_boxes = self.preprocess_image(image).copy()
        
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            confidence = detection['confidence']
            class_name = detection['class_name']
            
            # Draw bounding box
            cv2.rectangle(image_with_boxes, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            
            # Draw label
            label = f"{class_name}: {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
            cv2.rectangle(image_with_boxes, (int(x1), int(y1) - label_size[1] - 10),
                         (int(x1) + label_size[0], int(y1)), (0, 255, 0), -1)
            cv2.putText(image_with_boxes, label, (int(x1), int(y1) - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        
        return image_with_boxes

# Global detector instance
detector = YOLODetector()