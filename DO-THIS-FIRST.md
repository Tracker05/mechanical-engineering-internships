# Do this first — complete walkthrough

No coding. No terminal. You'll click through some websites and one app.

**Time:** about 30 minutes, most of it waiting.

There are 10 parts. Do them in order. After each part there's a
**✅ Check** — if what you see matches, move on. If it doesn't, the fix is
right there.

---

## Part 1 — Make a GitHub account (3 min)

Skip if you already have one.

1. Go to **github.com**
2. Click **Sign up**
3. Enter your email, make a password, pick a username.
   - Your username becomes part of your web address, so pick something you
     don't mind being public. `gabe-tamu` over `xX_gabe_Xx`.
4. Verify your email when they send the code.

**✅ Check:** You're logged in and see a page with "Create repository" or a
dashboard. Good.

---

## Part 2 — Unzip the folder (1 min)

1. Find `mechanical-engineering-internships.zip` in your Downloads.
2. **Windows:** right-click → *Extract All* → *Extract*.
   **Mac:** double-click it.
3. You now have a *folder* with the same name. Open it. You should see files
   like `README.md`, `run.py`, and folders named `data`, `src`, `docs`.

**⚠️ Important:** Move this folder somewhere you won't accidentally delete it —
your Documents folder is fine. Not Downloads.

**✅ Check:** You can open the folder and see `run.py` inside. If you only see
another zip file, you didn't extract it — go back to step 2.

---

## Part 3 — Install GitHub Desktop (5 min)

This is the app that uploads your folder to GitHub. It exists so you never have
to type commands.

1. Go to **desktop.github.com**
2. Click the download button (it detects Windows or Mac automatically).
3. Install it like any normal app.
4. Open it. It asks you to sign in — click **Sign in to GitHub.com** and use
   the account from Part 1. It'll bounce you to your browser to approve, then
   back to the app.
5. It asks for a name and email for commits. Anything is fine. Click **Finish**.

**✅ Check:** GitHub Desktop is open and shows "Let's get started!" or a mostly
empty window. Good.

---

## Part 4 — Upload your folder (3 min)

1. In GitHub Desktop: **File** menu → **Add local repository**
2. Click **Choose...** and select the folder you unzipped in Part 2.
   - Pick the folder itself, not a file inside it. If you see `run.py` listed
     when you're browsing, you're one level too deep — go up one.
3. Click **Add repository**.
4. Now look at the top of the window. Click the blue **Publish repository**
   button.
5. A box pops up. This part matters:
   - **Name:** `internships` (or anything you like)
   - **⚠️ UNCHECK the box that says "Keep this code private"**

     This one is not optional. GitHub only gives unlimited free automation to
     public repositories. If you leave it private, it will work for a few days
     and then quietly stop when you run out of free minutes.
6. Click **Publish repository**. Wait maybe 30 seconds.

**✅ Check:** Go to `github.com/YOUR-USERNAME` in your browser. You should see
your new repository listed. Click into it and you should see the files.

---

## Part 5 — Turn on automation (2 min)

By default GitHub won't let a new repo run anything automatically. You have to
allow it.

1. In your repository on github.com, click the **Settings** tab (top right,
   with a gear icon).
2. In the left sidebar, scroll down and click **Actions** → **General**.
3. The first section is "Actions permissions". Select
   **Allow all actions and reusable workflows**.
4. Scroll down and click **Save**.

**✅ Check:** The radio button next to "Allow all actions and reusable
workflows" is filled in.

---

## Part 6 — Turn on the web page (2 min)

This gives you a searchable dashboard at your own web address.

1. Still in **Settings**, click **Pages** in the left sidebar.
2. Under "Build and deployment" → "Source", choose **Deploy from a branch**.
3. Two dropdowns appear underneath:
   - First one (branch): pick **main**
   - Second one (folder): pick **/docs** ← not `/root`
4. Click **Save**.

**✅ Check:** A message appears saying your site is ready to be published, or
gives you a URL like `https://YOUR-USERNAME.github.io/internships/`. The page
won't work yet — that's expected, it needs Part 7 first.

---

## Part 7 — Run it for the first time (5 min, mostly waiting)

1. Click the **Actions** tab at the top of your repository.
2. If you see a big green button saying "I understand my workflows, go ahead
   and enable them", click it.
3. In the left sidebar, click **Update internships**.
4. On the right, click the **Run workflow** dropdown → then the green
   **Run workflow** button.
5. Wait about 10 seconds, then refresh the page. You'll see a run appear with a
   yellow dot (running). It takes **3 to 6 minutes** — it's checking about 4,500
   real company job boards.
6. When the dot turns into a green checkmark, it's done.

**✅ Check:** Go back to the main page of your repository (click the **Code**
tab). The README now shows a table of actual internships instead of the
placeholder text.

