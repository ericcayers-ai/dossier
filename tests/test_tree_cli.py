import json

from dossier import cli


def test_tree_cli_add_link_status_and_view(tmp_path, capsys):
    root = tmp_path / "workspace"
    root.mkdir()

    assert cli.main(["tree", "add", "--root", str(root), "--id", "experience", "--type", "experience", "--title", "Past project", "--state", "complete", "--json"]) == 0
    experience = json.loads(capsys.readouterr().out)
    assert experience["id"] == "experience"

    assert cli.main(["tree", "add", "--root", str(root), "--id", "email", "--type", "touchpoint", "--title", "Inbound email", "--state", "complete", "--json"]) == 0
    capsys.readouterr()
    assert cli.main(["tree", "link", "--root", str(root), "--parent", "experience", "--child", "email", "--json"]) == 0
    link = json.loads(capsys.readouterr().out)
    assert link == {"parent_id": "experience", "child_id": "email"}

    assert cli.main(["tree", "status", "--root", str(root), "--json"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["node_count"] == 2 and status["link_count"] == 1

    assert cli.main(["tree", "view", "--root", str(root), "--format", "mermaid"]) == 0
    assert "graph TD" in capsys.readouterr().out


def test_tree_cli_sync_imports_a_workspace_corpus(tmp_path, capsys):
    root = tmp_path / "workspace"
    aggregate = root / "all_boards_data"
    aggregate.mkdir(parents=True)
    (aggregate / "all_jobs.json").write_text(json.dumps([{"id": 1, "title": "Engineer", "employer": "Acme"}]), encoding="utf-8")
    (root / "job-history.md").write_text(
        "| Date | Company | Role | Fit | Resume file | Status |\n"
        "|---|---|---|---|---|---|\n"
        "| Sep 2026 | Acme | Engineer | High | missing.docx | drafted |\n",
        encoding="utf-8",
    )

    assert cli.main(["tree", "sync", "--root", str(root), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["jobs_seen"] == 1
    assert report["tracker_matched"] == 1
    assert cli.main(["tree", "view", "--root", str(root), "--json"]) == 0
    graph = json.loads(capsys.readouterr().out)
    assert sum(node["type"] == "opportunity" for node in graph["nodes"]) == 1
    job = next(node for node in graph["nodes"] if node["type"] == "opportunity")
    assert job["data"]["tracker"]["status"] == "drafted"
