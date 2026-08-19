# Editing the questions participants answer

The questions asked before the task live in one file: **`questions.js`**, in the
main folder. It is the only file you need to touch to change them.

After any change, open **`preview.html`** in your browser. It shows the questions
exactly as participants will see them, points out mistakes, and tells you what
the answers will be called in your results. You do not have to run the whole
experiment to check your edits.

```bash
python3 -m http.server 8000
```

then open <http://localhost:8000/preview.html>.

## What one question looks like

```js
{ id: "dominantHand",
  label: "Dominant hand",
  type: "select",
  required: true,
  options: ["Right", "Left", "Ambidextrous", "Prefer not to say"] },
```

- `id` is the name used in your data. Keep it short, one word, no spaces, and do
  not use the same one twice.
- `label` is what the participant reads.
- `type` decides what kind of box they get. The list is further down.
- `required: true` means they cannot continue without answering.
- `options` is the list of choices, for the types that need one.

## Adding a question

Copy any existing entry, paste it, and change it. Put it wherever you want it to
appear in the list. This one asks for years of musical training:

```js
{ id: "yearsMusicTraining",
  label: "Years of musical training",
  type: "number",
  min: 0,
  max: 90,
  placeholder: "e.g. 6" },
```

Save the file, reload `preview.html`, and it is there.

## Removing a question

Delete the whole entry, from its opening `{` to the `},` that closes it. For
example, to stop asking about smoking, delete these four lines:

```js
  { id: "smokingStatus",
    label: "Smoking status",
    type: "select",
    options: ["Never smoked", "Former smoker", "Current smoker", "Prefer not to say"] },
```

To remove the questions page entirely so participants go straight from the
consent form to the task:

```js
export const DEMOGRAPHIC_QUESTIONS = [];
```

## Changing the choices in a drop-down

Edit the `options` list. Adding "Prefer not to say" to the device question:

```js
{ id: "device",
  label: "What device are you using?",
  type: "select",
  required: true,
  options: ["Laptop", "Desktop computer", "Tablet", "Phone", "Prefer not to say"] },
```

Order matters: they appear in the order you write them.

## Changing the wording

Change `label`. The `id` does not have to match, and it is better not to change
`id` once you have started collecting data, because it is the column name in
your results. If you change a label halfway through a study, the answers still
line up. If you change an `id`, they will not.

## The kinds of question

| `type` | What they see | Needs `options` |
|---|---|---|
| `"select"` | a drop-down | yes |
| `"radio"` | every choice shown, pick one | yes |
| `"checkboxes"` | every choice shown, pick any number | yes |
| `"number"` | a box that only accepts numbers | no |
| `"text"` | one line of text | no |
| `"textarea"` | a bigger box for a longer answer | no |

`"radio"` is worth using instead of `"select"` when there are only two or three
choices, because it saves a click.

`"checkboxes"` answers are saved as a list, and appear in your results as a
single column with the choices separated by commas.

## Settings you can add to any question

| Setting | What it does |
|---|---|
| `required: true` | they cannot continue without answering, and a red asterisk appears |
| `help: "..."` | smaller grey text under the label, for an explanation |
| `placeholder: "..."` | greyed-out example inside the box |
| `min:` and `max:` | the allowed range, for `"number"` questions |

## One id that behaves specially

A question with the id `participantId` is also used as the participant's ID in
your data. If somebody arrives from Prolific, it is filled in for them. If they
leave it blank, they are given a random anonymous ID. Delete the question if you
do not want to ask.

## Where the answers turn up

Each answer is stored under `demographics` in the session, and
`analysis/compute_metrics.py` turns it into a column named `demo_` followed by
the id. A question with `id: "age"` becomes the column `demo_age` in
`data/processed/trial_metrics.csv`, alongside the movement measurements, so you
can group by it directly:

```python
import pandas as pd
df = pd.read_csv("data/processed/trial_metrics.csv")
df.groupby("demo_dominantHand")["rate_hz"].mean()
```

`preview.html` lists the exact column names your current questions will produce.

Unanswered optional questions are left out rather than saved as blank, so they
appear as missing values in the table rather than empty text.

## Mistakes that are easy to make

`preview.html` checks for all of these and tells you which question is at fault.

| Mistake | What happens |
|---|---|
| Two questions with the same `id` | the second answer overwrites the first |
| A space in an `id` | awkward column name in your results |
| `"select"` with no `options` | an empty drop-down |
| A missing `label` | the question is skipped |
| A missing comma between entries | the page does not load at all |

That last one is the most common. Every entry ends with `},` and the list ends
with `];`. If the page goes blank after an edit, open the browser console (F12,
or Cmd+Option+J on a Mac) and it will name the line.

## Changing the consent form as well

The consent document is `consent/consent-form.pdf`. Replace it with your own
approved form, keeping the same filename. The statements participants tick are
`CONSENT.affirmations` in `config.js`. See
[CUSTOMIZE.md](CUSTOMIZE.md#the-consent-form).
