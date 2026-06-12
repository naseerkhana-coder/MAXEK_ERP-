# VPS backup to GitHub

Yes — you can back up your **current VPS** (database + files) to **GitHub**. Use a **private repository** only.

---

## What gets backed up

| Item | Included by default |
|------|---------------------|
| `maxek.db` (production data) | Yes |
| Application code archive | Yes |
| Templates / static archives | Yes |
| Uploaded documents | Yes |
| `.env` (secrets) | **No** (enable only if you accept the risk) |

---

## Option A — Push from VPS (automated)

### 1. Create a private GitHub repo

1. GitHub → **New repository**
2. Name: `maxek-erp-vps-backup` (or any name)
3. Visibility: **Private**
4. Do not add README (empty repo is fine)

### 2. Add SSH key on VPS (recommended)

On the VPS:

```bash
ssh-keygen -t ed25519 -C "maxek-vps-backup" -f ~/.ssh/id_ed25519_github -N ""
cat ~/.ssh/id_ed25519_github.pub
```

Copy the public key → GitHub → **Settings → SSH and GPG keys → New SSH key**

Test:

```bash
ssh -T -i ~/.ssh/id_ed25519_github git@github.com
```

Add to `~/.ssh/config`:

```
Host github.com
  IdentityFile ~/.ssh/id_ed25519_github
  IdentitiesOnly yes
```

### 3. Configure backup on VPS

```bash
cd /var/www/maxek_erp
cp deploy/github_backup.env.example deploy/github_backup.env
nano deploy/github_backup.env   # set YOUR GitHub username/repo
chmod 600 deploy/github_backup.env
chmod +x deploy/vps_backup_to_github.sh deploy/vps_backup.sh
```

### 4. Run backup → GitHub

```bash
bash deploy/vps_backup_to_github.sh /var/www/maxek_erp
```

Each run creates a folder like `snapshots/20260611_143000/` on branch `vps-backups`.

### 5. Schedule (optional — weekly)

```bash
sudo crontab -e
```

Add:

```
0 2 * * 0 www-data cd /var/www/maxek_erp && bash deploy/vps_backup_to_github.sh /var/www/maxek_erp >> /var/log/maxek_github_backup.log 2>&1
```

---

## Option B — Download from VPS, push from Windows PC

If you prefer not to put Git credentials on the VPS:

### 1. Backup on VPS (SSH)

```bash
cd /var/www/maxek_erp
bash deploy/vps_backup.sh
```

Note the folder, e.g. `/var/www/maxek_erp/backups/backup_20260611_1430/`

### 2. Download with WinSCP

Download that entire `backup_YYYYMMDD_HHMM` folder to your PC, e.g.:

`C:\Users\rajee\Documents\maxek-vps-backups\backup_20260611_1430\`

### 3. Push to GitHub from PC

```powershell
cd "C:\Users\rajee\Documents\maxek-vps-backups"
git init
git checkout -b vps-backups
git remote add origin https://github.com/naseerkhana-coder/maxek-erp-vps-backup.git
git add backup_20260611_1430
git commit -m "VPS backup 2026-06-11"
git push -u origin vps-backups
```

Use `gh auth login` first if GitHub asks for authentication.

---

## Push application **code** to GitHub (separate from data backup)

Your PC project can hold source code **without** production database:

```powershell
cd "C:\Users\rajee\Documents\New project"
git remote add origin https://github.com/naseerkhana-coder/maxek-erp.git
```

Add to `.gitignore` (already recommended):

```
MAXEK_ERP/database/*.db
MAXEK_ERP/deploy/github_backup.env
.env
```

Then:

```powershell
git add MAXEK_ERP
git commit -m "feat: MAXEK ERP application"
git push -u origin master
```

**Do not** commit `maxek.db` or `.env` to the code repository unless the repo is private and you intentionally want that.

---

## Restore from GitHub backup

```bash
# On VPS — stop app
sudo systemctl stop maxek-erp

# Copy DB from cloned backup repo
cp /path/to/snapshots/20260611_143000/maxek.db /var/www/maxek_erp/database/maxek.db
sudo chown www-data:www-data /var/www/maxek_erp/database/maxek.db

sudo systemctl start maxek-erp
```

---

## Security checklist

- [ ] GitHub repository is **Private**
- [ ] `.env` is **not** pushed (unless you explicitly enable it)
- [ ] `github_backup.env` is **not** committed to git
- [ ] VPS SSH key is dedicated for backup repo only
- [ ] Two-factor authentication enabled on GitHub account
