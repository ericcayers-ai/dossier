# Contributing

Thanks for helping improve Dossier — a local-first job-search workspace with a
language-model socket. Please read this guide before opening a pull request.

By participating, you agree to follow our [Code of Conduct](CODE_OF_CONDUCT.md).

## What belongs in this repo

Do **not** commit:

- Secrets, API tokens, cookies, or model-provider credentials
- **Real job-search data** — captured listings, resumes, application records,
  cover letters, or recruiter correspondence belonging to a real person
- Screenshots or logs containing a real name, email address, phone number,
  home address, employer, or student ID
- Generated `ui/dist` build output or virtualenvs

If you need fixtures for tests, use synthetic or clearly fictional samples only.
This project's whole purpose is handling one person's private material; treat
every example as if it will be published, because it will be.

## Development setup

You need **Python 3.13**.

```bash
uv sync
```

Run the engine against a working folder:

```bash
uv run dossier --root "C:\path\to\folder" --open
```

The UI is a separate Vite app under `ui/`:

```bash
cd ui && npm install && npm run build && cd ..
```

## Running tests

```bash
py -3.13 -m pytest -q
```

`pyproject.toml` pins `pythonpath = ["src"]` for pytest. The built server serves
`ui/dist`; during UI development `npm run dev` works with the Vite dev server.

A doctor command checks the environment:

```bash
python -m dossier.cli doctor --root .
```

## Pull request expectations

- Keep the mechanical/model boundary intact: the engine owns state and gates,
  the model owns judgement. Do not move a gate into a prompt.
- Add or update tests for behaviour changes; a new engine action needs a test.
- Keep diffs scoped. Unrelated reformatting makes review harder.
- Update `README.md` or `DESIGN.md` when you change a documented contract.

## Questions

Open a [discussion or issue](https://github.com/ericcayers-ai/dossier/issues)
rather than sending a patch without context.
