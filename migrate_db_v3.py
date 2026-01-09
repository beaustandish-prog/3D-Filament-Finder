import sqlite3

def add_code_column():
    conn = sqlite3.connect('filament_minder.db')
    c = conn.cursor()
    
    try:
        c.execute('ALTER TABLE inventory ADD COLUMN filament_code TEXT')
        print("Successfully added 'filament_code' column.")
    except sqlite3.OperationalError as e:
        print(f"Skipped: {e} (Column might already exist)")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_code_column()
