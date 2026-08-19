# Setup

This takes about 15 minutes and you only do it once. At the end you will have a
working study you can send to participants.

Keep `check.html` open in a tab while you work through this. After each step,
reload it to see which checks now pass.

---

## Before you start

```bash
git clone https://github.com/ShadowCoder1/markerless-online-experiments.git
cd markerless-online-experiments
python3 -m http.server 8000
```

Leave that running and open <http://localhost:8000/>. The experiment already
works in demo mode without any of the steps below, so you can try it once to see
what your participants will see. Nothing is saved until you finish this page.

Then open <http://localhost:8000/check.html>.

> Browsers do not allow camera access on pages opened straight from disk (a
> `file://` address). Running a local server avoids this. Any static server
> works; Python's is used here because you already have it.

---

## Step 1. Create a Firebase project

1. Go to <https://console.firebase.google.com/> and sign in with a Google account.
2. **Create a project**. Name it after your study, e.g. `tapping-study`.
3. Google Analytics is offered. You do not need it, so turn it off.

The free Spark plan is enough for a typical study. One 15-second tapping trial
is roughly 400 KB, so the free 1 GiB of storage holds somewhere around 2,000
trials.

## Step 2. Register a web app and copy the config

1. On the project overview page, click the **web** icon (`</>`).
2. Give it a nickname. Do not tick Firebase Hosting, because your study is
   hosted on GitHub Pages.
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

> This is safe to commit to a public repository. A Firebase web API key
> identifies your project but does not grant access to it. Access is controlled
> by the rules you publish in step 4. See
> [Google's documentation](https://firebase.google.com/docs/projects/api-keys).

Reload `check.html`. The check named "config.js has been filled in" should now
pass.

## Step 3. Turn on anonymous sign-in

**Build → Authentication → Get started → Sign-in method → Anonymous → Enable.**

This gives every participant a unique id without asking them to make an account,
and it lets the security rules tell a real participant apart from a random bot.

## Step 4. Create the database and publish the rules

1. **Build → Firestore Database → Create database.**
2. Pick the location closest to your participants. **This cannot be changed
   later.**
3. When it offers **production mode** or **test mode**, choose **production
   mode**. You are about to paste your own rules anyway.
4. Open the **Rules** tab, delete what is there, and paste the entire contents of
   **`firestore.rules`** from this repository. Click **Publish**.

> Do not use test mode. It allows anyone on the internet to read and delete your
> participants' data, and it stops working after 30 days. If that happens partway
> through a study, uploads fail silently and you may not notice for some time.

Reload `check.html`. Every check should now pass. If one does not, the page says
which step to go back to.

## Step 4b. Use your own consent form and questions

The included consent form is the one from Prof. Tsay's lab at Carnegie Mellon,
and it is there as an example. Replace `consent/consent-form.pdf` with the
document your own ethics board approved, keeping the same filename.

Then edit `CONSENT.affirmations` in `config.js` so the statements participants
tick match the ones on your form, and edit `questions.js` so the demographic
questions are the ones you want to ask.

Open <http://localhost:8000/preview.html> to see your questions as participants
will see them without running the task. It also warns about common mistakes and
lists the column names your questions will produce.
[docs/EDITING-QUESTIONS.md](EDITING-QUESTIONS.md) is the full guide.

## Step 5. Run it on yourself

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

> If you do not have `gcloud`, install the
> [Google Cloud CLI](https://cloud.google.com/sdk/docs/install). If your
> institution blocks that sign-in, create a service account key in the Firebase
> console (Project settings → Service accounts) and point
> `GOOGLE_APPLICATION_CREDENTIALS` at the downloaded file. Keep that file out of
> git. The `.gitignore` already excludes `data/`, but a key file belongs outside
> the repository entirely.

## Step 6. Going live with Prolific

1. Push your copy to GitHub.
2. **Settings → Pages → Source: Deploy from a branch → `main` / `/ (root)` → Save.**
3. Wait a minute, then open `https://<your-username>.github.io/<your-repo>/` and
   run `check.html` again on that address. A study that works on localhost can
   still fail once it is online, so it is worth checking there too.
4. In Prolific, set the study URL to your Pages address. Prolific appends
   `?PROLIFIC_PID=…&STUDY_ID=…&SESSION_ID=…`, which the study reads
   automatically, so there is nothing to configure.
5. Copy your Prolific completion URL into `completionRedirectUrl` in `config.js`
   so participants are sent back and paid:

```js
completionRedirectUrl: "https://app.prolific.com/submissions/complete?cc=XXXXXXXX",
```

6. Pilot the study on yourself through the real Prolific link before you open
   recruitment.

---

## Before you recruit

- [ ] `check.html` passes on the public URL, not just on localhost
- [ ] You have run the study on yourself and looked at the figure
- [ ] `consent/consent-form.pdf` is your own approved form, not the example
- [ ] `CONSENT.affirmations` matches the statements on your form
- [ ] `completionRedirectUrl` is set, and you have tested the redirect
- [ ] The marked taps in the figure line up with taps you actually made
- [ ] You have deleted your pilot sessions, or noted their IDs so you can exclude them
