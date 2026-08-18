# Setup

About 15 minutes, once. At the end you will have a working study you can send to
participants.

Keep `check.html` open in a tab while you work through this — after each step,
reload it and watch another line go green.

---

## Before you start

```bash
git clone https://github.com/ShadowCoder1/markerless-online-experiments.git
cd markerless-online-experiments
python3 -m http.server 8000
```

Leave that running and open <http://localhost:8000/> — the experiment already
works, in demo mode, without any of the steps below. Try it once to see what
your participants will see. Nothing is saved until you finish this page.

Then open <http://localhost:8000/check.html>.

> **Why a server?** Browsers refuse camera access to pages opened straight from
> disk (a `file://` address). A local server makes the browser treat the page as
> trustworthy. Any static server works; Python's is just the one you already have.

---

## Step 1 — Create a Firebase project

1. Go to <https://console.firebase.google.com/> and sign in with a Google account.
2. **Create a project**. Name it after your study, e.g. `tapping-study`.
3. Google Analytics is offered — you do not need it. Turn it off.

Firebase's free Spark plan is enough for a typical study. As a rough guide, one
15-second tapping trial is about 400 KB, so the free 1 GiB of storage holds
somewhere around 2,000 trials.

## Step 2 — Register a web app and copy the config

1. On the project overview page, click the **web** icon (`</>`).
2. Give it a nickname (anything). **Do not** tick Firebase Hosting — your study
   is hosted on GitHub Pages.
3. Firebase shows you a `firebaseConfig` object. Copy the values into the
   `FIREBASE` block at the top of **`config.js`**.

```js
export const FIREBASE = {
  apiKey:            "AIzaSy…",
  authDomain:        "tapping-study.firebaseapp.com",
  projectId:         "tapping-study",
  storageBucket:     "tapping-study.firebasestorage.app",
  messagingSenderId: "123456789012",
  appId:             "1:1234…:web:abcd…",
};
```

> **Is it safe to commit this to a public repo?** Yes. A Firebase web API key
> identifies your project; it does not grant access to it. Access is controlled
> by the rules you publish in step 4. This is
> [Google's documented position](https://firebase.google.com/docs/projects/api-keys).

Reload `check.html` — *"config.js has been filled in"* should now be green.

## Step 3 — Turn on anonymous sign-in

**Build → Authentication → Get started → Sign-in method → Anonymous → Enable.**

This gives every participant a unique id without asking them to make an account,
and it lets the security rules tell a real participant apart from a random bot.

## Step 4 — Create the database and publish the rules

1. **Build → Firestore Database → Create database.**
2. Pick the location closest to your participants. **This cannot be changed
   later.**
3. When it offers **production mode** or **test mode**, choose **production
   mode**. You are about to paste your own rules anyway.
4. Open the **Rules** tab, delete what is there, and paste the entire contents of
   **`firestore.rules`** from this repository. Click **Publish**.

> **Do not use test mode.** It lets anyone on the internet read and delete your
> participants' data, and it stops working after 30 days — which, if you are
> mid-study, means a week of silently failed uploads before you notice.

Reload `check.html`. Everything should now be green. If it is not, the page tells
you which step to revisit.

## Step 5 — Run it on yourself

Open <http://localhost:8000/>. Do the whole thing once, start to finish. Then:

```bash
pip install -r analysis/requirements.txt
gcloud auth application-default login      # once per computer, no key file created
python analysis/fetch_data.py
python analysis/compute_metrics.py
python analysis/visualize.py
```

Open the figure in `data/figures/` and check that the marked taps line up with
taps you actually made. **Do this before you recruit anyone.**

> **No `gcloud`?** Install the
> [Google Cloud CLI](https://cloud.google.com/sdk/docs/install). If your
> institution blocks that sign-in, create a service account key in the Firebase
> console (Project settings → Service accounts) and point
> `GOOGLE_APPLICATION_CREDENTIALS` at the downloaded file. Keep that file out of
> git — the `.gitignore` already excludes `data/`, but a key belongs outside the
> repository entirely.

## Step 6 — Going live with Prolific

1. Push your copy to GitHub.
2. **Settings → Pages → Source: Deploy from a branch → `main` / `/ (root)` → Save.**
3. Wait a minute, then open `https://<your-username>.github.io/<your-repo>/` and
   **run `check.html` again on that address.** A study that works on localhost
   can still fail live, and this is where you find out.
4. In Prolific, set the study URL to your Pages address. Prolific appends
   `?PROLIFIC_PID=…&STUDY_ID=…&SESSION_ID=…`, which the study reads
   automatically — there is nothing to configure.
5. Copy your Prolific completion URL into `completionRedirectUrl` in `config.js`
   so participants are sent back and paid:

```js
completionRedirectUrl: "https://app.prolific.com/submissions/complete?cc=XXXXXXXX",
```

6. **Pilot on yourself through the real Prolific link before opening recruitment.**

---

## A checklist before you recruit

- [ ] `check.html` is all green **on the public URL**, not just localhost
- [ ] You have run the study on yourself and looked at the figure
- [ ] The consent text in `config.js` matches what your IRB approved
- [ ] `completionRedirectUrl` is set, and you have tested the redirect
- [ ] The tap detector's marks line up with taps you actually made
- [ ] You have deleted your pilot sessions, or noted their IDs so you can exclude them
