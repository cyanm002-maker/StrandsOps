# OpsRanger Backend Guide (Node.js / Express — Beginner Step-by-Step)

Welcome! If you are new to backend development or connecting Node.js to another service, this guide is made for you. You will build the **Node.js + Express (JavaScript)** backend inside the `server/` folder of **OpsRanger: Incident Copilot**.

---

## 1. What Is Your Role in This Project?

Our project has two backend pieces working together:
1. **Your Node.js Backend (`server/`):** Receives incoming alerts (like CloudWatch alerts), calls the Python RAG service to get client-specific runbooks, runs basic diagnostic/approval logic, and sends clean responses back.
2. **Python RAG Microservice (`rag-service/`):** Already runs on `http://localhost:8000` and answers `POST /retrieve` with matching `.txt` runbooks filtered by `client_id` so one client's data never leaks into another's.

You do **not** need TypeScript—we are using plain JavaScript (`.js`) so it is faster and easier to build and debug.

---

## 2. Before You Start: What You Need Installed

Make sure you have these two tools on your computer:
- **Node.js** (v18 or newer recommended). Check in terminal with:
  ```bash
  node -v
  npm -v
  ```
- **Postman** (or Thunder Client / VS Code REST Client) to test your API endpoints without needing the React frontend yet.

---

## 3. Folder Structure Inside `server/`

Keep your backend organized inside `server/` like this:

```text
server/
├── .env
├── package.json
└── src/
    ├── index.js                  # Main server entry point (start here!)
    ├── routes/
    │   └── alert.routes.js       # Alert API routes
    ├── controllers/
    │   └── alert.controller.js   # Handles incoming alert requests
    └── services/
        └── rag.service.js        # Calls the Python RAG microservice via Axios
```

> **Beginner Tip:** On **Day 1**, you can put everything in `server/src/index.js` first to see it work quickly, then split into `routes/`, `controllers/`, and `services/` once it runs.

---

## 4. Step-by-Step Setup Instructions

### Step 1: Initialize the Node.js Project
Open your terminal, go into the `server/` folder, and initialize the project:

```bash
cd server
npm init -y
```

Install the packages you need:
- `express`: Creates the web server and API routes.
- `axios`: Sends HTTP requests from Node.js to the Python RAG service (`http://localhost:8000/retrieve`).
- `dotenv`: Loads secret/config variables from a `.env` file.
- `cors`: Allows frontend apps to talk to your backend later.

```bash
npm install express axios dotenv cors
```

*(Optional)* Install `nodemon` so your server restarts automatically when you save a file:
```bash
npm install --save-dev nodemon
```

### Step 2: Configure `package.json` for `import` / `export`
Open `server/package.json` and add `"type": "module"` (and a helpful `start` script):

```json
{
  "name": "server",
  "version": "1.0.0",
  "type": "module",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "dev": "nodemon src/index.js"
  },
  "dependencies": {
    "axios": "^1.7.0",
    "cors": "^2.8.5",
    "dotenv": "^16.4.0",
    "express": "^4.19.0"
  },
  "devDependencies": {
    "nodemon": "^3.1.0"
  }
}
```

### Step 3: Create Your `.env` File
Create a file named `.env` inside `server/` (do not commit real secrets to Git):

```env
PORT=5000
PYTHON_RAG_URL=http://localhost:8000
```

### Step 4: Write Your First Working Server (`src/index.js`)
Create `server/src/index.js` and paste this starter code:

```javascript
import express from 'express';
import dotenv from 'dotenv';
import cors from 'cors';
import axios from 'axios';

dotenv.config();

const app = express();
app.use(express.json());
app.use(cors());

const PORT = process.env.PORT || 5000;
const PYTHON_RAG_URL = process.env.PYTHON_RAG_URL || 'http://localhost:8000';

// 1. Health check route to confirm your server is alive
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', service: 'opsranger-node-backend' });
});

// 2. Main alert endpoint: receives an alert -> calls Python RAG -> returns context
app.post('/api/v1/alerts', async (req, res) => {
  try {
    const { alert_message, client_id, severity = 'HIGH' } = req.body;

    // Basic validation so beginners see clear errors if fields are missing
    if (!alert_message || !client_id) {
      return res.status(400).json({
        error: 'Both alert_message and client_id are required.'
      });
    }

    console.log(`[Alert Received] client_id=${client_id} | severity=${severity}`);

    // Call the Python RAG service on port 8000
    const ragResponse = await axios.post(`${PYTHON_RAG_URL}/retrieve`, {
      query: alert_message,
      client_id: client_id
    });

    // Simple starter diagnostic + approval flag for the hackathon flow
    const retrievedContext = ragResponse.data;

    return res.status(200).json({
      status: 'analyzed',
      client_id,
      severity,
      alert_message,
      retrieved_context: retrievedContext,
      next_step: 'Review retrieved runbook, run safe read-only checks, and request approval for risky actions.'
    });
  } catch (error) {
    console.error('Error talking to RAG service:', error.message);
    return res.status(502).json({
      error: 'Failed to reach Python RAG microservice',
      details: error.message
    });
  }
});

app.listen(PORT, () => {
  console.log(`Node.js backend running at http://localhost:${PORT}`);
});
```

---

## 5. How to Run & Test Everything Step by Step

### Test A: Start Python RAG First (Port `8000`)
Ask your teammate running `rag-service/` to start it so it is listening on `http://localhost:8000`.

### Test B: Start Your Node.js Server (Port `5000`)
In your `server/` terminal:
```bash
npm start
```
You should see:
```text
Node.js backend running at http://localhost:5000
```

### Test C: Check `/health` in Postman
1. Open **Postman**.
2. Create a **GET** request to `http://localhost:5000/health`.
3. Click **Send** -> You should get `200 OK` with `{"status":"ok","service":"opsranger-node-backend"}`.

### Test D: Test `/api/v1/alerts` + Client Isolation
1. Create a **POST** request to `http://localhost:5000/api/v1/alerts`.
2. Go to **Body -> raw -> JSON** and send:
   ```json
   {
     "alert_message": "How do I fix database connection exhaustion?",
     "client_id": "client_alpha",
     "severity": "CRITICAL"
   }
   ```
3. Click **Send** and verify `retrieved_context` returns `client_alpha` data.
4. Now change `"client_id"` to `"client_beta"` and send again—verify you do **not** get `client_alpha`'s database runbook back.

---

## 6. Next Features to Add After Postman Works

Once `POST /api/v1/alerts` works cleanly end-to-end:
1. **Split code into `routes/`, `controllers/`, and `services/`** so it's easy for two people to edit without merge conflicts.
2. **Add simulated read-only diagnostics** (e.g., mock CloudWatch metrics/logs) and a **root-cause hypothesis** field in the response.
3. **Add a human-in-the-loop approval flow** (e.g., `status: "PENDING_APPROVAL"` for risky actions + a `POST /api/v1/approvals/:id/resolve` route).
4. **Add an incident summary** output once resolved.