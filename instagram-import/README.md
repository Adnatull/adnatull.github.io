# Instagram import

Turns an Instagram "Download your information" export into `content/travel/`
page bundles, without ever putting the multi-GB export into git.

## One-time setup

1. **Create a Google Cloud service account** (console.cloud.google.com ->
   IAM & Admin -> Service Accounts -> Create). Any project name is fine.
2. **Enable the Google Drive API** for that project (APIs & Services ->
   Enable APIs -> "Google Drive API").
3. **Create a JSON key** for the service account (Keys tab -> Add key ->
   JSON) and download it.
4. **Base64-encode the key** and save it as a repo secret named
   `GDRIVE_SA_KEY_B64`:
   ```
   base64 -i your-key.json | pbcopy   # macOS
   base64 -w0 your-key.json           # Linux
   ```
   Paste the result into GitHub -> Settings -> Secrets and variables ->
   Actions -> New repository secret.
5. **Share the export file/folder in Google Drive** with the service
   account's email address (looks like
   `something@your-project.iam.gserviceaccount.com`, shown on the service
   account's page) -- Viewer access is enough.
6. (Optional, for AI-assisted parsing when Instagram's export format
   changes) add two more secrets: `ANTHROPIC_API_KEY` and
   `ANTHROPIC_MODEL` (a current model name string). If these aren't set,
   posts that fail strict parsing go straight to
   `instagram-import/quarantine/` instead of being guessed at.

## Every time you have a new export

1. Upload the export zip to Google Drive (the folder you shared with the
   service account, or anywhere the service account can read).
2. Open the file in Drive, get its file ID (from the share link, the long
   string between `/d/` and `/view`) or just copy the whole share link.
3. Edit `instagram-import/pending.txt` in this repo, paste the ID/link in,
   commit to `master` -- from the GitHub mobile app this is just
   "edit file -> commit."
4. The Action picks it up, downloads the export straight to the runner
   (never to git), extracts every post it hasn't seen before (tracked in
   `instagram-import-manifest.json` at the repo root), writes each as a
   `content/travel/YYYY/MM/DD/slug/index.md` bundle at full original
   quality, commits just that, and clears `pending.txt`.
5. Re-running with the same or a newer export is safe -- already-imported
   posts (tracked by a hash of their media, not by filename) are skipped.

## If something doesn't parse

Check `instagram-import/quarantine/*.json` -- each file is the raw,
untouched post object plus a reason it couldn't be turned into a post.
Nothing quarantined is ever silently dropped or guessed into a live post.

## What you'll want to check after each import

Posts publish with `draft: false` straight away -- captions come verbatim
from Instagram, `tags` starts empty, and the title falls back to the
Instagram location name (or the first ~60 chars of the caption if there's
no location). Worth a quick skim of new posts under `content/travel/` for
tags/title tweaks before you consider the import "done," but nothing
blocks the build if you skip it.
