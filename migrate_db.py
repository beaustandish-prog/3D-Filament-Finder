import sqlite3

def add_quantity_column():
    conn = sqlite3.connect('filament_minder.db')
    c = conn.cursor()
    
    try:
        c.execute('ALTER TABLE inventory ADD COLUMN quantity INTEGER DEFAULT 1')
        print("Successfully added 'quantity' column.")
    except sqlite3.OperationalError as e:
        print(f"Skipped: {e} (Column might already exist)")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_quantity_column()
