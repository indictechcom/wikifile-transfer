# Wikifile Transfer

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![Node.js](https://img.shields.io/badge/node-18+-green.svg)
![Flask](https://img.shields.io/badge/Flask-2.x-black.svg?logo=flask)
![React](https://img.shields.io/badge/React-18-blue.svg?logo=react)
![Redis](https://img.shields.io/badge/Redis-broker-red.svg?logo=redis)
![Docker](https://img.shields.io/badge/Docker-compose-blue.svg?logo=docker)


> A [Toolforge](https://wikifile-transfer.toolforge.org) web application that helps Wikimedia contributors seamlessly transfer media files across Wikimedia projects using MediaWiki APIs and OAuth authentication.


---
## Overview
 
Wikifile Transfer is a [Toolforge](https://wikifile-transfer.toolforge.org) web application maintained by [Indic TechCom](https://meta.wikimedia.org/wiki/Indic-TechCom). It allows Wikimedia contributors to transfer media files (images, documents, etc.) between different Wikimedia projects (e.g., from English Wikipedia to Commons, or between language wikis) without manual downloading and re-uploading.
 
**Live Tool:** https://wikifile-transfer.toolforge.org  
**Issue Tracker:** https://phabricator.wikimedia.org/tag/indic-techcom/  
**Discussion:** https://meta.wikimedia.org/wiki/Talk:Indic-TechCom/Tools/Wikifile-transfer




---
## ⚙️ Prerequisites
 
Before setting up, ensure you have the following installed:
 
| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Backend runtime |
| Node.js + npm | 18+ | Frontend build |
| Redis | Any stable | Task broker |
| MySQL / MariaDB | Any stable | Production DB (SQLite for prototyping) |
| Docker + Compose | Latest | Optional but recommended |
| Wikimedia OAuth | — | Consumer key/secret from [Special:OAuthConsumerRegistration](https://meta.wikimedia.org/wiki/Special:OAuthConsumerRegistration) |


---
 
## 🔧 Configuration
 
Copy the example config and fill in your values:
 
```bash
cp config.yaml.bak config.yaml
```
 
Then edit `config.yaml`:
 
```yaml
ENV: dev                        # Use 'dev' locally, 'prod' on Toolforge
SECRET_KEY: your-secret-key     # Any random string for Flask sessions
CONSUMER_KEY: <wikimedia-consumer-key>
CONSUMER_SECRET: <wikimedia-consumer-secret>
OAUTH_MWURI: https://meta.wikimedia.org/w
SESSION_COOKIE_SECURE: True
SESSION_REFRESH_EACH_REQUEST: False
PREFERRED_URL_SCHEME: https
SQLALCHEMY_DATABASE_URI: mysql+pymysql://user:pass@host/dbname
SQLALCHEMY_TRACK_MODIFICATIONS: False
```
 
> ⚠️ **Never commit `config.yaml` to version control.** It is already listed in `.gitignore`.
 
Also ensure the `temp_images/` directory exists and is writable:
 
```bash
mkdir -p temp_images && chmod 755 temp_images
```
 
---

## 🛠️ Local Development
 
Follow these steps to run the project locally without Docker:
 
### 1. Clone the Repository
 
```bash
git clone https://github.com/indictechcom/wikifile-transfer.git
cd wikifile-transfer
```
 
### 2. Set Up Python Virtual Environment
 
```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```
 
### 3. Configure the App
 
```bash
cp config.yaml.bak config.yaml
# Edit config.yaml with your OAuth credentials and DB URI
```
 
### 4. Set Up the Database
 
```bash
flask db init        # Only required the very first time
flask db migrate -m "initial migration"
flask db upgrade
```
 
### 5. Start Redis
 
```bash
redis-server         # Or use Docker: docker run -p 6379:6379 redis
```
 
### 6. Start the Celery Worker
 
```bash
celery -A celeryWorker.app worker --loglevel=info
```
 
### 7. Start the Flask Backend
 
```bash
python app.py
```
 
Backend will be available at `http://localhost:5001`
 
### 8. Start the React Frontend
 
Open a new terminal:
 
```bash
cd frontend
npm install
npm start
```
 
Frontend will be available at `http://localhost:3000`
 
---
 
## 🐳 Docker Setup
 
The easiest way to get the full stack running locally:
 
```bash
docker-compose up --build
```
 
This spins up three services:
 
| Service | URL |
|---|---|
| Flask backend | `http://localhost:5001` |
| React frontend | `http://localhost:3000` |
| Redis | `localhost:6379` |
 
To stop all services:
 
```bash
docker-compose down
```
---
## 🤝 Contributing
 
We welcome contributions from the community! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
 
- Setting up your development environment
- Submitting pull requests
- Reporting bugs and requesting features
- Coding conventions and branch naming
 
**Bug reports & feature requests:** [Phabricator](https://phabricator.wikimedia.org/tag/indic-techcom/)  
**Discussion:** [Meta-Wiki Talk Page](https://meta.wikimedia.org/wiki/Talk:Indic-TechCom/Tools/Wikifile-transfer)  
**Code contributions:** Fork this repo and open a pull request against `master`






## License

MIT License