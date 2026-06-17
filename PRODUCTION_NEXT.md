# Production Next Steps

These are the items intentionally saved for the next production pass.

## 2. HTTPS Behind Nginx / Let's Encrypt

Put the dashboard behind Nginx and use Let's Encrypt certificates so the
website is served over HTTPS.

## 3. Real Domain Name

Point a domain or subdomain at the Ubuntu server and configure Nginx for it.

## 4. Bind Gunicorn To Localhost

After Nginx is in front of the dashboard, change the dashboard service bind
from `0.0.0.0:5000` to `127.0.0.1:5000`.

## 5. Off-Server Backups

Keep local backups for quick rollback, but also copy database backups and
important media to a different server or cloud storage location.
