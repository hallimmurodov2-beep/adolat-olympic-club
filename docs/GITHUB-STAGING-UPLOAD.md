# Publishing the M1.2 staging checkpoint to GitHub

This archive starts at the repository root. The GitHub repository must be **private**. Push only source files; never publish local databases, backups, passwords, or real student records.

On macOS, after downloading this ZIP to `~/Downloads`:

```sh
cd ~/Downloads
unzip Adolat_Olympic_Club_V2_M1_2_GitHub_Ready.zip -d adolat-olympic-club-upload
cd adolat-olympic-club-upload
git init -b main
git add .
git status --short
git commit -m "Import Adolat Olympic Club V2 M1.2 staging checkpoint"
git remote add origin https://github.com/hallimmurodov2-beep/adolat-olympic-club.git
git push -u origin main
```

If Git asks you to identify yourself, set your name and email with `git config --global user.name` and `git config --global user.email` before re-running the `git commit` line. Sign in to GitHub when prompted by a browser/credential helper. Never paste a token, password, or Supabase credential into the conversation.

**Stop after the GitHub push.** The `render.yaml` and Supabase setup are staging candidates, not a one-click verified school launch. We must create empty Supabase staging resources, run the migrations using an operator connection (not the runtime credential), verify protected Postgres TLS and role policies, set Render secrets, and run hosted security/browser checks.

The original M1.2 application code was preserved. This upload package updates the expected Alembic head in `docs/supabase-setup.md` to `d84f103f71aa` and adds this upload guide plus macOS/Git ignore rules. No cloud credentials or actual account data are part of this ZIP.
