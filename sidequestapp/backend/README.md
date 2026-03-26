# 🗺️ Side Quest App — Backend Setup

## Prerequisites
- Python 3.9+
- pip

---

## 1. Set Up the Backend

```bash
# Clone / move these files to a folder, then:
cd sidequests-backend

# Create a virtual environment
python -m venv venv

# Activate it
# On Mac/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python app.py
```

The API will be live at: **http://localhost:5000**

The SQLite database (`sidequests.db`) and `uploads/` folder are created automatically on first run.  
100 quests are seeded automatically.

---

## 2. Environment Variables (for production)

Create a `.env` file and update `app.py` to use `os.environ.get(...)`:

```
SECRET_KEY=your-very-secret-key
JWT_SECRET_KEY=your-jwt-secret-key
DATABASE_URL=sqlite:///sidequests.db
```

---

## 3. API Endpoints

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login, get JWT token |
| GET | `/api/auth/me` | Get current user |

### Users
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users` | List all users |
| GET | `/api/users/<id>` | Get a user profile |
| PATCH | `/api/users/me` | Update own profile |

### Quests
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/quests` | Get all 100 quests |
| GET | `/api/quests/<id>` | Get one quest |

### Completions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/completions` | Submit a completion (multipart/form-data with optional photo) |
| GET | `/api/completions/me` | My completions |
| GET | `/api/completions/feed` | Global activity feed |

### Schedules
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/schedules` | Get my (or another user's) schedule |
| POST | `/api/schedules` | Add a schedule slot |
| DELETE | `/api/schedules/<id>` | Delete a slot |

### Leaderboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/leaderboard` | Ranked leaderboard |

---

## 4. Authentication

All routes (except register/login) require a JWT Bearer token:

```
Authorization: Bearer <your_token>
```

The frontend stores this in localStorage and sends it with every request.

---

## 5. Photo Uploads

Completions can include a photo. Send as `multipart/form-data`:

```
POST /api/completions
Content-Type: multipart/form-data

quest_id: 3
mode: duo
partner_ids: 2,4
note: We actually did it!!
photo: [file]
```

Uploaded photos are served at `/api/uploads/<filename>`.

---

## 6. Deploying to Production

### Render (free tier)
1. Push code to GitHub
2. Create a new Web Service on render.com
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `gunicorn app:app`
5. Add `gunicorn` to requirements.txt

### Railway
1. `railway init` then `railway up`

### Heroku
1. Add `Procfile`: `web: gunicorn app:app`
2. `git push heroku main`

---

## 7. Connecting the Frontend

In the React app, update the API base URL:
```js
const API = 'http://localhost:5000'  // development
// or
const API = 'https://your-deployed-url.com'  // production
```
