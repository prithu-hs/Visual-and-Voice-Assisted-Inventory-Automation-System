import speech_recognition as sr
import pyaudio
import wave
import threading
import time
import json
import sqlite3
from gtts import gTTS
import os
import tempfile
from pydub import AudioSegment
from pydub.playback import play


class SpeechRecognizer:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.is_listening = False
        self.current_thread = None
        
        # Adjust for ambient noise
        print("Adjusting for ambient noise...")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=2)
        print("Speech recognizer initialized")
    
    def recognize_speech_google(self, audio_data):
        """Recognize speech using Google Speech Recognition"""
        try:
            text = self.recognizer.recognize_google(audio_data)
            return text, True
        except sr.UnknownValueError:
            return "Could not understand audio", False
        except sr.RequestError as e:
            return f"Error with speech recognition service: {e}", False
    
    def recognize_speech_from_mic(self, timeout=5, phrase_time_limit=10):
        """Capture and recognize speech from microphone"""
        try:
            with self.microphone as source:
                print("Listening...")
                audio = self.recognizer.listen(
                    source, 
                    timeout=timeout, 
                    phrase_time_limit=phrase_time_limit
                )
            
            print("Processing speech...")
            return self.recognize_speech_google(audio)
            
        except sr.WaitTimeoutError:
            return "No speech detected", False
        except Exception as e:
            return f"Error capturing audio: {e}", False
    
    def start_continuous_listening(self, callback, timeout=5):
        """Start continuous listening in a separate thread"""
        self.is_listening = True
        
        def listen_loop():
            while self.is_listening:
                text, success = self.recognize_speech_from_mic(timeout=timeout)
                callback(text, success)
                time.sleep(0.1)  # Small delay between listens
        
        self.current_thread = threading.Thread(target=listen_loop)
        self.current_thread.daemon = True
        self.current_thread.start()
    
    def stop_continuous_listening(self):
        """Stop continuous listening"""
        self.is_listening = False
        if self.current_thread:
            self.current_thread.join(timeout=1)
    
    def process_voice_command(self, command_text,user_id=None):
        """Process voice command and execute inventory actions"""
        command_text = command_text.lower().strip()
        response = {
            'success': True,
            'command': command_text,
            'processed': False,
            'message': 'Command processed successfully',
            'action_taken': None
        }
        
        try:
            # Parse command using NLP-like rules
            words = command_text.split()
            print("words==",words)
            
            # Inventory check commands
            if any(word in command_text for word in ['stock', 'inventory', 'how many']):
                if 'low' in command_text or 'out' in command_text:
                    response.update(self.get_low_stock_info())
                else:
                    # Check specific product stock
                    product_name = self.extract_product_name(command_text)
                    if product_name:
                        response.update(self.get_product_stock(product_name))
                    else:
                        response.update(self.get_inventory_summary())
            
            # Stock modification commands
            elif 'add' in command_text or 'restock' in command_text or 'update' in command_text:
                quantity = self.extract_quantity(command_text)
                product_name = self.extract_product_name(command_text)
                print("quantity==",quantity)
                print("product_name==",product_name)
                
                if quantity and product_name:
                    response.update(self.add_stock(product_name, quantity))
                else:
                    response.update({
                        'success': False,
                        'message': 'Please specify both product and quantity'
                    })
            
            # Remove stock commands
            elif any(word in command_text for word in ['remove', 'sell', 'sale']):
                quantity = self.extract_quantity(command_text)
                product_name = self.extract_product_name(command_text)
                
                if quantity and product_name:
                    response.update(self.remove_stock(product_name, quantity, user_id=user_id))
                else:
                    response.update({
                        'success': False,
                        'message': 'Please specify both product and quantity'
                    })
            
            # Help commands
            elif any(word in command_text for word in ['help', 'what can', 'how to']):
                response.update(self.get_help_commands())
            elif any(word in command_text for word in ['buy', 'purchase', 'order']):
                product_name = self.extract_product_name(command_text)
                quantity = self.extract_quantity(command_text) or 1
                if product_name:
                    response.update(self.remove_stock(product_name, quantity, user_id=user_id))
                    response['message'] = f"You purchased {quantity} {product_name}(s). Thank you!"
                else:
                    response.update({'success': False,'message': 'Please specify the product to buy.' })
            elif any(word in command_text for word in ['add','cart','caught', 'add to cart','had','add to caught']):
                quantity = self.extract_quantity(command_text) or 1
                product_name = self.extract_product_name(command_text)
                if product_name:
                    # This will be handled by the cart system
                    response.update({'processed': True,'message': f'Added {quantity} {product_name} to cart','action_taken': 'add_to_cart'})
                else:
                    response.update({'success': False,'message': 'Please specify the product to add to cart'})
            elif any(word in command_text for word in ['checkout', 'complete purchase','End ']):
                response.update({'processed': True,'message': 'Proceeding to checkout...','action_taken': 'checkout'
            
    })
                
            
            else:
                response.update({
                    'processed': False,
                    'message': 'Command not recognized. Say "help" for available commands.'
                })
            
            # Log the command
            self.log_voice_command(command_text, response['message'], response['success'])
            
        except Exception as e:
            response.update({
                'success': False,
                'message': f'Error processing command: {str(e)}'
            })
        
        return response
    
    def extract_quantity(self, text):
        """Extract quantity from command text"""
        words = text.split()
        for i, word in enumerate(words):
            if word.isdigit():
                return int(word)
            # Handle spelled out numbers
            number_words = {
                'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10
            }
            if word in number_words:
                return number_words[word]
        return None
    
    def extract_product_name(self, text):
        """Extract product name from command text"""
        # Common product keywords to ignore
        ignore_words = ['stock', 'inventory', 'add', 'remove', 'sell', 'check', 
                       'how', 'many', 'much', 'the', 'a', 'an', 'to', 'from']
        
        words = [word for word in text.split() if word not in ignore_words and not word.isdigit()]
        
        # Look for product in database
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                possible_name = ' '.join(words[i:j])
                product = cursor.execute(
                    'SELECT name FROM products WHERE name LIKE ?', 
                    (f'%{possible_name}%',)
                ).fetchone()
                
                if product:
                    conn.close()
                    return product[0]
        
        conn.close()
        return None
    
    def get_low_stock_info(self):
        """Get information about low stock items"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        low_stock = cursor.execute('''
            SELECT name, current_stock FROM products 
            WHERE current_stock <= min_stock_level 
            ORDER BY current_stock ASC
        ''').fetchall()
        
        conn.close()
        
        if low_stock:
            items = ', '.join([f"{name} ({stock} left)" for name, stock in low_stock[:3]])
            message = f"Low stock items: {items}"
            if len(low_stock) > 3:
                message += f" and {len(low_stock) - 3} more items"
        else:
            message = "No low stock items"
        
        return {
            'processed': True,
            'message': message,
            'action_taken': 'low_stock_check'
        }
    
    def get_product_stock(self, product_name):
        """Get stock for specific product"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        product = cursor.execute(
            'SELECT name, current_stock FROM products WHERE name LIKE ?',
            (f'%{product_name}%',)
        ).fetchone()
        
        conn.close()
        
        if product:
            message = f"{product[0]} has {product[1]} units in stock"
        else:
            message = f"Product '{product_name}' not found"
        
        return {
            'processed': True,
            'message': message,
            'action_taken': 'product_stock_check'
        }
    
    def get_inventory_summary(self):
        """Get inventory summary"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        total_products = cursor.execute('SELECT COUNT(*) FROM products').fetchone()[0]
        total_stock = cursor.execute('SELECT SUM(current_stock) FROM products').fetchone()[0]
        low_stock = cursor.execute('SELECT COUNT(*) FROM products WHERE current_stock <= min_stock_level').fetchone()[0]
        
        conn.close()
        
        message = f"You have {total_products} products with {total_stock} total units. {low_stock} items are low on stock."
        
        return {
            'processed': True,
            'message': message,
            'action_taken': 'inventory_summary'
        }
    
    def add_stock(self, product_name, quantity):
        """Add stock to product"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        print("add_stock is called")
        product = cursor.execute(
        'SELECT id, name, current_stock FROM products WHERE name LIKE ?',
        (f'%{product_name}%',)).fetchone()
        if product:
            new_stock = product[2] + quantity
            cursor.execute('UPDATE products SET current_stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',(new_stock, product[0]))
            # Record transaction log
            cursor.execute('''INSERT INTO transactions (product_id, transaction_type, quantity, previous_stock, new_stock, notes) VALUES (?, 'restock', ?, ?, ?, ?)''', (product[0], quantity, product[2], new_stock, 'Voice command restock'))
            conn.commit()
            message = f"✅ Added {quantity} units to {product[1]}. New stock: {new_stock}"
        else:
            message = f"⚠️ Product '{product_name}' not found"
        conn.close()

        return {'processed': True,'message': message,'action_taken': 'add_stock'}

    
    # In the remove_stock method, ensure the order is properly recorded
    def remove_stock(self, product_name, quantity, user_id=None):
        """Remove stock from product"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        product = cursor.execute('SELECT id, name, current_stock, price FROM products WHERE name LIKE ?',(f'%{product_name}%',)).fetchone()
        if product:
            if product[2] >= quantity:
                new_stock = product[2] - quantity
                cursor.execute('UPDATE products SET current_stock = ? WHERE id = ?',(new_stock, product[0]))
                cursor.execute('''INSERT INTO transactions (product_id, transaction_type, quantity, previous_stock, new_stock, notes)VALUES (?, 'sale', ?, ?, ?, ?)''', (product[0], quantity, product[2], new_stock, 'Voice command sale'))
                if user_id:
                    try:
                        total_price = (product[3] or 1.0) * quantity
                        cursor.execute('''INSERT INTO orders (user_id, product_id, quantity, total_price) VALUES (?, ?, ?, ?)''', (user_id, product[0], quantity, total_price))
                        print(f"✅ Order logged for user_id={user_id}")
                    except Exception as e:
                        print("⚠️ Order logging failed:", e)
                else:
                    print("⚠️ No user_id provided; skipping order logging.")
                conn.commit()
                message = f"✅ Purchased {quantity} {product[1]}(s). Total: ₹{total_price:.2f}. New stock: {new_stock}"
            else:
                message = f"❌ Not enough stock. Only {product[2]} units available."
        else:
            message = f"❌ Product '{product_name}' not found"
        conn.close()
        return {'processed': True,'message': message,'action_taken': 'remove_stock','success': product is not None and product[2] >= quantity }
    
    


    
    def get_help_commands(self):
        """Return help message with available commands"""
        message = """
        Available commands:
        - 'Check stock of [product]' - Get product stock level
        - 'Add [quantity] [product] to stock' - Restock product
        - 'Remove [quantity] [product] from stock' - Sell product
        - 'Show low stock' - Get low stock items
        - 'Inventory summary' - Get overall inventory status
        """
        
        return {
            'processed': True,
            'message': message,
            'action_taken': 'help'
        }
    
    def log_voice_command(self, command_text, result, success):
        """Log voice command to database"""
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO voice_commands (command_text, processed_result, confidence, success)
            VALUES (?, ?, ?, ?)
        ''', (command_text, result, 0.8, success))
        
        conn.commit()
        conn.close()
    
    def text_to_speech(self, text):
        """Convert text to speech and play it"""
        try:
            tts = gTTS(text=text, lang='en')
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                tts.save(tmp_file.name)
                # Play the audio file
                audio = AudioSegment.from_mp3(tmp_file.name)
                play(audio)
            os.unlink(tmp_file.name)
        except Exception as e:
            print(f"Text-to-speech error: {e}")

# Global speech recognizer instance
speech_recognizer = SpeechRecognizer()