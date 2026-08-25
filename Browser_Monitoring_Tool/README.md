# 📊 Computer Lab Activity Monitoring System

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)](https://flask.palletsprojects.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-4.5.0-brightgreen.svg)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)


## 🎯 Overview

The **Computer Lab Activity Monitoring System** is a comprehensive solution designed for educational institutions to monitor and analyze student browsing activities in computer labs. It features an automated agent that collects browser history from multiple users, classifies websites using machine learning, and provides a centralized dashboard for real-time monitoring and analytics.

### Key Use Cases
- **Educational Institutions**: Monitor computer lab usage and ensure students stay on task
- **IT Administrators**: Track system usage and identify potential security threats
- **Instructors**: Gain insights into student browsing patterns and interests

---

## ✨ Features

### 🔍 Agent Features
- **Multi-Browser Support**: Extracts history from Chrome, Firefox, Edge, and Brave
- **Multi-User Support**: Scans all user profiles on a Windows system
- **Real-time Collection**: Continuously monitors and collects browsing data
- **VPN Detection**: Automatically detects and disables active VPN connections
- **Offline Buffering**: Stores data locally when server is unreachable
- **Machine Learning**: Classifies URLs into categories using TF-IDF and Random Forest

### 🖥️ Server Features
- **Data Aggregation**: Centralized storage of activity data
- **Machine Learning**: Automatic classification and flagging of suspicious URLs
- **Dashboard**: Interactive web interface with:
  - Real-time data visualization
  - Date-wise filtering
  - Lab and system selection
  - Flag/unflag functionality
  - Category distribution charts

### 🛡️ Security Features
- Basic authentication for dashboard access
- Environment variable-based configuration
- Secure MongoDB connection
- Data encryption in transit

---

## 🛠️ Tech Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Core programming language |
| Flask | 2.3.3 | Web framework for API |
| Flask-CORS | 4.0.0 | Cross-origin resource sharing |
| MongoDB | 4.5.0 | Database for storing records |
| scikit-learn | 1.5.2 | ML for URL classification |
| joblib | 1.4.2 | Model serialization |
| pandas | 2.2.2 | Data manipulation |
| numpy | 1.26.4 | Numerical operations |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| HTML5 | - | Structure |
| CSS3 | - | Styling |
| Bootstrap | 5.3.0 | UI framework |
| Chart.js | - | Data visualization |
| Axios | - | API communication |

### Deployment
| Tool | Purpose |
|------|---------|
| Render | Cloud hosting |
| Gunicorn | WSGI HTTP Server |
| Git | Version control |
---