**If the dot turns red instead:** click the failed run, then click the step
with the red X to see the message. The most common cause is skipping Part 5.

---

## Part 8 — Make your Telegram bot (5 min)

This is what sends alerts to your phone. It's free and unlimited.

1. Install **Telegram** on your phone (App Store / Play Store) and make an
   account if you don't have one.

2. In Telegram, tap the search icon and search for **BotFather**. Open the one
   with the blue checkmark.

3. Tap **Start**, then send the message: `/newbot`

4. It asks two questions:
   - *"Alright, a new bot. How are we going to call it?"* → type anything,
     like `Gabe Internships`
   - *"Now let's choose a username"* → this must end in `bot`, like
     `gabe_internships_bot`. If it's taken, add numbers.

5. It replies with a message containing your **token**. It looks like:

   ```
   8123456789:AAH7xK2pQr5vNmZ...
   ```

   **Copy the whole thing**, including the numbers before the colon. Email it
   to yourself or paste it in your notes — you need it in Part 9.

6. Now search Telegram for **userinfobot** and open it. Tap **Start**. It
   immediately replies with your info. Copy the **Id** number (just digits,
   like `847392015`).

7. **⚠️ Don't skip this:** go find your own bot in Telegram (search the
   username you made in step 4), open it, and send it any message — just "hi".

   A Telegram bot is not allowed to message you until you've messaged it first.
   This is the single most common reason alerts silently never arrive.

**✅ Check:** You have two things written down — a long token with a colon in
it, and a shorter number that's your ID.

---

## Part 9 — Connect the bot (3 min)

Now you give GitHub those two values so it can send you alerts. They're stored
encrypted — nobody can read them, including you, after you save.

1. In your repository: **Settings** tab → in the left sidebar click
   **Secrets and variables** → then **Actions**.
2. Click the green **New repository secret** button.
3. First secret:
   - **Name:** `TELEGRAM_BOT_TOKEN`
   - **Secret:** paste your token from Part 8 step 5
   - Click **Add secret**
4. Click **New repository secret** again. Second secret:
   - **Name:** `TELEGRAM_CHAT_ID`
   - **Secret:** paste your ID number from Part 8 step 6
   - Click **Add secret**

**⚠️ The names must match exactly** — all capitals, underscores not spaces, no
typos. Copy them from this page if you're unsure.

**✅ Check:** The page lists two secrets: `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`. You can't see their values, only the names. That's correct.

---

## Part 10 — You're done

Nothing left to do. It now runs every 30 minutes on its own, forever, and
messages your phone when it finds something new.

**Where your stuff lives:**

| What | Where |
| --- | --- |
| Searchable dashboard | `https://YOUR-USERNAME.github.io/internships/` |
| Plain list | Your repository's front page |
| Spreadsheet | In the repo, `data/internships.csv` — click it, then **Download** |

---

## Things that will happen, that are normal

**No alerts for a while after setup.** Alerts only fire for *newly discovered*
roles. The first run learned about everything at once, so there's nothing "new"
until a company actually posts something. This is working correctly, not broken.

**The list is short right now.** It's September. Summer 2027 mechanical
postings come out in waves through fall and winter. It'll fill up.

**Some runs take longer than others.** It's polling thousands of real websites.
Some are slow.

**A run occasionally fails.** If one out of twenty is red, ignore it — a
company's site was down. If they're *all* red, something's wrong.

---

## If something's broken

**Alerts never arrive, but runs are green**
Nine times out of ten it's Part 8 step 7 — you haven't messaged your own bot.
Go do that. Otherwise check your two secret names for typos.

**The web page shows 404**
Pages takes a few minutes after the first successful run. If it's been an hour,
recheck Part 6 — the folder dropdown must say `/docs`.

**Every run is red**
Almost always Part 5. Go back and confirm "Allow all actions" is selected.

**Too many alerts / too much junk in the list**
Open `data/config.json` on the GitHub website, click the pencil icon to edit,
and change `"include_general_engineering": true` to `false`. Click
**Commit changes**. That's the biggest single filter — it stops vague
"Engineering Intern" postings from showing up.

**It stopped working after a couple months**
GitHub pauses automation on repos nobody's touched in 60 days. They email you
first. Go to Actions → Update internships → Run workflow, and it's re-armed.

---

## Changing settings later

You don't need GitHub Desktop for small edits. On the GitHub website, click any
file, click the **pencil** icon, make your change, scroll down, click
**Commit changes**. The next run picks it up.

Useful ones in `data/config.json`:

| Setting | What it does |
| --- | --- |
| `include_general_engineering` | `false` = stricter, less noise |
| `max_per_company` | Lower = fewer roles from any one employer |
| `cycles` | Remove `"Fall 2026"` if you only want Summer 2027 |
| `regions` | `["Global"]` to include international roles |
