# Dokku Deployment Guide

This guide covers the deployment of the Sauspiel Scraper to a self-hosted Dokku instance on a Proxmox VM.

## 1. VM Setup & Dokku Installation

1.  **Create VM**: Create a Debian or Ubuntu VM on Proxmox (e.g., 2GB RAM, 2 CPUs).
2.  **Install Dokku**: Follow the [official Dokku installation guide](https://dokku.com/docs/getting-started/installation/):
    ```bash
    wget -nv -O - https://dokku.com/install/v0.34.14/bootstrap.sh | sudo bash
    ```
3.  **SSH Key**: Add your SSH public key to the `dokku` user:
    ```bash
    cat ~/.ssh/id_rsa.pub | ssh root@your-vm-ip "dokku ssh-keys:add admin"
    ```

## 2. App Creation & Database Setup

On the Dokku host (via SSH):

1.  **Create App**:
    ```bash
    dokku apps:create sauspiel-scraper
    ```
2.  **Install Postgres Plugin**:
    ```bash
    sudo dokku plugin:install https://github.com/dokku/dokku-postgres.git
    ```
3.  **Create & Link Database**:
    ```bash
    dokku postgres:create sauspiel-db
    # This automatically sets the DATABASE_URL environment variable
    dokku postgres:link sauspiel-db sauspiel-scraper
    ```

## 3. Configuration

Set required environment variables:

```bash
dokku config:set sauspiel-scraper \
    FERNET_KEY=your-fernet-key \
    SESSION_SECRET=your-session-secret
```

## 4. Deployment

From your local machine:

1.  **Add Git Remote**:
    ```bash
    git remote add dokku dokku@your-vm-ip:sauspiel-scraper
    ```
2.  **Push Code**:
    ```bash
    git push dokku master
    ```
    *Note: If you use squash-rebase on GitHub, you may need to force push to Dokku:*
    ```bash
    git push dokku master --force
    ```

## 5. Schema Migration & Data Transfer

After the first deployment:

1.  **Run Alembic Migrations**:
    ```bash
    dokku run sauspiel-scraper alembic upgrade head
    ```

2.  **Transfer SQLite Database**:
    If you have existing data to migrate:
    ```bash
    # On your local machine:
    scp output/sauspiel.db root@your-vm-ip:/var/lib/dokku/data/storage/sauspiel-scraper/sauspiel.db
    ```
    *Note: You may need to create the directory and ensure the `dokku` user has permissions.*

3.  **Run Data Migration Script**:
    ```bash
    dokku run sauspiel-scraper python scripts/migrate_sqlite_to_postgres.py
    ```

## 6. Maintenance & Backups

### Database Backups
To export the database:
```bash
dokku postgres:export sauspiel-db > sauspiel-db-backup.dump
```
It is recommended to set up a cron job for regular backups.

### Logs
To view application logs:
```bash
dokku logs sauspiel-scraper -t
```
