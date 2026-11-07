# Templates — "provide your own .docx"

The resume pipeline has two entry points, and they solve different problems.

| You have | Use | What happens |
|---|---|---|
| your current resume, and want a targeted version | `dossier tailor replace` / the `build` mode | a copy of your base is edited in place; verified by a source diff against it |
| your own template (a form, a house layout, a designed page) | `dossier tailor template` / the `template` mode | a copy of your template is filled; verified by placeholder/value/template checks |

Neither rebuilds a document from a generic layout. The `base-document` gate is unchanged: no
real `.docx`, no document.

## Placeholders

Write `{{Name}}`, `{{ Objective }}`, `{{Skills}}` anywhere a `.docx` holds text: a body
paragraph, a table cell, a header, a footer. A token is a short label (letters, digits,
`_`, `-`, `.`, spaces), so a document that merely contains braces is not mistaken for a
template.

```text
dossier tailor fields --template templates/my-template.docx
```

lists the placeholders in first-appearance order. That is also what the Build pane calls to
draw one input per field.

## Filling

```text
dossier tailor template --template templates/my-template.docx \
                        --spec fields.json --out resume-acme.docx
```

```json
{
  "fields": {
    "Name": "A. C",
    "Objective": "Senior engineer, platform reliability",
    "Skills": "Python, SQL, Playwright",
    "Phone": "021 000 0000"
  },
  "replace": {
    "REFERENCES AVAILABLE ON REQUEST": "References: supplied on request."
  }
}
```

- `fields` fills `{{tokens}}`. A token inside one run is replaced **in that run**, so a bold
  name stays bold. A token Word split across runs falls back to a paragraph-level rewrite
  that keeps the first run's formatting — visible in the report as `mode.paragraph`.
- `replace` swaps a paragraph whose whole text matches exactly, for a template with no
  tokens in one spot.
- A field with no matching placeholder is reported as `unused`, not dropped silently.

## The leftover gate

With the default `strict`, a template that would still contain `{{…}}` is **not written at
all**. The error names the leftovers and the partial document is never created. A
half-filled resume that renders beautifully is still a half-filled resume.

`--allow-leftovers` (or `allow_leftovers: true` over the API) writes the partial document and
reports the leftovers, for the case where you are iterating on the template itself.

## Checking the result

```text
dossier verify template --template templates/my-template.docx \
                        --candidate resume-acme.docx --spec fields.json
```

Three checks, each failing independently:

| Check | It proves |
|---|---|
| `no-leftover-placeholders` | no `{{…}}` survived into the document |
| `values-present` | every supplied value actually appears in the built text |
| `template-preserved` | every token-free paragraph the template wrote is still there |

A source diff is deliberately **not** run against the template: a filled field is a
legitimate difference, and flagging it would make the gate unusable. A render is still
required before anyone calls the document visually verified (`dossier render`, `dossier
verify visual`).

## In the app

**Build** pane → type the template path → **Read placeholders** → one input per field →
**Build from template** → **Check the document**. The pane shows `written`, the fill count,
any unused value, any leftover, and each verification check.

## Limits

- Placeholder substitution is text-level. A template that needs a variable number of rows
  (three jobs one day, five the next) still needs a paragraph-level swap, or a base-document
  build.
- Images and text boxes are not scanned for placeholders (`python-docx` does not expose
  them); a token inside a text box stays unfilled and the leftover gate will say so if it is
  in a paragraph it can read.
- The output inherits the template's page geometry, so one page is the template's decision,
  not a guarantee.
