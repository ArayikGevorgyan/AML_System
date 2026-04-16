# Deployment Guide — AML Transaction Monitoring System

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.13 |
| Node.js | 18 or higher |
| npm | 9 or higher |
| Git | Any recent version |

## Backend Setup

Step 1: Navigate to the backend folder

Step 2: Create and activate virtual environment
On macOS/Linux: python3 -m venv venv then source venv/bin/activate

Step 3: Install dependencies
Run: pip install -r requirements.txt

Step 4: Configure environment variables
Copy .env.example to .env and fill in your SMTP credentials

Step 5: Seed database with initial data
Run: python scripts/seed_data.py

Step 6: Import OFAC sanctions data
Requires sdn_advanced.xml file in the Downloads folder.
Run: python scripts/import_sanctions.py

Step 7: Start the backend server
Run: uvicorn main:app --reload --port 8000

Backend runs at: http://localhost:8000
Swagger API docs: http://localhost:8000/docs

## Frontend Setup

Step 1: Navigate to the frontend folder

Step 2: Install dependencies
Run: npm install

Step 3: Start development server
Run: npm start

Frontend runs at: http://localhost:3000

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| SMTP_HOST | SMTP server hostname | sandbox.smtp.mailtrap.io |
| SMTP_PORT | SMTP port | 2525 |
| SMTP_USER | SMTP username | your_username |
| SMTP_PASSWORD | SMTP password or API key | your_password |
| SMTP_FROM | Sender email address | noreply@amlsystem.io |

## Demo Accounts

| Username | Password | Role |
|----------|----------|------|
| admin | Admin@123 | Admin |
| ArayikAnalyst | Analyst@123 | Analyst |
| ArayikSupervisor | Super@123 | Supervisor |

## Daily Data Generation

To automatically generate synthetic transaction data every day at 8:00 AM, run this command once:

crontab -l followed by adding the cron entry pointing to seed_today.py

## Restarting After Shutdown

Terminal 1 (Backend):
cd backend then source venv/bin/activate then uvicorn main:app --reload --port 8000

Terminal 2 (Frontend):
cd frontend then npm start
