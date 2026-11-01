# 🌟 Vibely - Modern Social Media Platform

Vibely is a feature-rich, fully responsive social media web application built with a modern tech stack. It allows users to connect, share posts, manage profile details, and interact seamlessly through an Instagram-inspired UI.

---

## 🚀 Tech Stack

* **Backend:** Python, Flask, Gunicorn (Production WSGI)
* **Database:** TiDB Cloud (MySQL-Compatible Distributed Database)
* **Frontend:** Tailwind CSS, HTML5, JavaScript (AJAX for Infinite Scroll & Dynamic Interactions)
* **Styling & UI:** Glassmorphism effects, Custom Instagram-style gradients, FontAwesome icons

---

## ✨ Key Features

* **User Authentication & Profiles:** Secure signup/login system with dynamic profile pages, follower/following counts, and verification badges.
* **Dynamic Post Feed:** AJAX-powered infinite scrolling displaying randomized posts and user suggestions.
* **Settings & Privacy Module:** Dedicated settings panel featuring an **About Account** modal and an editable **Edit Account** dialog (Name, Username, Bio, Date of Birth, and Gender).
* **Responsive Design:** Optimized for both desktop (glassmorphism sidebar) and mobile devices (fixed bottom navigation bar).

---

## 📁 Project Structure

```text
vibely/
│
├── static/
│   ├── assets/           # Logos, badges, and static images
│   └── ...
├── templates/
│   ├── home.html         # Main feed and post creation
│   ├── profile.html      # User profile and post grid
│   └── settings.html     # Settings, About, and Edit modals
│
├── .gitignore            # Excludes .venv, .env, and cache files
├── app.py                # Main Flask application backend & routes
├── requirements.txt      # Python dependencies list
└── README.md             # Project documentation