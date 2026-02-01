# KKS Sago Factory Management System

A professional, cassava-themed, academic web application for managing the procurement, processing, inventory, and sales of a Sago Factory.

## Project Overview

This system manages the end-to-end lifecycle of sago production:
1.  **Procurement:** Farmers (Producers) submit sell requests for raw cassava.
2.  **Inventory:** Admin manages raw material (Cassava) and finished product (Sago) stocks.
3.  **Production:** Converting raw cassava into sago pearls/powder with cost tracking.
4.  **Sales:** Selling finished products to a single authorized agent.
5.  **Analytics:** Real-time dashboard with charts for supply, sales, and profit/loss.
6.  **Admin Control:** Centralized admin dashboard for all operations.

## Tech Stack

*   **Frontend:** HTML5, CSS3, Bootstrap 5, JavaScript (ES6)
*   **Backend:** Python (Flask)
*   **Database:** SQLite (SQLAlchemy ORM)
*   **Visualization:** Chart.js
*   **Icons:** Font Awesome 6
*   **Animations:** AOS (Animate On Scroll) & Animate.css

## Project Folder Structure

```
d:\factory\
├── app.py                  # Main Flask Application & Routes
├── kks_factory.db          # SQLite Database
├── requirements.txt        # Python Dependencies
├── static\
│   └── css\
│       └── style.css       # Custom Styling (Cassava Theme)
└── templates\
    ├── base.html           # Base Template (Header/Footer/Sidebar)
    ├── index.html          # Public Home & Sell Request Form
    ├── contact.html        # Public Contact Page
    ├── login.html          # Admin Login Page
    ├── dashboard.html      # Admin Dashboard & Analytics
    ├── procurement.html    # Admin Procurement Management
    ├── inventory.html      # Inventory Status (Kg)
    ├── production.html     # Production Batches & Costing
    ├── sales.html          # Sales Management
    ├── payments.html       # Payment Settlement
    ├── reports.html        # Comprehensive Reports
    ├── settings.html       # System Configuration (Packet Weight)
    └── messages.html       # Admin Inbox
```

## Database Schema

The system uses SQLite with the following tables:

1.  **User:** Admin authentication (`username`, `password`).
2.  **ProducerRequest:** Cassava sell requests (`name`, `phone`, `quantity`, `packet_size`, `price`, `status`).
3.  **Inventory:** Stock tracking (`item_name`, `quantity` in Kg).
4.  **Production:** Processing records (`input_qty`, `output_qty`, `cost`, `date`).
5.  **Sale:** Sales records (`quantity`, `rate`, `total_amount`, `agent_name`).
6.  **SystemConfig:** Global settings (`packet_weight`).
7.  **Contact:** Public inquiries (`name`, `email`, `message`).

## Business Logic & Modules

### 1. Procurement (Producer -> Admin)
*   **Public:** Producers submit sell requests via `Sell Cassava` form (Packets × Price).
*   **Admin:** Reviews requests in **Procurement Module**.
*   **Action:** 
    *   **Approve:** Converts packets to Kg and adds to **Raw Cassava Inventory**.
    *   **Reject:** Discards the request.
    *   **Pay:** Marks the transaction as settled in **Payments Module**.

### 2. Production (Raw -> Finished)
*   **Input:** Admin selects quantity of Raw Cassava (Kg) to process.
*   **Process:** System applies a conversion ratio (default 35%) to estimate Sago output.
*   **Update:** Reduces Raw stock, increases Sago stock.
*   **Cost:** Tracks production cost based on raw material price.

### 3. Sales (Finished -> Agent)
*   **Action:** Admin sells Sago (Kg) to "Global Sago Traders".
*   **Update:** Reduces Sago stock, records revenue.
*   **Financials:** Updates Profit & Loss calculation.

### 4. Analytics & Reports
*   **Profit Formula:** `Total Sales - Total Production Cost`.
*   **Charts:** Visualizes supply trends, inventory distribution, and financial performance.

## How to Run the Project

1.  **Prerequisites:** Python 3.x installed.
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Run the Application:**
    ```bash
    python app.py
    ```
4.  **Access the App:**
    *   Open Browser: `http://127.0.0.1:5000`
    *   **Admin Login:**
        *   Username: `admin`
        *   Password: `password123`

## Key Features
*   **Dynamic Packet Config:** Admin can change packet weight in Settings.
*   **Auto-Calculations:** Forms automatically calculate totals (Price × Qty).
*   **Unit Conversion:** Seamlessly handles Packets-to-Kg conversion.
*   **Responsive Design:** Works on mobile and desktop.
