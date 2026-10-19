from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import datetime

app = Flask(__name__)
app.secret_key = 'cinema_secret_key'

DB_NAME = 'cinema.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# Дерекқорды және кестелерді автоматты түрде құру функциясы
def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS Genres (
        GenreID INTEGER PRIMARY KEY AUTOINCREMENT,
        GenreName TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS Films (
        FilmID INTEGER PRIMARY KEY AUTOINCREMENT,
        Title TEXT NOT NULL,
        GenreID INTEGER,
        DurationMinutes INTEGER,
        AgeRating TEXT,
        FOREIGN KEY (GenreID) REFERENCES Genres(GenreID)
    );

    CREATE TABLE IF NOT EXISTS Cinemas (
        CinemaID INTEGER PRIMARY KEY AUTOINCREMENT,
        Name TEXT NOT NULL,
        Address TEXT NOT NULL,
        City TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS Halls (
        HallID INTEGER PRIMARY KEY AUTOINCREMENT,
        CinemaID INTEGER,
        HallName TEXT NOT NULL,
        Capacity INTEGER,
        FOREIGN KEY (CinemaID) REFERENCES Cinemas(CinemaID)
    );

    CREATE TABLE IF NOT EXISTS PriceCategories (
        PriceCategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
        CategoryName TEXT NOT NULL,
        PriceMultiplier REAL
    );

    CREATE TABLE IF NOT EXISTS Seats (
        SeatID INTEGER PRIMARY KEY AUTOINCREMENT,
        HallID INTEGER,
        RowNumber INTEGER,
        SeatNumber INTEGER,
        PriceCategoryID INTEGER,
        FOREIGN KEY (HallID) REFERENCES Halls(HallID),
        FOREIGN KEY (PriceCategoryID) REFERENCES PriceCategories(PriceCategoryID)
    );

    CREATE TABLE IF NOT EXISTS Sessions (
        SessionID INTEGER PRIMARY KEY AUTOINCREMENT,
        FilmID INTEGER,
        HallID INTEGER,
        StartTime TEXT,
        BasePrice REAL,
        FOREIGN KEY (FilmID) REFERENCES Films(FilmID),
        FOREIGN KEY (HallID) REFERENCES Halls(HallID)
    );

    CREATE TABLE IF NOT EXISTS Bookings (
        BookingID INTEGER PRIMARY KEY AUTOINCREMENT,
        SessionID INTEGER,
        SeatID INTEGER,
        CustomerPhone TEXT,
        BookingTime TEXT,
        Status TEXT DEFAULT 'Pending',
        FOREIGN KEY (SessionID) REFERENCES Sessions(SessionID),
        FOREIGN KEY (SeatID) REFERENCES Seats(SeatID)
    );

    CREATE TABLE IF NOT EXISTS Payments (
        PaymentID INTEGER PRIMARY KEY AUTOINCREMENT,
        BookingID INTEGER UNIQUE,
        Amount REAL,
        PaymentTime TEXT,
        PaymentMethod TEXT,
        FOREIGN KEY (BookingID) REFERENCES Bookings(BookingID)
    );

    CREATE TABLE IF NOT EXISTS Tickets (
        TicketID INTEGER PRIMARY KEY AUTOINCREMENT,
        BookingID INTEGER UNIQUE,
        TicketCode TEXT UNIQUE,
        IssuedAt TEXT,
        FOREIGN KEY (BookingID) REFERENCES Bookings(BookingID)
    );
    ''')
    
    # Егер кестелер бос болса, тесттік деректер қосу
    cursor.execute("SELECT COUNT(*) FROM Films")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO Genres (GenreName) VALUES ('Фантастика'), ('Экшн'), ('Анимация')")
        cursor.execute("INSERT INTO PriceCategories (CategoryName, PriceMultiplier) VALUES ('Стандарт', 1.0), ('VIP', 1.5)")
        cursor.execute("INSERT INTO Cinemas (Name, Address, City) VALUES ('Kinopark Esentai', 'әл-Фараби 77', 'Алматы')")
        cursor.execute("INSERT INTO Halls (CinemaID, HallName, Capacity) VALUES (1, 'IMAX Зал', 20)")
        
        # Орындар жасау (2 қатар, 10 орыннан)
        for r in range(1, 3):
            for s in range(1, 11):
                cat = 2 if r == 2 else 1
                cursor.execute("INSERT INTO Seats (HallID, RowNumber, SeatNumber, PriceCategoryID) VALUES (1, ?, ?, ?)", (r, s, cat))
                
        cursor.execute("INSERT INTO Films (Title, GenreID, DurationMinutes, AgeRating) VALUES ('Аватар: Су жолы', 1, 192, '12+')")
        cursor.execute("INSERT INTO Films (Title, GenreID, DurationMinutes, AgeRating) VALUES ('Дюна: 2-бөлім', 1, 166, '16+')")
        
        cursor.execute("INSERT INTO Sessions (FilmID, HallID, StartTime, BasePrice) VALUES (1, 1, '2026-11-01 15:00', 2500)")
        cursor.execute("INSERT INTO Sessions (FilmID, HallID, StartTime, BasePrice) VALUES (2, 1, '2026-11-01 19:00', 3000)")
        
        conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    # Белсенді сеанстар
    sessions = cursor.execute('''
        SELECT s.SessionID, f.Title, f.AgeRating, c.Name, h.HallName, s.StartTime, s.BasePrice,
               (h.Capacity - (SELECT COUNT(*) FROM Bookings b WHERE b.SessionID = s.SessionID AND b.Status IN ('Pending', 'Paid'))) AS FreeSeats
        FROM Sessions s
        JOIN Films f ON s.FilmID = f.FilmID
        JOIN Halls h ON s.HallID = h.HallID
        JOIN Cinemas c ON h.CinemaID = c.CinemaID
    ''').fetchall()
    conn.close()
    return render_template('index.html', sessions=sessions)

@app.route('/session/<int:session_id>')
def select_seat(session_id):
    conn = get_db()
    cursor = conn.cursor()
    session_info = cursor.execute('''
        SELECT s.SessionID, f.Title, h.HallName, s.StartTime, s.BasePrice, h.HallID
        FROM Sessions s
        JOIN Films f ON s.FilmID = f.FilmID
        JOIN Halls h ON s.HallID = h.HallID
        WHERE s.SessionID = ?
    ''', (session_id,)).fetchone()

    seats = cursor.execute('''
        SELECT st.SeatID, st.RowNumber, st.SeatNumber, pc.CategoryName, pc.PriceMultiplier,
               CASE 
                   WHEN b.BookingID IS NOT NULL AND b.Status IN ('Pending', 'Paid') THEN 1 
                   ELSE 0 
               END AS IsBooked
        FROM Seats st
        JOIN PriceCategories pc ON st.PriceCategoryID = pc.PriceCategoryID
        LEFT JOIN Bookings b ON st.SeatID = b.SeatID AND b.SessionID = ? AND b.Status IN ('Pending', 'Paid')
        WHERE st.HallID = ?
        ORDER BY st.RowNumber, st.SeatNumber
    ''', (session_id, session_info['HallID'])).fetchall()
    conn.close()
    return render_template('seats.html', session=session_info, seats=seats)

@app.route('/book', methods=['POST'])
def book_seat():
    session_id = request.form['session_id']
    seat_id = request.form['seat_id']
    phone = request.form['phone']

    conn = get_db()
    cursor = conn.cursor()
    
    # Орынның бос екенін тексеру
    existing = cursor.execute('''
        SELECT BookingID FROM Bookings 
        WHERE SessionID = ? AND SeatID = ? AND Status IN ('Pending', 'Paid')
    ''', (session_id, seat_id)).fetchone()

    if existing:
        conn.close()
        flash("Бұл орын бос емес немесе брондалған!")
        return redirect(url_for('select_seat', session_id=session_id))

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
        INSERT INTO Bookings (SessionID, SeatID, CustomerPhone, BookingTime, Status)
        VALUES (?, ?, ?, ?, 'Pending')
    ''', (session_id, seat_id, phone, now))
    conn.commit()
    booking_id = cursor.lastrowid
    conn.close()
    return redirect(url_for('pay', booking_id=booking_id))

@app.route('/pay/<int:booking_id>')
def pay(booking_id):
    conn = get_db()
    cursor = conn.cursor()
    booking = cursor.execute('''
        SELECT b.BookingID, f.Title, st.RowNumber, st.SeatNumber, (s.BasePrice * pc.PriceMultiplier) AS Price
        FROM Bookings b
        JOIN Sessions s ON b.SessionID = s.SessionID
        JOIN Films f ON s.FilmID = f.FilmID
        JOIN Seats st ON b.SeatID = st.SeatID
        JOIN PriceCategories pc ON st.PriceCategoryID = pc.PriceCategoryID
        WHERE b.BookingID = ?
    ''', (booking_id,)).fetchone()
    conn.close()
    return render_template('ticket.html', booking=booking)

@app.route('/confirm_payment', methods=['POST'])
def confirm_payment():
    booking_id = request.form['booking_id']
    conn = get_db()
    cursor = conn.cursor()
    
    booking = cursor.execute('''
        SELECT s.BasePrice, pc.PriceMultiplier, b.BookingID
        FROM Bookings b
        JOIN Sessions s ON b.SessionID = s.SessionID
        JOIN Seats st ON b.SeatID = st.SeatID
        JOIN PriceCategories pc ON st.PriceCategoryID = pc.PriceCategoryID
        WHERE b.BookingID = ?
    ''', (booking_id,)).fetchone()

    amount = booking[0] * booking[1]
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ticket_code = f"TKT-{booking_id}-{int(datetime.datetime.now().timestamp())}"

    cursor.execute("UPDATE Bookings SET Status = 'Paid' WHERE BookingID = ?", (booking_id,))
    cursor.execute("INSERT INTO Payments (BookingID, Amount, PaymentTime, PaymentMethod) VALUES (?, ?, ?, 'Kaspi')", (booking_id, amount, now))
    cursor.execute("INSERT INTO Tickets (BookingID, TicketCode, IssuedAt) VALUES (?, ?, ?)", (booking_id, ticket_code, now))
    conn.commit()
    conn.close()

    return f"<div style='text-align:center; padding:50px; font-family:sans-serif;'><h2>Төлем сәтті өтті!</h2><p>Билет коды: <b>{ticket_code}</b></p><a href='/'>Басты бетке оралу</a></div>"

if __name__ == '__main__':
    app.run(debug=True, port=5000)