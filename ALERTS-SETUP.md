# Setting up alerts

## The one thing to know first

Alerts fire when the engine finds a new role. So the engine has to be
*running* on its own for alerts to mean anything. Running it manually on your
laptop and then getting a notification about what you just watched it find
isn't useful.

So yes — alerts means the GitHub route after all. It's free, and it's the
scheduled runner that makes the whole thing work while you're in class.

Total time: about 15 minutes, most of it waiting on the first run.

---

## Part 1 — Get it running on GitHub (10 min)

1. Go to github.com and make a new repository. Public. Name it whatever —
   `internships` is fine. Don't add a README or .gitignore.

2. Unzip this folder, open a terminal inside it, and run:

   ```
   git init
   git add -A
   git commit -m "initial"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPO.git
   git push -u origin main
   ```

   It'll ask you to sign in. Use a personal access token, not your password —
   GitHub will prompt you through it.

3. In the repo: **Settings → Actions → General** → under "Actions permissions"
   pick *Allow all actions*. Save.

4. **Settings → Pages** → Source: *Deploy from a branch*, branch `main`,
   folder `/docs`. Save.

5. **Actions** tab → **Update internships** in the sidebar → **Run workflow**.

   First run takes a few minutes. When it's green, your list is live. After
   this it runs itself every 30 minutes.

---

## Part 2 — Telegram alerts (5 min)

This is the one to use. Free, unlimited, real lock-screen push on your phone,
no email infrastructure. Discord and email are covered below but Telegram is
less work and better for personal alerts.

1. Install Telegram on your phone if you don't have it.

2. Open Telegram, search for **@BotFather**, start a chat, send `/newbot`.
   Follow the prompts (it asks for a name, then a username ending in `bot`).
   It gives you a **token** that looks like
   `8123456789:AAH7xK2p...`. Copy it.

3. Search for **@userinfobot**, start it, and it replies with your numeric
   user ID. Copy that — it's your **chat id**.

4. Go back to your new bot and send it any message ("hi"). A bot can't message
   you until you've messaged it first. This step is easy to miss and it's why
   most people's first test goes nowhere.

5. In your GitHub repo: **Settings → Secrets and variables → Actions** →
   **New repository secret**. Add two:

   | Name | Value |
   | --- | --- |
   | `TELEGRAM_BOT_TOKEN` | the token from step 2 |
   | `TELEGRAM_CHAT_ID` | the number from step 3 |

That's it. Next time the engine finds a new role you get a push.

### Testing it

Don't wait around. Actions → Update internships → Run workflow. If the run is
green but no push arrives, it's almost always step 4 — you haven't messaged the
bot yet. Second most common: the chat id has a typo.

Note that alerts only fire for **newly found** roles. If a run finds nothing
new, you correctly get nothing. Right after the first run the store already
knows about everything, so the first few runs may legitimately be quiet.

---

## Part 3 — Discord (optional, 3 min)

Only worth it if you already live in a Discord server.

1. In a server you own: **Server Settings → Integrations → Webhooks → New
   Webhook**. Pick a channel, then **Copy Webhook URL**.
2. Add it as the repo secret `DISCORD_WEBHOOK_URL`.

You get one rich embed per role, color-coded by cycle, capped at 50 roles per
run so it can't spam the channel.

---

## Part 4 — Email digest (optional, ~30 min, probably skip)

Be warned: this one is built for running a public list that *other people*
subscribe to through the dashboard. For alerting just yourself it's a lot of
work for a worse result than Telegram.

It needs four secrets and a database:

- A **Supabase** project (free tier) with an `email_subscribers` table and RLS
  policies, plus `supabase_url` and `supabase_publishable_key` added to
  `data/config.json` to turn the signup form back on.
- A **Brevo** account (free tier, 300/day) with a verified sender address.
- Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `BREVO_API_KEY`, `MAIL_FROM`.

I stripped the original author's Supabase credentials out of the config, so
this is genuinely off until you add your own. If you do want it later, the
table schema and RLS policies are documented in `src/intern_engine/mailer.py`
and `src/intern_engine/db.py`.

---

## Turning down the volume

If alerts get noisy, `data/config.json` is where you fix it:

- `include_general_engineering` → `false`. Biggest lever. Stops bare
  "Engineering Intern" postings from alerting.
- `max_per_company` → lower it. Stops one employer flooding you.
- `cycles` → drop `"Fall 2026"` if you only want Summer 2027.

Commit and push after editing; the next scheduled run picks it up.

## If alerts stop

Check the Actions tab for red runs. GitHub disables scheduled workflows on
repos with no activity for 60 days — it emails you first, and one manual run
re-arms it.
