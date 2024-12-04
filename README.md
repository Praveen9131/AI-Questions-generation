# Question Types and Identifiers

This document provides an overview of the different types of questions and their corresponding identifiers that can be used in quiz applications.

## Question Types and Codes

| **Question Type** | **Identifier Code** |
|-------------------|---------------------|
| Simple Radio Button | 100 |
| Simple Radio Button with Image Question | 500 |
| Image Radio Button | 701 |
| Image Radio Button with Image Question | 600 |
| True False Radio Button with Image & Text Question | 700 |
| Appropriate Radio with Image & Text Question | 900 |
| Fill In The Blank with drag and drop feature | 300 |
| Match the Sequence with drag and drop feature | 400 |
| Simple Checkbox | 200 |
| Simple Checkbox with Image Question | 501 |
| Image Checkbox | 601 |
| Image Checkbox with Image Question | 602 |
| Simple Radio Button and Text/Image Sub Question | 800 |
| Image Radio Button and Text/Image Sub Question | 801 |
| Simple Checkbox and Text/Image Sub Question | 802 |
| Image Checkbox and Text/Image Sub Question | 803 |

## Notes
- Some question types do not have identifier codes provided. These should be added when the appropriate information is available.
- The identifiers are intended to categorize different types of questions in a quiz or survey application for easy reference and implementation.

## Usage
These identifier codes can be used in your application to programmatically create and manage different question types, ensuring that the appropriate format and functionality are applied to each question.

---

# AI Question Generator

This repository contains a collection of scripts for generating various types of questions using generative AI. The types of questions include multiple-choice questions (MCQs), checkbox questions, fill-in-the-blank questions, and image-based questions.

## Table of Contents

- [Installation](#installation)
- [Usage](#usage)
- [Scripts](#scripts)
- [Deployment](#deployment)
- [Contributing](#contributing)
- [License](#license)

---

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/goldsandhu22brain/AiQuestionGenerator.git
    cd AiQuestionGenerator
    ```

2. Install the required packages:

    ```bash
    pip install -r requirements.txt
    ```

---

## Usage

Run the application:

```bash
python app.py
```

# Deployment
## Step-by-Step Deployment Guide:
## Navigate to the Parent Directory:
```bash
cd /var/www/flaskapp
```
## Clone the New Repository:
```bash
sudo git https://github.com/goldsandhu22brain/AiQuestionGenerator.git
```
## Navigate to the Cloned Repository Directory:
```bash

cd AiQuestionGenerator
```
## Install Dependencies:
```bash
pip install -r requirements.txt
```
## Update the Service File (if necessary):
``` bash
sudo nano /etc/systemd/system/flaskapp.service
```

``` bash
[Unit]
Description=Gunicorn instance to serve flaskapp
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/var/www/flaskapp
Environment="PATH=/var/www/flaskapp/venv/bin"
ExecStart=/var/www/flaskapp/venv/bin/gunicorn --workers 3 --bind unix:/var/www/flaskapp/flaskapp.sock --timeout 700 -m 007 wsgi:app

[Install]
WantedBy=multi-user.target
```
## Reload the Systemd Daemon:
``` bash
sudo systemctl daemon-reload
```
## Restart the Gunicorn Service:
``` bash
sudo systemctl restart flaskapp
```

## Check the Status of the Service:
``` bash
sudo systemctl status flaskapp
```
## View the Logs Using Journalctlsudo journalctl -u flaskapp -f

``` bash
sudo journalctl -u flaskapp -f
```
## Create Nginx Config for Flask App:

``` bash
sudo nano /etc/nginx/sites-available/flaskapp
```

## add
``` bash
server {
    listen 80;
    server_name your-server-ip;  # Replace this with your server's IP or domain name

    location / {
        proxy_pass http://unix:/var/www/flaskapp/flaskapp.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /var/www/flaskapp/static/;
    }
}
```
## Enable the Nginx Site Configuration:
``` bash
sudo ln -s /etc/nginx/sites-available/flaskapp /etc/nginx/sites-enabled
```
## Restart Nginx:
```bash
sudo systemctl restart nginx
```
