import sqlite3
import datetime

def init_db():
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS clock_times (
                 user_id INTEGER,
                 date TEXT,
                 clock_in TEXT,
                 clock_out TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS timestamps (
                 id INTEGER PRIMARY KEY,
                 last_message TEXT)''')
    conn.commit()
    conn.close()

def get_last_message_timestamp():
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute('SELECT last_message FROM timestamps WHERE id = 1')
    result = c.fetchone()
    conn.close()
    if result:
        return datetime.datetime.fromisoformat(result[0])
    return None

def set_last_message_timestamp(timestamp):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO timestamps (id, last_message) VALUES (1, ?)', (timestamp.isoformat(),))
    conn.commit()
    conn.close()

def add_clock_in(user_id, date, clock_in):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("INSERT INTO clock_times (user_id, date, clock_in, clock_out) VALUES (?, ?, ?, ?)",
              (user_id, date, clock_in, None))
    conn.commit()
    conn.close()

def update_clock_out(user_id, date, clock_out):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("UPDATE clock_times SET clock_out = ? WHERE user_id = ? AND date = ? AND clock_out IS NULL",
              (clock_out, user_id, date))
    conn.commit()
    conn.close()

def get_clock_times(user_id, date):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("SELECT clock_in, clock_out FROM clock_times WHERE user_id = ? AND date = ?", (user_id, date))
    rows = c.fetchall()
    conn.close()
    return rows

def get_ongoing_sessions(user_id=None):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    if user_id:
        c.execute("SELECT user_id, date, clock_in FROM clock_times WHERE user_id = ? AND clock_out IS NULL", (user_id,))
    else:
        c.execute("SELECT user_id, date, clock_in FROM clock_times WHERE clock_out IS NULL")
    rows = c.fetchall()
    conn.close()
    return rows

def remove_session(user_id, date, clock_in):
    conn = sqlite3.connect('clock_times.db')
    c = conn.cursor()
    c.execute("DELETE FROM clock_times WHERE user_id = ? AND date = ? AND clock_in = ?", (user_id, date, clock_in))
    conn.commit()
    conn.close()

def get_punish_count(user_id):
    conn = sqlite3.connect('punishments.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS punishments (user_id INTEGER PRIMARY KEY, count INTEGER)")
    cursor.execute("SELECT count FROM punishments WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

def reset_punish_count(user_id):
    conn = sqlite3.connect('punishments.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS punishments (user_id INTEGER PRIMARY KEY, count INTEGER)")
    cursor.execute("UPDATE punishments SET count = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def increment_punish_count(user_id):
    conn = sqlite3.connect('punishments.db')
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS punishments (user_id INTEGER PRIMARY KEY, count INTEGER)")
    current_count = get_punish_count(user_id)
    new_count = current_count + 1
    cursor.execute("INSERT OR REPLACE INTO punishments (user_id, count) VALUES (?, ?)", (user_id, new_count))
    conn.commit()
    conn.close()
    return new_count
